import json
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import get_db
from app.models.risk_tables import RiskWithdrawDecision, UserDevice

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def calculate_delta(current, previous):
    """Helper to calculate percentage change safely."""
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 1)

@router.get("/")
async def dashboard_index(request: Request, db: AsyncSession = Depends(get_db)):
    # 1. TIME FILTER: Fetch Last 48 Hours to enable Trend Analysis
    now_utc = datetime.now(timezone.utc)
    cutoff_time = now_utc - timedelta(hours=48)
    midpoint_time = now_utc - timedelta(hours=24) # The split point between Current and Prev
    
    result = await db.execute(
        select(RiskWithdrawDecision)
        .where(RiskWithdrawDecision.decision_timestamp >= cutoff_time)
        .order_by(RiskWithdrawDecision.decision_timestamp.desc())
    )
    logs = result.scalars().all()

    # --- 2. FETCH COUNTRIES (Batch Fetch) ---
    txn_ids = []
    for log in logs:
        if log.txn_id and str(log.txn_id).isdigit():
            txn_ids.append(int(log.txn_id))
    
    txn_country_map = {}
    if txn_ids:
        unique_ids = list(set(txn_ids))
        device_res = await db.execute(
            select(UserDevice.event_id, UserDevice.country)
            .where(UserDevice.event_id.in_(unique_ids))
        )
        for row in device_res.all():
            if row[1]:
                txn_country_map[str(row[0])] = row[1]

    # --- 3. DEDUPLICATION (Last Write Wins) ---
    unique_txns = {} 
    
    # We still need raw logs for Latency calculation (Operational Metric)
    # But we limit latency calc to the CURRENT 24h to represent current system health
    metrics_latency = {"rule_sum": 0, "rule_count": 0, "ai_sum": 0, "ai_count": 0}
    hourly_latency = defaultdict(lambda: {"rule": [], "ai": []})
    
    ai_save_of_day = None
    highest_ai_confidence = 0.0

    for log in logs:
        # Standardize Timezone
        if log.decision_timestamp.tzinfo:
            ts_utc = log.decision_timestamp.astimezone(timezone.utc)
        else:
            ts_utc = log.decision_timestamp.replace(tzinfo=timezone.utc)

        # A. Operational Stats (Latency) - ONLY for Current 24h
        if ts_utc >= midpoint_time:
            source = "AI_AGENT_REVIEW" if "AI" in (log.decision_source or "") else "RULE_ENGINE_RULES"
            ts_key = ts_utc.strftime("%d %H:00")
            lat = float(log.processing_time_ms or 0)
            
            if source == "RULE_ENGINE_RULES":
                metrics_latency["rule_sum"] += lat
                metrics_latency["rule_count"] += 1
                hourly_latency[ts_key]["rule"].append(lat)
            else:
                metrics_latency["ai_sum"] += lat
                metrics_latency["ai_count"] += 1
                hourly_latency[ts_key]["ai"].append(lat)

            # AI Insight Logic (Current 24h only)
            if source == "AI_AGENT_REVIEW" and log.decision == "REJECT":
                conf = float(log.confidence or 0)
                if conf > highest_ai_confidence:
                    highest_ai_confidence = conf
                    ai_save_of_day = log

        # B. Build Unique Map
        if log.txn_id:
            curr = unique_txns.get(log.txn_id)
            log_ts = ts_utc # Use the standardized one
            if curr:
                curr_ts = curr.decision_timestamp.astimezone(timezone.utc) if curr.decision_timestamp.tzinfo else curr.decision_timestamp.replace(tzinfo=timezone.utc)
                if log_ts > curr_ts:
                    unique_txns[log.txn_id] = log
            else:
                unique_txns[log.txn_id] = log

    # --- 4. BUSINESS METRICS (Split Current vs Previous) ---
    
    # Structure to hold aggregated data
    stats = {
        "curr": {"volume": 0.0, "count": 0, "pass": 0, "reject": 0, "hold": 0},
        "prev": {"volume": 0.0, "count": 0, "pass": 0, "reject": 0, "hold": 0}
    }
    
    # Specific containers for Current 24h Charts
    threat_counts = Counter()
    country_risk = defaultdict(float)
    hourly_vol = defaultdict(lambda: {"pass": 0.0, "block": 0.0})
    recent_blocks_display = []

    sorted_unique = sorted(unique_txns.values(), key=lambda x: x.decision_timestamp, reverse=True)

    for log in sorted_unique:
        # Standardize Time
        if log.decision_timestamp.tzinfo:
            ts_utc = log.decision_timestamp.astimezone(timezone.utc)
        else:
            ts_utc = log.decision_timestamp.replace(tzinfo=timezone.utc)
            
        # Parse Data
        data = {}
        try:
            if isinstance(log.features_snapshot, str): data = json.loads(log.features_snapshot)
            else: data = log.features_snapshot or {}
        except: data = {}

        amount = float(data.get("withdrawal_amount", 0.0))
        currency = data.get("withdraw_currency", "CRYPTO").upper()
        country = txn_country_map.get(str(log.txn_id), "Unknown")
        decision = (log.decision or "UNKNOWN").upper()

        # --- PERIOD ROUTING ---
        if ts_utc >= midpoint_time:
            # CURRENT 24H
            bucket = "curr"
            ts_key = ts_utc.strftime("%d %H:00")
            
            # Chart Data (Current Only)
            if decision == "PASS":
                hourly_vol[ts_key]["pass"] += amount
            else:
                hourly_vol[ts_key]["block"] += amount
                threat_counts[log.primary_threat or "Unknown"] += 1
                country_risk[country] += amount
                
                # Recent Table
                if len(recent_blocks_display) < 5:
                    src_label = "AI Agent" if "AI" in (log.decision_source or "") else "Rule Engine"
                    recent_blocks_display.append({
                        "time_str": ts_utc.strftime('%H:%M:%S'),
                        "user_code": log.user_code,
                        "currency": currency,
                        "country": country,
                        "source_label": src_label,
                        "decision": log.decision
                    })
        else:
            # PREVIOUS 24H
            bucket = "prev"

        # --- AGGREGATES ---
        stats[bucket]["volume"] += amount
        stats[bucket]["count"] += 1
        
        if decision == "PASS": stats[bucket]["pass"] += 1
        elif decision == "REJECT": stats[bucket]["reject"] += 1
        elif decision == "HOLD": stats[bucket]["hold"] += 1

    # --- 5. FINAL CALCULATIONS & TRENDS ---
    
    # KPI 1: Value Secured (Total Volume as requested)
    vol_curr = stats["curr"]["volume"]
    vol_prev = stats["prev"]["volume"]
    vol_trend = calculate_delta(vol_curr, vol_prev)
    
    # KPI 2: Transaction Count
    cnt_curr = stats["curr"]["count"]
    cnt_prev = stats["prev"]["count"]
    cnt_trend = calculate_delta(cnt_curr, cnt_prev)

    # KPI 3: Pass Rate
    pass_rate_curr = round((stats["curr"]["pass"] / cnt_curr * 100), 1) if cnt_curr else 0.0
    pass_rate_prev = round((stats["prev"]["pass"] / cnt_prev * 100), 1) if cnt_prev else 0.0
    pass_rate_trend = round(pass_rate_curr - pass_rate_prev, 1) # Absolute % diff for rates

    # Latency Averages (Current 24h)
    avg_rule = int(metrics_latency["rule_sum"] / metrics_latency["rule_count"]) if metrics_latency["rule_count"] else 0
    avg_ai = int(metrics_latency["ai_sum"] / metrics_latency["ai_count"]) if metrics_latency["ai_count"] else 0

    # KPI Object
    kpi = {
        "value_secured": f"${vol_curr:,.2f}", # Showing Total Volume now
        "value_trend": vol_trend,
        "txn_count": cnt_curr,
        "txn_trend": cnt_trend,
        "pass_rate": pass_rate_curr,
        "pass_trend": pass_rate_trend,
        "avg_rule_lat": f"{avg_rule}ms",
        "avg_ai_lat": f"{avg_ai}ms"
    }

    # --- CHARTS ---
    
    # 1. Comparative Decision Distribution
    decision_chart_data = {
        "labels": ["PASS", "HOLD", "REJECT"],
        "current": [stats["curr"]["pass"], stats["curr"]["hold"], stats["curr"]["reject"]],
        "previous": [stats["prev"]["pass"], stats["prev"]["hold"], stats["prev"]["reject"]]
    }

    # 2. Time Series (Latency & Volume - Current 24h)
    all_hours = sorted(set(hourly_latency.keys()) | set(hourly_vol.keys()))
    chart_rule_lat, chart_ai_lat, chart_vol_pass, chart_vol_block = [], [], [], []
    
    for h in all_hours:
        lats = hourly_latency[h]
        chart_rule_lat.append(int(sum(lats["rule"])/len(lats["rule"])) if lats["rule"] else 0)
        chart_ai_lat.append(int(sum(lats["ai"])/len(lats["ai"])) if lats["ai"] else 0)
        vols = hourly_vol[h]
        chart_vol_pass.append(vols["pass"])
        chart_vol_block.append(vols["block"])

    charts = {
        "threats": { "labels": list(threat_counts.keys()), "data": list(threat_counts.values()) },
        "countries": { "labels": list(country_risk.keys()), "data": list(country_risk.values()) },
        "volume": { "labels": all_hours, "pass": chart_vol_pass, "block": chart_vol_block },
        "latency": { "labels": all_hours, "rule": chart_rule_lat, "ai": chart_ai_lat },
        "decisions": decision_chart_data # New structure
    }

    return templates.TemplateResponse("dashboard/index.html", {
        "request": request,
        "kpi": kpi,
        "charts": charts,
        "ai_insight": ai_save_of_day,
        "recent_blocks": recent_blocks_display
    })
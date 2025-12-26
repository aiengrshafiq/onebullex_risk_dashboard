import json
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import get_db
# Ensure UserDevice is imported
from app.models.risk_tables import RiskWithdrawDecision, UserDevice

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/")
async def dashboard_index(request: Request, db: AsyncSession = Depends(get_db)):
    # 1. TIME FILTER: Strict Last 24 Hours
    cutoff_time = datetime.utcnow() - timedelta(hours=24)
    
    result = await db.execute(
        select(RiskWithdrawDecision)
        .where(RiskWithdrawDecision.decision_timestamp >= cutoff_time)
        .order_by(RiskWithdrawDecision.decision_timestamp.desc())
    )
    logs = result.scalars().all()

    # --- 2. FETCH COUNTRIES (Batch Fetch) ---
    txn_ids = []
    for log in logs:
        # txn_id might be string in JSON logs, typically purely numeric
        if log.txn_id and str(log.txn_id).isdigit():
            txn_ids.append(int(log.txn_id))
    
    txn_country_map = {}
    if txn_ids:
        # Dedupe IDs for query efficiency
        unique_ids = list(set(txn_ids))
        # Chunking in case of massive list is good practice, but for dashboard snapshot 1000 is fine
        device_res = await db.execute(
            select(UserDevice.event_id, UserDevice.country)
            .where(UserDevice.event_id.in_(unique_ids))
        )
        for row in device_res.all():
            if row[1]:
                txn_country_map[str(row[0])] = row[1]

    # --- 3. DEDUPLICATION (The "ChatGPT Fix") ---
    # We need two views of the data:
    # View A: Unique Transactions (For Volume, Pass Rate, Value Secured)
    # View B: Raw Activity (For Latency, Decision Mix Counts)
    
    unique_txns = {} # Key: txn_id -> Log Object
    
    # Raw Counters (View B)
    decision_mix = {
        "RULE_ENGINE_RULES": {"PASS": 0, "HOLD": 0, "REJECT": 0},
        "AI_AGENT_REVIEW":   {"PASS": 0, "HOLD": 0, "REJECT": 0}
    }
    hourly_latency = defaultdict(lambda: {"rule": [], "ai": []})
    
    # Latency Stats
    metrics_latency = {
        "rule_sum": 0, "rule_count": 0,
        "ai_sum": 0, "ai_count": 0
    }

    ai_save_of_day = None
    highest_ai_confidence = 0.0
    recent_blocks_display = []

    # --- LOOP 1: PROCESS RAW LOGS (Operational Stats) ---
    for log in logs:
        # Normalize Source
        source = "RULE_ENGINE_RULES"
        if "AI" in (log.decision_source or ""): source = "AI_AGENT_REVIEW"
        
        # 1. Decision Mix (Workload)
        decision = (log.decision or "UNKNOWN").upper()
        if decision in decision_mix[source]:
            decision_mix[source][decision] += 1
            
        # 2. Latency & Time Bucketing (Format: "Day Hour:00")
        ts_key = log.decision_timestamp.strftime("%d %H:00")
        lat = float(log.processing_time_ms or 0)
        
        if source == "RULE_ENGINE_RULES":
            metrics_latency["rule_sum"] += lat
            metrics_latency["rule_count"] += 1
            hourly_latency[ts_key]["rule"].append(lat)
        else:
            metrics_latency["ai_sum"] += lat
            metrics_latency["ai_count"] += 1
            hourly_latency[ts_key]["ai"].append(lat)

        # 3. AI Insight Logic (Keep looking through all logs)
        if source == "AI_AGENT_REVIEW" and decision == "REJECT":
            conf = float(log.confidence or 0)
            if conf > highest_ai_confidence:
                highest_ai_confidence = conf
                ai_save_of_day = log

        # 4. Build Unique Map (Latest timestamp wins per txn_id)
        if log.txn_id:
            curr = unique_txns.get(log.txn_id)
            if not curr or log.decision_timestamp > curr.decision_timestamp:
                unique_txns[log.txn_id] = log

    # --- LOOP 2: PROCESS UNIQUE TXNS (Business Metrics) ---
    metrics_biz = {
        "value_secured": 0.0,
        "pass_count": 0,
        "volume_processed": 0.0
    }
    
    threat_counts = Counter()
    country_risk = defaultdict(float)
    hourly_vol = defaultdict(lambda: {"pass": 0.0, "block": 0.0})

    # Sort logs for "Recent Blocks" table
    sorted_unique = sorted(unique_txns.values(), key=lambda x: x.decision_timestamp, reverse=True)

    for log in sorted_unique:
        # Parse Amount
        data = {}
        try:
            if isinstance(log.features_snapshot, str): data = json.loads(log.features_snapshot)
            else: data = log.features_snapshot or {}
        except: data = {}

        amount = float(data.get("withdrawal_amount", 0.0))
        currency = data.get("withdraw_currency", "CRYPTO").upper()
        country = txn_country_map.get(str(log.txn_id), "Unknown")
        
        ts_key = log.decision_timestamp.strftime("%d %H:00")
        
        # Pass Rate & Volume
        metrics_biz["volume_processed"] += amount
        
        if log.decision == "PASS":
            metrics_biz["pass_count"] += 1
            hourly_vol[ts_key]["pass"] += amount
        else:
            # HOLD or REJECT
            metrics_biz["value_secured"] += amount
            hourly_vol[ts_key]["block"] += amount
            threat_counts[log.primary_threat or "Unknown"] += 1
            country_risk[country] += amount
            
            # Populate Table (Only Blocked)
            if len(recent_blocks_display) < 5:
                # Label Source cleanly
                src_label = "AI Agent" if "AI" in (log.decision_source or "") else "Rule Engine"
                recent_blocks_display.append({
                    "time_str": log.decision_timestamp.strftime('%H:%M:%S'),
                    "user_code": log.user_code,
                    "currency": currency,
                    "country": country,
                    "source_label": src_label,
                    "decision": log.decision
                })

    # --- FINAL CALCULATIONS ---
    
    # 1. Averages
    avg_rule = int(metrics_latency["rule_sum"] / metrics_latency["rule_count"]) if metrics_latency["rule_count"] else 0
    avg_ai = int(metrics_latency["ai_sum"] / metrics_latency["ai_count"]) if metrics_latency["ai_count"] else 0
    
    total_unique = len(unique_txns)
    pass_rate = round((metrics_biz["pass_count"] / total_unique * 100), 1) if total_unique else 0.0

    # 2. Charts Construction
    # Get all unique hour keys from both latency and volume to ensure X-axis alignment
    all_hours = sorted(set(hourly_latency.keys()) | set(hourly_vol.keys()))
    
    chart_rule_lat = []
    chart_ai_lat = []
    chart_vol_pass = []
    chart_vol_block = []
    
    for h in all_hours:
        # Latency
        lats = hourly_latency[h]
        chart_rule_lat.append(int(sum(lats["rule"])/len(lats["rule"])) if lats["rule"] else 0)
        chart_ai_lat.append(int(sum(lats["ai"])/len(lats["ai"])) if lats["ai"] else 0)
        
        # Volume
        vols = hourly_vol[h]
        chart_vol_pass.append(vols["pass"])
        chart_vol_block.append(vols["block"])

    # 3. Context Payload
    kpi = {
        "secured_usd": f"${metrics_biz['value_secured']:,.2f}",
        "pass_rate": pass_rate,
        "avg_rule_lat": f"{avg_rule}ms",
        "avg_ai_lat": f"{avg_ai}ms"
    }

    charts = {
        "threats": { "labels": list(threat_counts.keys()), "data": list(threat_counts.values()) },
        "countries": { "labels": list(country_risk.keys()), "data": list(country_risk.values()) },
        "volume": { "labels": all_hours, "pass": chart_vol_pass, "block": chart_vol_block },
        "latency": { "labels": all_hours, "rule": chart_rule_lat, "ai": chart_ai_lat },
        "decisions": {
            "rule": [decision_mix["RULE_ENGINE_RULES"]["PASS"], decision_mix["RULE_ENGINE_RULES"]["HOLD"], decision_mix["RULE_ENGINE_RULES"]["REJECT"]],
            "ai": [decision_mix["AI_AGENT_REVIEW"]["PASS"], decision_mix["AI_AGENT_REVIEW"]["HOLD"], decision_mix["AI_AGENT_REVIEW"]["REJECT"]]
        }
    }

    return templates.TemplateResponse("dashboard/index.html", {
        "request": request,
        "kpi": kpi,
        "charts": charts,
        "ai_insight": ai_save_of_day,
        "recent_blocks": recent_blocks_display
    })
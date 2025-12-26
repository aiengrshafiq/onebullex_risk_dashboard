import json
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import get_db
from app.models.risk_tables import RiskWithdrawDecision

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

    # --- METRIC CONTAINERS ---
    total_txns = len(logs)
    
    # Hero Metrics
    metrics = {
        "value_secured": 0.0,
        "pass_count": 0,
        "ai_intervention_count": 0,
        "rule_latency_sum": 0,
        "rule_latency_count": 0,
        "ai_latency_sum": 0,
        "ai_latency_count": 0
    }
    
    # Chart Data Containers
    threat_counts = Counter()
    currency_risk = defaultdict(float) # Changed from Chain to Currency
    
    # Time Series Buckets (Hour -> Data)
    # Structure: "HH:00": { "rule_lat": [], "ai_lat": [], "pass_vol": 0, "block_vol": 0 }
    hourly_stats = defaultdict(lambda: {"rule_lats": [], "ai_lats": [], "pass_vol": 0.0, "block_vol": 0.0})
    
    # Decision Mix (Source -> Decision -> Count)
    decision_mix = {
        "RULE_ENGINE_RULES": {"PASS": 0, "HOLD": 0, "REJECT": 0},
        "AI_AGENT_REVIEW":   {"PASS": 0, "HOLD": 0, "REJECT": 0}
    }

    ai_save_of_day = None
    highest_ai_confidence = 0.0

    # --- PROCESSING LOOP ---
    for log in logs:
        # A. Parse Snapshot
        data = {}
        if log.features_snapshot:
            try:
                if isinstance(log.features_snapshot, str):
                    data = json.loads(log.features_snapshot)
                else:
                    data = log.features_snapshot
            except:
                data = {}

        amount = float(data.get("withdrawal_amount", 0.0))
        # Use Currency instead of Chain for better business value
        currency = data.get("withdraw_currency", "UNKNOWN").upper()
        
        # Normalize Decision Source Key (Database might vary slightly)
        source = log.decision_source
        if "RULE" in source: source = "RULE_ENGINE_RULES"
        elif "AI" in source: source = "AI_AGENT_REVIEW"
        else: source = "RULE_ENGINE_RULES" # Fallback

        # B. Decision Mix Counters
        decision = log.decision.upper()
        if decision in decision_mix[source]:
            decision_mix[source][decision] += 1

        # C. Latency & Time Series
        # Group by Hour (e.g., "14:00")
        ts_key = log.decision_timestamp.strftime("%H:00")
        
        latency = float(log.processing_time_ms or 0)

        if source == "RULE_ENGINE_RULES":
            metrics["rule_latency_sum"] += latency
            metrics["rule_latency_count"] += 1
            hourly_stats[ts_key]["rule_lats"].append(latency)
        else:
            metrics["ai_intervention_count"] += 1
            metrics["ai_latency_sum"] += latency
            metrics["ai_latency_count"] += 1
            hourly_stats[ts_key]["ai_lats"].append(latency)

        # D. Volume & Threat Logic
        if decision == "PASS":
            metrics["pass_count"] += 1
            hourly_stats[ts_key]["pass_vol"] += amount
        else:
            # HOLD or REJECT
            metrics["value_secured"] += amount
            hourly_stats[ts_key]["block_vol"] += amount
            threat_counts[log.primary_threat or "Unknown"] += 1
            currency_risk[currency] += amount # Aggregate by Currency

            # E. AI Insight Logic
            if source == "AI_AGENT_REVIEW" and decision == "REJECT":
                conf = float(log.confidence or 0)
                if conf > highest_ai_confidence:
                    highest_ai_confidence = conf
                    ai_save_of_day = log

    # --- FINAL CALCULATIONS ---
    
    # Averages
    avg_rule_lat = int(metrics["rule_latency_sum"] / metrics["rule_latency_count"]) if metrics["rule_latency_count"] else 0
    avg_ai_lat = int(metrics["ai_latency_sum"] / metrics["ai_latency_count"]) if metrics["ai_latency_count"] else 0
    
    pass_rate = 0.0
    if total_txns > 0:
        pass_rate = round((metrics["pass_count"] / total_txns) * 100, 1)

    # Prepare Chart Arrays (Sorted by Time)
    sorted_hours = sorted(hourly_stats.keys())
    
    # Calculate Avg Latency per hour for the chart
    chart_rule_lat = []
    chart_ai_lat = []
    
    for h in sorted_hours:
        stats = hourly_stats[h]
        # Avg Rule Latency for this hour
        if stats["rule_lats"]:
            chart_rule_lat.append(int(sum(stats["rule_lats"]) / len(stats["rule_lats"])))
        else:
            chart_rule_lat.append(0)
            
        # Avg AI Latency for this hour
        if stats["ai_lats"]:
            chart_ai_lat.append(int(sum(stats["ai_lats"]) / len(stats["ai_lats"])))
        else:
            chart_ai_lat.append(0)

    # KPI Context
    kpi = {
        "secured_usd": f"${metrics['value_secured']:,.2f}",
        "pass_rate": pass_rate,
        "avg_rule_lat": f"{avg_rule_lat}ms",
        "avg_ai_lat": f"{avg_ai_lat}ms"
    }

    # Chart Context
    charts = {
        "threats": {
            "labels": list(threat_counts.keys()),
            "data": list(threat_counts.values())
        },
        "currencies": { # Renamed from Chains
            "labels": list(currency_risk.keys()),
            "data": list(currency_risk.values())
        },
        "volume": {
            "labels": sorted_hours,
            "pass": [hourly_stats[h]["pass_vol"] for h in sorted_hours],
            "block": [hourly_stats[h]["block_vol"] for h in sorted_hours]
        },
        "latency": {
            "labels": sorted_hours,
            "rule": chart_rule_lat,
            "ai": chart_ai_lat
        },
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
        "recent_blocks": [l for l in logs if l.decision != 'PASS'][:5]
    })
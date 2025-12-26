import json
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc

from app.core.database import get_db
from app.models.risk_tables import RiskWithdrawDecision, RiskRule

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/")
async def dashboard_index(request: Request, db: AsyncSession = Depends(get_db)):
    # 1. Fetch recent Decision Logs (Limit 1000 for snapshot performance)
    result = await db.execute(
        select(RiskWithdrawDecision)
        .order_by(RiskWithdrawDecision.decision_timestamp.desc())
        .limit(1000)
    )
    logs = result.scalars().all()

    # --- METRIC CALCULATIONS ---
    total_txns = len(logs)
    
    # Initialize Counters
    metrics = {
        "value_secured": 0.0,      # USD saved (Held/Rejected)
        "pass_count": 0,
        "ai_intervention": 0,
        "rule_latency_sum": 0,     # Sum of latency for RULES only
        "rule_latency_count": 0,   # Count of rule-based decisions
        "volume_processed": 0.0
    }
    
    threat_counts = Counter()
    chain_risk = defaultdict(float)
    hourly_vol = defaultdict(lambda: {"pass": 0.0, "block": 0.0})
    
    ai_save_of_day = None
    highest_ai_confidence = 0.0

    for log in logs:
        # A. Parse Feature Snapshot safely
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
        chain = data.get("chain", "UNKNOWN")
        
        # B. General Volume Metrics
        metrics["volume_processed"] += amount

        # C. Latency Calculation (Strictly EXCLUDE AI)
        if log.decision_source != 'AI_AGENT_REVIEW':
            metrics["rule_latency_sum"] += float(log.processing_time_ms or 0)
            metrics["rule_latency_count"] += 1

        # D. Decision Logic
        if log.decision == "PASS":
            metrics["pass_count"] += 1
            ts_key = log.decision_timestamp.strftime("%H:00")
            hourly_vol[ts_key]["pass"] += amount
        else:
            # HOLD or REJECT = Value Secured
            metrics["value_secured"] += amount
            threat_counts[log.primary_threat or "Unknown"] += 1
            chain_risk[chain] += amount
            
            ts_key = log.decision_timestamp.strftime("%H:00")
            hourly_vol[ts_key]["block"] += amount

        # E. AI Specific Stats
        if log.decision_source == "AI_AGENT_REVIEW":
            metrics["ai_intervention"] += 1
            
            # Logic for "Save of the Day":
            # Must be AI source + REJECT decision. We pick the one with highest confidence.
            if log.decision == "REJECT":
                conf = float(log.confidence or 0)
                if conf > highest_ai_confidence:
                    highest_ai_confidence = conf
                    ai_save_of_day = log

    # --- FINAL AGGREGATIONS ---
    
    # Calculate Average Latency (Prevent division by zero)
    avg_lat = 0
    if metrics["rule_latency_count"] > 0:
        avg_lat = int(metrics["rule_latency_sum"] / metrics["rule_latency_count"])

    # Calculate Rates
    pass_rate = 0.0
    ai_rate = 0.0
    if total_txns > 0:
        pass_rate = round((metrics["pass_count"] / total_txns) * 100, 1)
        ai_rate = round((metrics["ai_intervention"] / total_txns) * 100, 1)

    # 1. KPI Cards Context
    kpi = {
        "secured_usd": f"${metrics['value_secured']:,.2f}",
        "pass_rate": pass_rate,
        "avg_latency": f"{avg_lat}ms",
        "ai_rate": ai_rate
    }

    # 2. Charts Data Structure
    sorted_hours = sorted(hourly_vol.keys())
    
    charts = {
        "threats": {
            "labels": list(threat_counts.keys()),
            "data": list(threat_counts.values())
        },
        "chains": {
            "labels": list(chain_risk.keys()),
            "data": [v for v in chain_risk.values()]
        },
        "volume": {
            "labels": sorted_hours,
            "pass": [hourly_vol[h]["pass"] for h in sorted_hours],
            "block": [hourly_vol[h]["block"] for h in sorted_hours]
        }
    }

    return templates.TemplateResponse("dashboard/index.html", {
        "request": request,
        "kpi": kpi,
        "charts": charts,
        "ai_insight": ai_save_of_day,
        "recent_blocks": [l for l in logs if l.decision != 'PASS'][:5]
    })
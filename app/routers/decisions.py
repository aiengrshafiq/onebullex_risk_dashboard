from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, or_, func
from app.core.database import get_db
from app.models.risk_tables import RiskWithdrawDecision
import math

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/decisions")
async def view_decisions(
    request: Request, 
    page: int = 1, 
    q: str = "", 
    source: str = "ALL",
    db: AsyncSession = Depends(get_db)
):
    PAGE_SIZE = 15
    offset = (page - 1) * PAGE_SIZE
    
    # Base Query
    query = select(RiskWithdrawDecision)
    
    # Filters
    filters = []
    if q:
        filters.append(or_(
            RiskWithdrawDecision.user_code.ilike(f"%{q}%"),
            RiskWithdrawDecision.txn_id.ilike(f"%{q}%")
        ))
    
    if source != "ALL":
        filters.append(RiskWithdrawDecision.decision_source == source)
        
    if filters:
        query = query.where(*filters)
        
    # Count (Simple estimate for performance)
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total_records = count_result.scalar() or 0
    total_pages = math.ceil(total_records / PAGE_SIZE)
    
    # Fetch Data
    query = query.order_by(RiskWithdrawDecision.decision_timestamp.desc()).offset(offset).limit(PAGE_SIZE)
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return templates.TemplateResponse("risk/decisions_list.html", {
        "request": request,
        "logs": logs,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "source": source,
        "total_records": total_records
    })

@router.get("/decisions/{log_id}")
async def get_decision_details(log_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RiskWithdrawDecision).where(RiskWithdrawDecision.log_id == log_id))
    log = result.scalars().first()
    
    if not log:
        raise HTTPException(status_code=404, detail="Log entry not found")
    
    # Convert to Dict
    data = {c.name: getattr(log, c.name) for c in log.__table__.columns}
    
    # Handle Date Serialization
    if data['decision_timestamp']:
        data['decision_timestamp'] = data['decision_timestamp'].isoformat()
        
    return data
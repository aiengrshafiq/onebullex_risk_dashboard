from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, or_, func, text
from app.core.database import get_db
from app.models.risk_tables import RiskFeature
import math

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/risk-features")
async def view_risk_features(
    request: Request, 
    page: int = 1, 
    q: str = "", 
    db: AsyncSession = Depends(get_db)
):
    PAGE_SIZE = 20
    offset = (page - 1) * PAGE_SIZE
    
    # Base Query
    query = select(RiskFeature)
    
    # Search Filter
    if q:
        query = query.where(
            or_(
                RiskFeature.user_code.ilike(f"%{q}%"),
                RiskFeature.txn_id.ilike(f"%{q}%"),
                RiskFeature.destination_address.ilike(f"%{q}%")
            )
        )
    
    # Total Count (Optimized for Hologres: simple count)
    # Note: In massive tables, count(*) can be slow. 
    # For this implementation we assume < 100M rows or fast Hologres indexing.
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total_records = count_result.scalar()
    total_pages = math.ceil(total_records / PAGE_SIZE)
    
    # Data Query
    query = query.order_by(RiskFeature.update_time.desc()).offset(offset).limit(PAGE_SIZE)
    result = await db.execute(query)
    features = result.scalars().all()
    
    return templates.TemplateResponse("risk/features_list.html", {
        "request": request,
        "features": features,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "total_records": total_records
    })

@router.get("/risk-features/details")
async def get_feature_details(user_code: str, txn_id: str, db: AsyncSession = Depends(get_db)):
    # Fetch specific record
    query = select(RiskFeature).where(
        (RiskFeature.user_code == user_code) & 
        (RiskFeature.txn_id == txn_id)
    )
    result = await db.execute(query)
    record = result.scalars().first()
    
    if not record:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    # Convert SQLAlchemy object to Dict dynamically to show ALL columns
    # This avoids hardcoding 50 fields in HTML
    data_dict = {c.name: getattr(record, c.name) for c in record.__table__.columns}
    
    # Handle dates for JSON serialization
    for k, v in data_dict.items():
        if hasattr(v, 'isoformat'):
            data_dict[k] = v.isoformat()
            
    return data_dict
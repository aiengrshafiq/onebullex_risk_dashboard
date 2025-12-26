from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import get_db
from app.models.risk_tables import RiskWhitelistUser, RiskWhitelistAddress, RiskGreylist
from app.schemas.lists import WhitelistUserCreate, WhitelistAddressCreate, GreylistCreate

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# ==========================================
# 1. USER WHITELIST MANAGEMENT
# ==========================================
@router.get("/whitelist/users")
async def view_whitelist_users(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RiskWhitelistUser).order_by(RiskWhitelistUser.created_at.desc()))
    return templates.TemplateResponse("lists/whitelist_users.html", {"request": request, "users": result.scalars().all()})

@router.post("/whitelist/users/add")
async def add_whitelist_user(item: WhitelistUserCreate, db: AsyncSession = Depends(get_db)):
    # Check if exists
    exists = await db.get(RiskWhitelistUser, item.user_code)
    if exists:
        raise HTTPException(status_code=400, detail="User Code already whitelisted")
    
    new_entry = RiskWhitelistUser(**item.dict())
    db.add(new_entry)
    try:
        await db.commit()
        return {"status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 2. ADDRESS WHITELIST MANAGEMENT
# ==========================================
@router.get("/whitelist/addresses")
async def view_whitelist_addresses(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RiskWhitelistAddress).order_by(RiskWhitelistAddress.created_at.desc()))
    return templates.TemplateResponse("lists/whitelist_addresses.html", {"request": request, "addresses": result.scalars().all()})

@router.post("/whitelist/addresses/add")
async def add_whitelist_address(item: WhitelistAddressCreate, db: AsyncSession = Depends(get_db)):
    exists = await db.get(RiskWhitelistAddress, item.destination_address)
    if exists:
        raise HTTPException(status_code=400, detail="Address already whitelisted")
        
    new_entry = RiskWhitelistAddress(**item.dict())
    db.add(new_entry)
    try:
        await db.commit()
        return {"status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 3. GREYLIST MANAGEMENT
# ==========================================
@router.get("/greylist")
async def view_greylist(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RiskGreylist).order_by(RiskGreylist.created_at.desc()))
    return templates.TemplateResponse("lists/greylist.html", {"request": request, "items": result.scalars().all()})

@router.post("/greylist/add")
async def add_greylist(item: GreylistCreate, db: AsyncSession = Depends(get_db)):
    # Check composite key
    result = await db.execute(select(RiskGreylist).where(
        (RiskGreylist.entity_value == item.entity_value) & 
        (RiskGreylist.entity_type == item.entity_type)
    ))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Entity already greylisted")

    new_entry = RiskGreylist(**item.dict())
    db.add(new_entry)
    try:
        await db.commit()
        return {"status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 1. USER WHITELIST - UPDATE & DELETE
# ==========================================
# FIX: Added :path to capture full string ID properly
@router.put("/whitelist/users/{user_code:path}")
async def update_whitelist_user(user_code: str, item: WhitelistUserCreate, db: AsyncSession = Depends(get_db)):
    # Fetch
    entry = await db.get(RiskWhitelistUser, user_code)
    if not entry:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update fields
    entry.description = item.description
    entry.expires_at = item.expires_at
    entry.status = item.status
    
    await db.commit()
    return {"status": "success"}

# FIX: Added :path to capture full string ID properly
@router.delete("/whitelist/users/{user_code:path}")
async def delete_whitelist_user(user_code: str, db: AsyncSession = Depends(get_db)):
    entry = await db.get(RiskWhitelistUser, user_code)
    if not entry:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.delete(entry)
    await db.commit()
    return {"status": "success"}

# ==========================================
# 2. ADDRESS WHITELIST - UPDATE & DELETE
# ==========================================
# FIX: Added :path because crypto addresses can contain special characters
@router.put("/whitelist/addresses/{address:path}")
async def update_whitelist_address(address: str, item: WhitelistAddressCreate, db: AsyncSession = Depends(get_db)):
    entry = await db.get(RiskWhitelistAddress, address)
    if not entry:
        raise HTTPException(status_code=404, detail="Address not found")
    
    entry.chain = item.chain
    entry.description = item.description
    entry.status = item.status
    
    await db.commit()
    return {"status": "success"}

@router.delete("/whitelist/addresses/{address:path}")
async def delete_whitelist_address(address: str, db: AsyncSession = Depends(get_db)):
    entry = await db.get(RiskWhitelistAddress, address)
    if not entry:
        raise HTTPException(status_code=404, detail="Address not found")
    
    await db.delete(entry)
    await db.commit()
    return {"status": "success"}

# ==========================================
# 3. GREYLIST - UPDATE & DELETE
# ==========================================
@router.put("/greylist/update")
async def update_greylist(item: GreylistCreate, db: AsyncSession = Depends(get_db)):
    # Composite Key Lookup
    query = select(RiskGreylist).where(
        (RiskGreylist.entity_value == item.entity_value) & 
        (RiskGreylist.entity_type == item.entity_type)
    )
    result = await db.execute(query)
    entry = result.scalars().first()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    entry.reason = item.reason
    entry.expires_at = item.expires_at
    entry.status = item.status
    
    await db.commit()
    return {"status": "success"}

@router.delete("/greylist/delete")
async def delete_greylist(entity_value: str, entity_type: str, db: AsyncSession = Depends(get_db)):
    query = select(RiskGreylist).where(
        (RiskGreylist.entity_value == entity_value) & 
        (RiskGreylist.entity_type == entity_type)
    )
    result = await db.execute(query)
    entry = result.scalars().first()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    await db.delete(entry)
    await db.commit()
    return {"status": "success"}
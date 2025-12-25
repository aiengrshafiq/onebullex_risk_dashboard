from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import get_db
from app.models.risk_tables import (
    RiskBlacklistUser, RiskBlacklistIP, RiskBlacklistEmailDomain, RiskBlacklistAddress
)
from app.schemas.blacklist import (
    BlacklistUserCreate, BlacklistIPCreate, BlacklistDomainCreate, BlacklistAddressCreate
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# ================= MAIN DASHBOARD VIEW =================
@router.get("/blacklist")
async def view_blacklist_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    # Fetch all lists in parallel (conceptually) for the dashboard
    users = await db.execute(select(RiskBlacklistUser).order_by(RiskBlacklistUser.created_at.desc()))
    ips = await db.execute(select(RiskBlacklistIP).order_by(RiskBlacklistIP.created_at.desc()))
    domains = await db.execute(select(RiskBlacklistEmailDomain).order_by(RiskBlacklistEmailDomain.created_at.desc()))
    addresses = await db.execute(select(RiskBlacklistAddress).order_by(RiskBlacklistAddress.created_at.desc()))

    return templates.TemplateResponse("lists/blacklist.html", {
        "request": request,
        "users": users.scalars().all(),
        "ips": ips.scalars().all(),
        "domains": domains.scalars().all(),
        "addresses": addresses.scalars().all()
    })

# ================= 1. BLACKLIST USER =================
@router.post("/blacklist/user")
async def add_bl_user(item: BlacklistUserCreate, db: AsyncSession = Depends(get_db)):
    if await db.get(RiskBlacklistUser, item.user_code):
        raise HTTPException(400, "User already blacklisted")
    db.add(RiskBlacklistUser(**item.dict()))
    await db.commit()
    return {"status": "success"}

@router.put("/blacklist/user/{user_code}")
async def update_bl_user(user_code: str, item: BlacklistUserCreate, db: AsyncSession = Depends(get_db)):
    entry = await db.get(RiskBlacklistUser, user_code)
    if not entry: raise HTTPException(404, "Not found")
    entry.reason = item.reason
    entry.expires_at = item.expires_at
    entry.status = item.status
    await db.commit()
    return {"status": "success"}

@router.delete("/blacklist/user/{user_code}")
async def delete_bl_user(user_code: str, db: AsyncSession = Depends(get_db)):
    entry = await db.get(RiskBlacklistUser, user_code)
    if not entry: raise HTTPException(404, "Not found")
    await db.delete(entry)
    await db.commit()
    return {"status": "success"}

# ================= 2. BLACKLIST IP =================
@router.post("/blacklist/ip")
async def add_bl_ip(item: BlacklistIPCreate, db: AsyncSession = Depends(get_db)):
    if await db.get(RiskBlacklistIP, item.ip_address):
        raise HTTPException(400, "IP already blacklisted")
    db.add(RiskBlacklistIP(**item.dict()))
    await db.commit()
    return {"status": "success"}

@router.put("/blacklist/ip/{ip_address}")
async def update_bl_ip(ip_address: str, item: BlacklistIPCreate, db: AsyncSession = Depends(get_db)):
    entry = await db.get(RiskBlacklistIP, ip_address)
    if not entry: raise HTTPException(404, "Not found")
    entry.reason = item.reason
    entry.expires_at = item.expires_at
    entry.status = item.status
    await db.commit()
    return {"status": "success"}

@router.delete("/blacklist/ip/{ip_address}")
async def delete_bl_ip(ip_address: str, db: AsyncSession = Depends(get_db)):
    entry = await db.get(RiskBlacklistIP, ip_address)
    if not entry: raise HTTPException(404, "Not found")
    await db.delete(entry)
    await db.commit()
    return {"status": "success"}

# ================= 3. BLACKLIST DOMAIN =================
@router.post("/blacklist/domain")
async def add_bl_domain(item: BlacklistDomainCreate, db: AsyncSession = Depends(get_db)):
    if await db.get(RiskBlacklistEmailDomain, item.email_domain):
        raise HTTPException(400, "Domain already blacklisted")
    db.add(RiskBlacklistEmailDomain(**item.dict()))
    await db.commit()
    return {"status": "success"}

@router.put("/blacklist/domain/{domain}")
async def update_bl_domain(domain: str, item: BlacklistDomainCreate, db: AsyncSession = Depends(get_db)):
    entry = await db.get(RiskBlacklistEmailDomain, domain)
    if not entry: raise HTTPException(404, "Not found")
    entry.reason = item.reason
    entry.expires_at = item.expires_at
    entry.status = item.status
    await db.commit()
    return {"status": "success"}

@router.delete("/blacklist/domain/{domain}")
async def delete_bl_domain(domain: str, db: AsyncSession = Depends(get_db)):
    entry = await db.get(RiskBlacklistEmailDomain, domain)
    if not entry: raise HTTPException(404, "Not found")
    await db.delete(entry)
    await db.commit()
    return {"status": "success"}

# ================= 4. BLACKLIST ADDRESS =================
@router.post("/blacklist/address")
async def add_bl_address(item: BlacklistAddressCreate, db: AsyncSession = Depends(get_db)):
    if await db.get(RiskBlacklistAddress, item.destination_address):
        raise HTTPException(400, "Address already blacklisted")
    db.add(RiskBlacklistAddress(**item.dict()))
    await db.commit()
    return {"status": "success"}

@router.put("/blacklist/address/{address}")
async def update_bl_address(address: str, item: BlacklistAddressCreate, db: AsyncSession = Depends(get_db)):
    entry = await db.get(RiskBlacklistAddress, address)
    if not entry: raise HTTPException(404, "Not found")
    entry.chain = item.chain
    entry.reason = item.reason
    entry.expires_at = item.expires_at
    entry.status = item.status
    await db.commit()
    return {"status": "success"}

@router.delete("/blacklist/address/{address}")
async def delete_bl_address(address: str, db: AsyncSession = Depends(get_db)):
    entry = await db.get(RiskBlacklistAddress, address)
    if not entry: raise HTTPException(404, "Not found")
    await db.delete(entry)
    await db.commit()
    return {"status": "success"}
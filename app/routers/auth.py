from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.models.users import User
from app.core.security import verify_password, get_password_hash, create_access_token

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# --- REGISTER ---
@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request})

@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    # Check existing
    result = await db.execute(select(User).where(User.username == username))
    if result.scalars().first():
        return templates.TemplateResponse("auth/register.html", {"request": request, "error": "Username already exists"})
    
    new_user = User(
        username=username, 
        email=email, 
        password_hash=get_password_hash(password),
        role="analyst"
    )
    db.add(new_user)
    await db.commit()
    return RedirectResponse(url="/login", status_code=303)

# --- LOGIN ---
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})

@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    # Find user
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()

    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("auth/login.html", {"request": request, "error": "Invalid credentials"})
    
    # Create Token
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    
    # Set Cookie and Redirect
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response

# --- LOGOUT ---
@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response


# ================= USER MANAGEMENT =================

@router.get("/users")
async def list_users(request: Request, db: AsyncSession = Depends(get_db)):
    """List all registered users."""
    # Fetch users ordered by creation date
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    
    return templates.TemplateResponse("auth/users_list.html", {
        "request": request, 
        "users": users
    })

@router.delete("/users/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a specific user by ID."""
    # 1. Find the user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # 2. Delete
    await db.delete(user)
    await db.commit()
    
    return {"status": "success", "message": "User deleted"}
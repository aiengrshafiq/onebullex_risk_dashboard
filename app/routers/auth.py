from typing import Optional
from jose import jwt, JWTError
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.models.users import User
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings

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
    # Note: 'Bearer ' prefix is standard but sometimes complicates parsing. 
    # We will handle stripping it in get_current_user below.
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
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    
    return templates.TemplateResponse("auth/users_list.html", {
        "request": request, 
        "users": users
    })

@router.delete("/users/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a specific user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    await db.delete(user)
    await db.commit()
    
    return {"status": "success", "message": "User deleted"}

# ========================================================
#  NEW: AUTHENTICATION DEPENDENCY (get_current_user)
# ========================================================
async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """
    Dependency that reads the cookie, decodes JWT, and returns the User object.
    If not authenticated, raises 401.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Remove 'Bearer ' prefix if present
    if token.startswith("Bearer "):
        token = token.split(" ")[1]

    try:
        # Decode JWT
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    # Fetch User from DB
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
        
    return user
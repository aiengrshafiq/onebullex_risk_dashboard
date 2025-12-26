from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from app.routers import auth, risk_rules, lists, blacklist, features, decisions
# We will import dashboard router later

app = FastAPI(title="Phalanx Console")

# Mount Static Files (CSS/JS)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include Routers
app.include_router(auth.router)
app.include_router(risk_rules.router)
app.include_router(lists.router)
app.include_router(blacklist.router)
app.include_router(features.router)
app.include_router(decisions.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}

    
@app.get("/")
async def root():
    return RedirectResponse(url="/login")

# Temporary Dashboard Route to test login
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory="app/templates")

@app.get("/dashboard")
async def dashboard_home(request: Request):
    # In real app, we check cookie/token here
    return templates.TemplateResponse("dashboard/index.html", {"request": request})
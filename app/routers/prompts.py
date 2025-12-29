import json
import urllib.request
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, update

from app.core.database import get_db
from app.models.risk_tables import AIPrompt
from app.core.config import settings # Assuming you have this

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# --- SCHEMAS ---
class PromptUpdate(BaseModel):
    prompt_key: str
    prompt_text: str
    change_reason: str

class PromptTest(BaseModel):
    prompt_text: str
    test_json: str # User pastes a JSON case here

# --- ROUTES ---

@router.get("/")
async def prompt_manager_ui(request: Request, db: AsyncSession = Depends(get_db)):
    # Get the latest active prompt for the main key
    result = await db.execute(
        select(AIPrompt).where(
            AIPrompt.prompt_key == 'RISK_ANALYSIS_MAIN',
            AIPrompt.is_active == True
        )
    )
    active_prompt = result.scalars().first()
    
    # Get history
    history_res = await db.execute(
        select(AIPrompt)
        .where(AIPrompt.prompt_key == 'RISK_ANALYSIS_MAIN')
        .order_by(desc(AIPrompt.version))
        .limit(10)
    )
    history = history_res.scalars().all()

    return templates.TemplateResponse("prompts/index.html", {
        "request": request,
        "active_prompt": active_prompt,
        "history": history
    })

@router.post("/test")
async def test_prompt(payload: PromptTest):
    """
    Sends a dry-run request to Gemini to validate the prompt + JSON.
    """
    try:
        # 1. Parse the test JSON to ensure it's valid
        case_data = json.loads(payload.test_json)
        case_str = json.dumps(case_data, indent=2)
        
        # 2. Construct Full Prompt
        full_text = f"{payload.prompt_text}\n\nCase JSON:\n{case_str}"
        
        # 3. Call Gemini API (Using standard urllib as you requested)
        api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-pro:generateContent?key={settings.GEMINI_API_KEY}"
        
        req_body = {"contents": [{"parts": [{"text": full_text}]}]}
        data = json.dumps(req_body).encode("utf-8")
        
        req = urllib.request.Request(
            api_url, data=data, headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            
        # 4. Extract Text
        try:
            model_reply = res_json['candidates'][0]['content']['parts'][0]['text']
            # Clean formatting code fences if present
            if "```json" in model_reply:
                model_reply = model_reply.replace("```json", "").replace("```", "")
            return {"status": "success", "reply": model_reply}
        except Exception as e:
            return {"status": "error", "reply": f"Raw Gemini response invalid: {str(e)}", "raw": res_json}

    except json.JSONDecodeError:
        return {"status": "error", "reply": "Invalid Test Data JSON format."}
    except Exception as e:
        return {"status": "error", "reply": str(e)}

@router.post("/publish")
async def publish_prompt(payload: PromptUpdate, db: AsyncSession = Depends(get_db)):
    # 1. Find current max version
    res = await db.execute(
        select(AIPrompt.version)
        .where(AIPrompt.prompt_key == payload.prompt_key)
        .order_by(desc(AIPrompt.version))
        .limit(1)
    )
    curr_version = res.scalars().first() or 0
    new_version = curr_version + 1

    # 2. Deactivate old active prompts for this key
    await db.execute(
        update(AIPrompt)
        .where(AIPrompt.prompt_key == payload.prompt_key)
        .values(is_active=False)
    )

    # 3. Insert new Active Prompt
    new_prompt = AIPrompt(
        prompt_key=payload.prompt_key,
        version=new_version,
        prompt_text=payload.prompt_text,
        is_active=True,
        change_reason=payload.change_reason
    )
    db.add(new_prompt)
    await db.commit()
    
    return {"status": "success", "version": new_version}
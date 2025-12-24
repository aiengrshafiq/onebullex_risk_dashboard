from fastapi import APIRouter, Depends, Request, HTTPExcepti
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import get_db
from app.models.risk_tables import RiskRule
from app.schemas.risk import RiskRuleCreate

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/risk-rules")
async def view_risk_rules(request: Request, db: AsyncSession = Depends(get_db)):
    # Fetch all rules ordered by Priority (descending)
    result = await db.execute(select(RiskRule).order_by(RiskRule.priority.desc()))
    rules = result.scalars().all()
    
    return templates.TemplateResponse("risk/rules_list.html", {
        "request": request, 
        "rules": rules
    })

# --- NEW: ADD RULE ENDPOINT ---
@router.post("/risk-rules/add")
async def create_risk_rule(rule: RiskRuleCreate, db: AsyncSession = Depends(get_db)):
    try:
        new_rule = RiskRule(
            rule_name=rule.rule_name,
            logic_expression=rule.logic_expression,
            action=rule.action,
            narrative=rule.narrative,
            priority=rule.priority,
            status=rule.status
        )
        db.add(new_rule)
        await db.commit()
        await db.refresh(new_rule)
        return {"status": "success", "message": "Rule created successfully", "rule_id": new_rule.rule_id}
    except Exception as e:
        await db.rollback()
        # Log the error in a real app
        raise HTTPException(status_code=500, detail=str(e))

# --- NEW: UPDATE RULE ENDPOINT ---
@router.put("/risk-rules/{rule_id}")
async def update_risk_rule(
    rule_id: int, 
    rule_update: RiskRuleCreate, 
    db: AsyncSession = Depends(get_db)
):
    # 1. Fetch existing rule
    result = await db.execute(select(RiskRule).where(RiskRule.rule_id == rule_id))
    existing_rule = result.scalars().first()

    if not existing_rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # 2. Update fields
    existing_rule.rule_name = rule_update.rule_name
    existing_rule.logic_expression = rule_update.logic_expression
    existing_rule.action = rule_update.action
    existing_rule.narrative = rule_update.narrative
    existing_rule.priority = rule_update.priority
    existing_rule.status = rule_update.status

    # 3. Commit
    try:
        await db.commit()
        return {"status": "success", "message": "Rule updated successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import get_db
from app.models.risk_tables import RiskRule
from app.schemas.risk import RiskRuleCreate
from sqlalchemy import func
import ast


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# --- 1. Helper: AST Validator (Derived from your provided code) ---
_ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.UnaryOp, ast.BinOp, ast.Compare,
    ast.Name, ast.Load, ast.Constant, ast.And, ast.Or, ast.Not,
    ast.UAdd, ast.USub, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
    ast.Eq, ast.NotEq, ast.Gt, ast.GtE, ast.Lt, ast.LtE,
)

def validate_logic_expression(expr: str):
    """
    Parses string to AST and checks if it is a safe, valid Python expression.
    Returns (True, None) or (False, error_message).
    """
    expr = (expr or "").replace("\n", " ").strip()
    if not expr:
        return False, "Expression cannot be empty."
    
    try:
        # 1. Check Syntax
        tree = ast.parse(expr, mode="eval")
        
        # 2. Check Security/Allowed Nodes
        for n in ast.walk(tree):
            if not isinstance(n, _ALLOWED_NODES):
                return False, f"Security Block: Disallowed logic element '{type(n).__name__}'"
                
        return True, None
    except SyntaxError as e:
        return False, f"Syntax Error: {e.msg} at offset {e.offset}"
    except Exception as e:
        return False, str(e)


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
        # Validate Logic
        is_valid, error_msg = validate_logic_expression(rule.logic_expression)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Invalid Logic Expression: {error_msg}")
        # 1. Get the current maximum rule_id
        # We use coalesce to handle the case where the table is empty (returns 0)
        query = select(func.max(RiskRule.rule_id))
        result = await db.execute(query)
        max_id = result.scalar() or 0
        
        # 2. Calculate next ID
        next_id = max_id + 1
        # 3. Create the rule with the manual ID
        new_rule = RiskRule(
            rule_id=next_id,
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

     # Validate Logic
    is_valid, error_msg = validate_logic_expression(rule_update.logic_expression)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid Logic Expression: {error_msg}")
        
   
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
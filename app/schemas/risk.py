from pydantic import BaseModel
from typing import Optional

class RiskRuleCreate(BaseModel):
    rule_name: str
    logic_expression: str
    action: str
    narrative: str
    priority: int = 10
    status: str = "ACTIVE"
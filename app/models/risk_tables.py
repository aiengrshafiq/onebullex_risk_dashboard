from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.core.database import Base

class RiskRule(Base):
    __tablename__ = "risk_rules"
    __table_args__ = {"schema": "rt"}  # Explicitly targeting the 'rt' schema

    rule_id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(Text, nullable=False)
    logic_expression = Column(Text, nullable=False)
    action = Column(Text, nullable=False)  # e.g., 'HOLD', 'PASS'
    narrative = Column(Text, nullable=False)
    priority = Column(Integer, default=10)
    status = Column(Text, default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
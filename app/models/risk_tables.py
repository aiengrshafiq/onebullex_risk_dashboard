
from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.core.database import Base
from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy import Boolean, Float, Double
from sqlalchemy.dialects.postgresql import JSONB

from sqlalchemy import BigInteger, Numeric


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


# --- WHITELIST USER ---
class RiskWhitelistUser(Base):
    __tablename__ = "risk_whitelist_user"
    __table_args__ = {"schema": "rt"}

    user_code = Column(String, primary_key=True, index=True)
    description = Column(Text)
    status = Column(Text, default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

# --- WHITELIST ADDRESS ---
class RiskWhitelistAddress(Base):
    __tablename__ = "risk_whitelist_address"
    __table_args__ = {"schema": "rt"}

    destination_address = Column(String, primary_key=True, index=True)
    chain = Column(String)
    description = Column(Text)
    status = Column(Text, default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

# --- GREYLIST ---
class RiskGreylist(Base):
    __tablename__ = "risk_greylist"
    __table_args__ = {"schema": "rt"}

    # Composite Primary Key
    entity_value = Column(String, primary_key=True)
    entity_type = Column(String, primary_key=True) # e.g., IP, EMAIL, USER_CODE
    
    reason = Column(Text)
    status = Column(Text, default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)


# ================= BLACKLIST MODELS =================

class RiskBlacklistUser(Base):
    __tablename__ = "risk_blacklist_user"
    __table_args__ = {"schema": "rt"}

    user_code = Column(String, primary_key=True, index=True)
    reason = Column(Text)
    status = Column(Text, default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

class RiskBlacklistIP(Base):
    __tablename__ = "risk_blacklist_ip"
    __table_args__ = {"schema": "rt"}

    ip_address = Column(String, primary_key=True, index=True)
    reason = Column(Text)
    status = Column(Text, default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

class RiskBlacklistEmailDomain(Base):
    __tablename__ = "risk_blacklist_emaildomain"
    __table_args__ = {"schema": "rt"}

    email_domain = Column(String, primary_key=True, index=True)
    reason = Column(Text)
    status = Column(Text, default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

class RiskBlacklistAddress(Base):
    __tablename__ = "risk_blacklist_address"
    __table_args__ = {"schema": "rt"}

    destination_address = Column(String, primary_key=True, index=True)
    chain = Column(String)
    reason = Column(Text)
    status = Column(Text, default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)


# ================= RISK FEATURES (Big Data Table) =================
class RiskFeature(Base):
    __tablename__ = "risk_features"
    __table_args__ = {"schema": "rt"}

    # Composite Primary Key
    user_code = Column(String, primary_key=True)
    txn_id = Column(String, primary_key=True)
    
    # Key Financials
    withdrawal_amount = Column(Double)
    withdraw_currency = Column(String, name="withdraw_currency") # Mapped name
    chain = Column(String)
    pnl_amount = Column(Double)
    total_balance_sum = Column(Double)
    
    # Risk Scores & Flags
    session_risk_score = Column(Integer)
    source_risk_score = Column(Integer)
    is_sanctioned = Column(Boolean)
    sanctions_status = Column(String)
    is_impossible_travel = Column(Boolean)
    is_new_device = Column(Boolean)
    is_new_ip = Column(Boolean)
    
    # Time
    update_time = Column(DateTime(timezone=True))
    
    # --- Other 40+ columns mapped generically for the "View All" modal ---
    # We don't need to define every single column explicitly for SQLAlchemy 
    # if we only select specific ones for the list. 
    # BUT for "View All", we need them. 
    # To save space here, I will define the most important ones used in logic.
    # The rest will be fetched dynamically or we define them all.
    # For a production app, define ALL. Here is a subset for the list + generic access.
    
    deposit_fan_out = Column(Integer)
    withdrawal_fan_in = Column(Integer)
    ip_density = Column(Integer)
    device_density = Column(Integer)
    withdrawal_ratio = Column(Double)
    destination_address = Column(String)
    rapid_cycling = Column(Boolean)
    user_whitelisted = Column(Boolean)
    address_whitelisted = Column(Boolean)
    user_blacklisted = Column(Boolean)
    address_blacklisted = Column(Boolean)



# ================= DECISION LOG =================
class RiskWithdrawDecision(Base):
    __tablename__ = "risk_withdraw_decision"
    __table_args__ = {"schema": "rt"}

    # Although PK is composite, we use log_id for unique lookup in UI
    log_id = Column(Integer, primary_key=True) 
    
    user_code = Column(String)
    txn_id = Column(String)
    decision_source = Column(String) # RULE_ENGINE_RULES or AI_AGENT_REVIEW
    decision = Column(String)        # PASS, REJECT, HOLD
    primary_threat = Column(String)
    confidence = Column(Float)
    narrative = Column(Text)
    llm_reasoning = Column(Text)
    processing_time_ms = Column(Double)
    
    # Snapshot of data at the time of decision
    features_snapshot = Column(JSONB) 
    
    decision_timestamp = Column(DateTime(timezone=True))


# NEW TABLE DEFINITION
class UserDevice(Base):
    __tablename__ = "user_device"
    __table_args__ = {"schema": "rt"}

    id = Column(BigInteger, primary_key=True)
    user_code = Column(BigInteger)
    event_id = Column(BigInteger)  # This maps to txn_id
    country = Column(String)
    country_code = Column(String)
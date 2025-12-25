from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# --- Whitelist User ---
class WhitelistUserCreate(BaseModel):
    user_code: str
    description: str
    expires_at: Optional[datetime] = None
    status: str = "ACTIVE"

# --- Whitelist Address ---
class WhitelistAddressCreate(BaseModel):
    destination_address: str
    chain: str
    description: str
    expires_at: Optional[datetime] = None
    status: str = "ACTIVE"

# --- Greylist ---
class GreylistCreate(BaseModel):
    entity_value: str
    entity_type: str
    reason: str
    expires_at: Optional[datetime] = None
    status: str = "ACTIVE"
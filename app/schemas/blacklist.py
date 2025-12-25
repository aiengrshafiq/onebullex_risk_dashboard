from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# --- Base Schema (Common Fields) ---
class BlacklistBase(BaseModel):
    reason: str
    expires_at: Optional[datetime] = None
    status: str = "ACTIVE"

# --- User ---
class BlacklistUserCreate(BlacklistBase):
    user_code: str

# --- IP ---
class BlacklistIPCreate(BlacklistBase):
    ip_address: str

# --- Email Domain ---
class BlacklistDomainCreate(BlacklistBase):
    email_domain: str

# --- Crypto Address ---
class BlacklistAddressCreate(BlacklistBase):
    destination_address: str
    chain: str
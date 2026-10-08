from pydantic import BaseModel, Field
from typing import Optional


# ============================================================================
# Request Schemas
# ============================================================================

class AccessCodeSubmit(BaseModel):
    """Soumission du code d'accès aux zones privées"""
    code: str = Field(..., min_length=1, max_length=128)


# ============================================================================
# Response Schemas
# ============================================================================

class AccessStatusResponse(BaseModel):
    """État de l'accès privé (unlock, status et lock)"""
    unlocked: bool
    expires_in_seconds: Optional[int] = None

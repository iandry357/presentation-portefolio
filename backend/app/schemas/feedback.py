from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ============================================================================
# Request Schemas
# ============================================================================

class FeedbackAnswerCreate(BaseModel):
    """Réponse à une question du feedback"""
    question_key: str = Field(..., min_length=1, max_length=100)
    comment: Optional[str] = None


class FeedbackCreate(BaseModel):
    """Création d'un feedback"""
    session_id: UUID
    page_route: str = Field(..., min_length=1, max_length=255)
    page_type: str = Field(..., min_length=1, max_length=50)
    rating: int = Field(..., ge=1, le=5)
    job_offer_id: Optional[int] = None
    company_profile_id: Optional[int] = None
    answers: List[FeedbackAnswerCreate] = Field(default_factory=list)

    @field_validator('rating')
    @classmethod
    def validate_rating(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError('Rating must be between 1 and 5')
        return v


# ============================================================================
# Response Schemas
# ============================================================================

class FeedbackAnswerResponse(BaseModel):
    """Réponse à une question (pour lecture)"""
    id: int
    question_key: str
    comment: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class FeedbackResponse(BaseModel):
    """Feedback complet (pour lecture)"""
    id: int
    session_id: UUID
    user_id: Optional[int]
    page_route: str
    page_type: str
    rating: int
    job_offer_id: Optional[int]
    company_profile_id: Optional[int]
    created_at: datetime
    answers: List[FeedbackAnswerResponse]

    class Config:
        from_attributes = True


class FeedbackCreateResponse(BaseModel):
    """Réponse après création d'un feedback"""
    id: int
    message: str
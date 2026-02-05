from pydantic import BaseModel, Field
from typing import Optional, List


class SourceReference(BaseModel):
    """Référence à une source utilisée dans la réponse."""
    type: str  # "experience" | "project" | "formation"
    title: str
    score: float
    id: int


class ChatRequest(BaseModel):
    """Requête chat utilisateur."""
    message: str = Field(..., min_length=1, max_length=1000)
    session_id: str


class ChatResponse(BaseModel):
    """Réponse générée par le RAG."""
    query_id: str
    response: str
    sources: List[SourceReference]
    tokens_used: int
    cost: float  
    provider_used: str      
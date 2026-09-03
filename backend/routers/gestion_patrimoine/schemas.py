"""
schemas.py — Schémas Pydantic des endpoints /gestion-patrimoine/*.
"""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel


# --------------------------------------------------------------------------
# POST /gestion-patrimoine/profil
# --------------------------------------------------------------------------

class GenererProfilRequest(BaseModel):
    thematique: Optional[str] = None  # None → tirage aléatoire côté profil_agent


class GenererProfilResponse(BaseModel):
    session_id: UUID
    profil: dict


# --------------------------------------------------------------------------
# POST /gestion-patrimoine/chat
# --------------------------------------------------------------------------

class ChatRequest(BaseModel):
    session_id: UUID
    message: Optional[str] = None  # requis à partir du 2e tour, ignoré au premier


class ArticleCiteSchema(BaseModel):
    numero_article: str
    url_source: str


class ChatResponseSchema(BaseModel):
    texte: str
    articles_cites: list[ArticleCiteSchema]
    latence_ms: int
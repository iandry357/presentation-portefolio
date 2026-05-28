"""
Schémas Pydantic pour les routes /savencia/*.
"""
from typing import List, Optional
from pydantic import BaseModel


# ─────────────────────────────────────────
# Stats globales
# ─────────────────────────────────────────

class SavenciaStats(BaseModel):
    total_news: int
    total_savencia_news: int
    total_agroalimentaire_ia: int
    last_updated: Optional[str] = None


# ─────────────────────────────────────────
# News
# ─────────────────────────────────────────

class NewsItem(BaseModel):
    id: str
    title: str
    date: Optional[str]
    source_name: Optional[str]
    feed_name: Optional[str]
    url: Optional[str]


class NewsResponse(BaseModel):
    total: int
    items: List[NewsItem]


# ─────────────────────────────────────────
# RAG
# ─────────────────────────────────────────

class RagRequest(BaseModel):
    question: str
    n_results: Optional[int] = 5


class RagSource(BaseModel):
    id: str
    source: str
    title: str
    url: Optional[str]
    score: Optional[float]


class RagResponse(BaseModel):
    answer: str
    sources: List[RagSource]
    model_used: str
    tokens_used: int


# ─────────────────────────────────────────
# ViT Inference
# ─────────────────────────────────────────

class VitProbability(BaseModel):
    class_name: str
    probability: float


class VitInferenceResponse(BaseModel):
    cheese_type: str
    ripeness: str
    confidence: float
    class_name: str
    all_probabilities: dict
    heatmap_base64: str
    model_version: str
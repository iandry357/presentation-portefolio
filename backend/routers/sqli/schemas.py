"""
Schémas Pydantic pour les routes /sqli/*.
"""
from typing import List, Optional
from pydantic import BaseModel


# ─────────────────────────────────────────
# Stats globales
# ─────────────────────────────────────────

class SqliStats(BaseModel):
    total_news: int
    last_updated: Optional[str] = None


# ─────────────────────────────────────────
# News
# ─────────────────────────────────────────

class NewsItem(BaseModel):
    id: str
    title: str
    date: Optional[str]
    source: Optional[str]
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
    date: Optional[str] = None


class RagResponse(BaseModel):
    answer: str
    sources: List[RagSource]
    model_used: str
    tokens_used: int


# ─────────────────────────────────────────
# ML — Topic Modeling
# ─────────────────────────────────────────

class Topic(BaseModel):
    topic_id: int
    label: str
    keywords: List[str]
    summary: Optional[str] = None


class TopicDoc(BaseModel):
    id: Optional[str]
    source: Optional[str]
    title: Optional[str]
    date: Optional[str]
    url: Optional[str]
    dominant_topic: int
    dominant_label: str
    confidence: float


class TopicModelingResponse(BaseModel):
    n_topics: int
    total_docs: int
    topics: List[Topic]
    docs: List[TopicDoc]

"""
Schémas Pydantic pour les routes /sg/*.
"""
from typing import List, Optional
from pydantic import BaseModel


# ─────────────────────────────────────────
# Stats globales
# ─────────────────────────────────────────

class SgStats(BaseModel):
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


class RagResponse(BaseModel):
    answer: str
    sources: List[RagSource]
    model_used: str
    tokens_used: int


# ─────────────────────────────────────────
# ML — YOLO
# ─────────────────────────────────────────

class YoloDetection(BaseModel):
    class_name: str
    score: float
    x1: float
    y1: float
    x2: float
    y2: float


class YoloResponse(BaseModel):
    detections: List[YoloDetection]


# ─────────────────────────────────────────
# ML — NER
# ─────────────────────────────────────────

class NerEntity(BaseModel):
    text: str
    label: str
    score: float
    start: int
    end: int


class NerRequest(BaseModel):
    text: str


class NerResponse(BaseModel):
    entities: List[NerEntity]


# ─────────────────────────────────────────
# ML — Qwen
# ─────────────────────────────────────────

class QwenRequest(BaseModel):
    prompt: str
    max_new_tokens: Optional[int] = 200


class QwenResponse(BaseModel):
    generated_text: str
    model_type: str


# ─────────────────────────────────────────
# ML — Topic Modeling
# ─────────────────────────────────────────

class Topic(BaseModel):
    topic_id: int
    label: str
    keywords: List[str]


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
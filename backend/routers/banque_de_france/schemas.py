"""
Schémas Pydantic pour les routes /banque-de-france/*.
"""
from typing import List, Optional
from pydantic import BaseModel


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

# ─────────────────────────────────────────
# ML — EBA (scoring composite)
# ─────────────────────────────────────────

class EbaRatios(BaseModel):
    cet1_ratio: float
    leverage_ratio: float
    npl_ratio: float


class EbaMethodology(BaseModel):
    description: str
    eu_average_definition: str
    coverage_note: str
    unit: str
    not_a_regulatory_score: bool
    not_a_trained_model: bool


class EbaRecord(BaseModel):
    bank_name: str
    lei_code: str
    period: str
    ratios: EbaRatios
    eu_average: EbaRatios
    gaps_vs_eu_average: EbaRatios
    composite_score: float


class EbaScoresResponse(BaseModel):
    methodology: EbaMethodology
    records: List[EbaRecord]

# ─────────────────────────────────────────
# ML — Classification (griefs ACPR)
# ─────────────────────────────────────────

class ClassificationRequest(BaseModel):
    text: str


class ClassificationPrediction(BaseModel):
    category: str
    score: float
    threshold: float
    predicted: bool


class ClassificationResponse(BaseModel):
    predictions: List[ClassificationPrediction]
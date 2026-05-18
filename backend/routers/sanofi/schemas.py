"""
Schémas Pydantic pour les routes /sanofi/*.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


# ─────────────────────────────────────────
# Stats globales
# ─────────────────────────────────────────

class SanofiStats(BaseModel):
    total_clinical_trials: int
    total_pubmed: int
    total_news: int
    last_updated: Optional[str] = None


# ─────────────────────────────────────────
# Clinical Trials
# ─────────────────────────────────────────

class ClinicalTrialItem(BaseModel):
    id: str
    title: str
    date: Optional[str]
    phase: Optional[str]
    status: Optional[str]
    conditions: Optional[List[str]]
    study_type: Optional[str]
    sponsor: Optional[str]
    url: Optional[str]


class ClinicalTrialsResponse(BaseModel):
    total: int
    items: List[ClinicalTrialItem]


# ─────────────────────────────────────────
# PubMed
# ─────────────────────────────────────────

class PubMedItem(BaseModel):
    id: str
    title: str
    date: Optional[str]
    journal: Optional[str]
    authors: Optional[List[str]]
    keywords: Optional[List[str]]
    url: Optional[str]


class PubMedResponse(BaseModel):
    total: int
    items: List[PubMedItem]


# ─────────────────────────────────────────
# News
# ─────────────────────────────────────────

class NewsItem(BaseModel):
    id: str
    title: str
    date: Optional[str]
    source_name: Optional[str]
    url: Optional[str]


class NewsResponse(BaseModel):
    total: int
    items: List[NewsItem]


# ─────────────────────────────────────────
# RAG
# ─────────────────────────────────────────

class RagRequest(BaseModel):
    question: str
    sources: Optional[List[str]] = None  # None = toutes les sources
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
# Recherche sémantique
# ─────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    sources: Optional[List[str]] = None  # None = toutes les sources
    n_results: Optional[int] = 10


class SearchResult(BaseModel):
    id: str
    source: str
    title: str
    date: Optional[str]
    url: Optional[str]
    score: Optional[float]
    excerpt: Optional[str]


class SearchResponse(BaseModel):
    total: int
    results: List[SearchResult]
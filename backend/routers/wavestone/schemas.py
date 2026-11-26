"""
Schémas Pydantic pour les routes /wavestone/*.
"""
from typing import List, Optional
from pydantic import BaseModel


# ─────────────────────────────────────────
# Stats
# ─────────────────────────────────────────

class SectionCount(BaseModel):
    section: str                  # news, insight, clients_story, presse
    langue: Optional[str] = None
    nb_documents: int


class WavestoneStats(BaseModel):
    total_documents: int
    sections: List[SectionCount]
    last_updated: Optional[str] = None
    total_offres: int
    intitules_distincts: int
    periode_debut: Optional[str] = None
    periode_fin: Optional[str] = None
    charge_le: Optional[str] = None


# ─────────────────────────────────────────
# News (site + presse)
# ─────────────────────────────────────────

class NewsItem(BaseModel):
    id: str
    title: str
    date: Optional[str]
    source: Optional[str]
    url: Optional[str]
    section: str
    langue: Optional[str] = None
    source_name: Optional[str] = None
    date_type: Optional[str] = None


class NewsResponse(BaseModel):
    total: int
    items: List[NewsItem]


# ─────────────────────────────────────────
# RAG
# ─────────────────────────────────────────

class RagRequest(BaseModel):
    question: str
    n_results: Optional[int] = 8


class RagSource(BaseModel):
    id: str
    source: str
    title: str
    url: Optional[str]
    score: Optional[float]
    date: Optional[str] = None
    section: Optional[str] = None
    langue: Optional[str] = None


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
    lang: Optional[str] = None
    summary: Optional[str] = None


class TopicDoc(BaseModel):
    id: Optional[str]
    source: Optional[str]
    title: Optional[str]
    date: Optional[str]
    url: Optional[str]
    lang: Optional[str] = None
    section: Optional[str] = None
    dominant_topic: int
    dominant_label: str
    confidence: float


class TopicModelingResponse(BaseModel):
    n_topics: int
    total_docs: int
    topics: List[Topic]
    docs: List[TopicDoc]


# ─────────────────────────────────────────
# Cas clients
# ─────────────────────────────────────────

class CasClient(BaseModel):
    id: Optional[str]
    title: Optional[str]
    date: Optional[str]
    url: Optional[str]
    lang: Optional[str] = None
    secteur: str
    types_mission: List[str]
    client: Optional[str] = None
    resume: Optional[str] = None


class CasClientsResponse(BaseModel):
    genere_le: Optional[str] = None
    total: int
    secteurs: List[str]
    types_mission: List[str]
    cas: List[CasClient]


# ─────────────────────────────────────────
# Recrutement
# ─────────────────────────────────────────

class PosteItem(BaseModel):
    titre: str
    famille: str
    nb_publications: int          # republications du même intitulé sur la fenêtre
    premiere_date: Optional[str] = None
    derniere_date: Optional[str] = None
    lieu: Optional[str] = None
    contrat: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    score_max: Optional[int] = None          # adéquation au profil du candidat (0 à 100)
    categorie: Optional[str] = None          # coeur, adjacent, hors_cible
    cible_intitule: Optional[str] = None
    a_texte_complet: bool = False


class FamilleItem(BaseModel):
    famille: str
    nb_intitules: int
    nb_publications: int


class RecrutementResponse(BaseModel):
    total_offres: int
    intitules_distincts: int
    periode_debut: Optional[str] = None
    periode_fin: Optional[str] = None
    familles: List[FamilleItem]
    postes: List[PosteItem]

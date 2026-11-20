"""
Schémas Pydantic pour les routes /beelix/*.
"""
from typing import List, Optional
from pydantic import BaseModel


# ─────────────────────────────────────────
# Stats et secteurs
# ─────────────────────────────────────────

class BeelixStats(BaseModel):
    periode_debut: Optional[str] = None
    periode_fin: Optional[str] = None
    total_offres: int
    offres_cibles: int            # 6 secteurs Beelix
    comptes_cibles: int
    offres_concurrence: int
    nb_concurrents: int
    total_news: int
    charge_le: Optional[str] = None


class SecteurItem(BaseModel):
    secteur: str
    libelle: str
    nb_offres: int
    nb_entreprises: int
    cible: bool


class SecteursResponse(BaseModel):
    items: List[SecteurItem]


# ─────────────────────────────────────────
# Comptes et offres
# ─────────────────────────────────────────

class CompteItem(BaseModel):
    entreprise_nom: str
    entreprise_normalise: str
    secteur: str
    secteur_libelle: str
    naf_libelle: Optional[str] = None
    nb_offres: int
    derniere_offre: Optional[str] = None
    titres_recents: List[str]


class ComptesResponse(BaseModel):
    secteur: Optional[str] = None
    total: int
    items: List[CompteItem]


class OffreItem(BaseModel):
    id_unique: str
    titre: Optional[str] = None
    entreprise_nom: Optional[str] = None
    secteur_libelle: Optional[str] = None
    localisation_libelle: Optional[str] = None
    type_contrat_libelle: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None


class OffresResponse(BaseModel):
    total: int
    items: List[OffreItem]


# ─────────────────────────────────────────
# Concurrence, besoins, tendance
# ─────────────────────────────────────────

class ConcurrentItem(BaseModel):
    rang: int
    entreprise_nom: str
    nb_offres: int
    part: float                   # % des offres de la concurrence
    est_beelix: bool


class ConcurrenceResponse(BaseModel):
    total_offres: int
    nb_concurrents: int
    rang_beelix: Optional[int] = None
    items: List[ConcurrentItem]


class BesoinItem(BaseModel):
    famille: str
    nb_offres: int
    part: float                   # % des offres du périmètre


class BesoinsResponse(BaseModel):
    secteur: Optional[str] = None
    total: int
    items: List[BesoinItem]


class TendancePoint(BaseModel):
    semaine: str                  # lundi de la semaine, AAAA-MM-JJ
    offres_cibles: int
    offres_concurrence: int


class TendanceResponse(BaseModel):
    points: List[TendancePoint]


# ─────────────────────────────────────────
# News (comme SQLI)
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
# RAG (comme SQLI, entreprise en plus dans les sources)
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
    entreprise: Optional[str] = None
    secteur: Optional[str] = None


class RagResponse(BaseModel):
    answer: str
    sources: List[RagSource]
    model_used: str
    tokens_used: int

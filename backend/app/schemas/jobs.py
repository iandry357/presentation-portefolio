from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime


# ============================================================================
# JobOffer - Offre brute
# ============================================================================

class JobOfferSummary(BaseModel):
    """Vue résumée pour la liste des cards frontend."""
    id: int
    ft_id: Optional[str] = None
    source_offer: Optional[str] = None
    title: str
    description: Optional[str]
    company_name: Optional[str]
    location_label: Optional[str]
    contract_type: Optional[str]
    contract_label: Optional[str]
    work_time: Optional[str]
    salary_label: Optional[str]
    experience_label: Optional[str]
    sector_label: Optional[str]
    offer_url: Optional[str]
    ft_published_at: Optional[datetime]
    status: str
    applied_at: Optional[datetime]
    # has_enriched: bool  # indique si la fiche enrichie existe déjà
    has_enriched: bool = False
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class JobOfferDetail(JobOfferSummary):
    """Vue complète pour la page détail — inclut les données brutes."""
    # description: Optional[str]
    rome_code: Optional[str]
    location_postal_code: Optional[str]
    location_lat: Optional[float]
    location_lng: Optional[float]
    company_description: Optional[str]
    company_url: Optional[str]
    company_profile_id: Optional[int] = None
    source_offer: Optional[str] = None
    naf_code: Optional[str]
    raw_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# JobEnriched - Fiche enrichie
# ============================================================================

class JobEnrichedResponse(BaseModel):
    """Fiche enrichie retournée au frontend."""
    id: int
    job_offer_id: int
    parsed_data: Optional[Dict[str, Any]]
    analysis: Optional[Dict[str, Any]]
    summary: Optional[str]
    recalcul_count: int
    recalcul_remaining: int = 0     # calculé : 3 - recalcul_count
    recalcul_history: Optional[List[Dict[str, Any]]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Requêtes
# ============================================================================

class RecalculRequest(BaseModel):
    """Requête de recalcul d'une fiche enrichie."""
    instruction: str = Field(..., min_length=5, max_length=500)

class ManualJobRequest(BaseModel):
    """Ajout manuel d'une offre par son identifiant France Travail."""
    ft_id: str = Field(..., min_length=3, max_length=50)


class StatusUpdateRequest(BaseModel):
    """Mise à jour manuelle du statut d'une offre."""
    # status: str = Field(..., pattern="^(consulte|postule)$")
    status: str = Field(..., pattern="^(consulte|postule|enregistre)$")


class TriggerPipelineRequest(BaseModel):
    """Déclenchement manuel du pipeline (dev uniquement)."""
    region: Optional[str] = None    # override zone géo si besoin

class ExternalJobOfferCreate(BaseModel):
    """Ajout manuel d'une offre externe (hors France Travail)."""
    # Champs obligatoires
    title: str = Field(..., min_length=2, max_length=255)
    description: str = Field(..., min_length=10)
    company_name: str = Field(..., min_length=2, max_length=255)
    company_description: str = Field(..., min_length=10)
    location_label: str = Field(..., min_length=2, max_length=255)

    # Champs optionnels
    source_offer: Optional[str] = None
    offer_url: Optional[str] = None
    contract_type: Optional[str] = None
    experience_label: Optional[str] = None
    work_time: Optional[str] = None
    salary_label: Optional[str] = None
    sector_label: Optional[str] = None

    # Comportement pipeline
    trigger_enrichment: bool = False

    published_at: datetime


# ============================================================================
# Réponses
# ============================================================================

class JobListResponse(BaseModel):
    """Réponse paginée pour la liste des offres."""
    total: int
    items: List[JobOfferSummary]


class PipelineTriggerResponse(BaseModel):
    """Retour du déclenchement du pipeline."""
    message: str
    offers_collected: int
    offers_scored: int
    offers_enriched: int

class JobNotesUpdate(BaseModel):
    """Mise à jour des notes personnelles sur une offre."""
    notes: str
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime


# ============================================================================
# JobOffer - Offre brute
# ============================================================================

class JobOfferSummary(BaseModel):
    """Vue résumée pour la liste des cards frontend."""
    id: int
    ft_id: str
    title: str
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
    has_enriched: bool  # indique si la fiche enrichie existe déjà

    class Config:
        from_attributes = True


class JobOfferDetail(JobOfferSummary):
    """Vue complète pour la page détail — inclut les données brutes."""
    description: Optional[str]
    rome_code: Optional[str]
    location_postal_code: Optional[str]
    location_lat: Optional[float]
    location_lng: Optional[float]
    company_description: Optional[str]
    company_url: Optional[str]
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
    recalcul_remaining: int     # calculé : 3 - recalcul_count
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


class StatusUpdateRequest(BaseModel):
    """Mise à jour manuelle du statut d'une offre."""
    status: str = Field(..., pattern="^(consulte|postule)$")


class TriggerPipelineRequest(BaseModel):
    """Déclenchement manuel du pipeline (dev uniquement)."""
    region: Optional[str] = None    # override zone géo si besoin


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
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.config import settings
from app.core import france_travail_config as ft
from app.models.job_offer import JobOffer
from app.models.job_enriched import JobEnriched
from app.schemas.jobs import (
    JobListResponse,
    JobOfferSummary,
    JobOfferDetail,
    JobEnrichedResponse,
    RecalculRequest,
    StatusUpdateRequest,
    TriggerPipelineRequest,
    PipelineTriggerResponse,
)
from app.services.job_crew.crew import run_enrichment_crew
from app.services.job_scoring import build_profile_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ============================================================================
# GET /jobs — Liste paginée avec filtres
# ============================================================================

@router.get("", response_model=JobListResponse)
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    # Pagination
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    # Filtres
    contract_type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    hide_consulted: bool = Query(default=False),
    postal_code: Optional[str] = Query(default=None),
    max_days_old: Optional[int] = Query(default=None),
):
    filters = []

    if contract_type:
        filters.append(JobOffer.contract_type == contract_type)

    if status:
        filters.append(JobOffer.status == status)

    if hide_consulted:
        filters.append(JobOffer.status != "consulte")

    if postal_code:
        filters.append(JobOffer.location_postal_code == postal_code)

    if max_days_old:
        cutoff = datetime.utcnow() - timedelta(days=max_days_old)
        filters.append(JobOffer.ft_published_at >= cutoff)

    # Compter le total
    count_query = select(func.count()).select_from(JobOffer)
    if filters:
        count_query = count_query.where(and_(*filters))
    total = await db.scalar(count_query)

    # Récupérer les offres triées par date de création DESC
    query = select(JobOffer)
    if filters:
        query = query.where(and_(*filters))
    query = query.order_by(JobOffer.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    offers = result.scalars().all()

    # Vérifier quelles offres ont une fiche enrichie
    offer_ids = [o.id for o in offers]
    enriched_ids = set()
    if offer_ids:
        enriched_result = await db.execute(
            select(JobEnriched.job_offer_id).where(
                JobEnriched.job_offer_id.in_(offer_ids)
            )
        )
        enriched_ids = {row[0] for row in enriched_result.fetchall()}

    items = []
    for offer in offers:
        summary = JobOfferSummary.model_validate(offer)
        summary.has_enriched = offer.id in enriched_ids
        items.append(summary)

    return JobListResponse(total=total, items=items)


# ============================================================================
# GET /jobs/{id} — Détail offre + fiche enrichie
# ============================================================================

@router.get("/{job_id}", response_model=JobOfferDetail)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    offer = await db.get(JobOffer, job_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offre introuvable")

    # Marquer comme consultée si pas encore postulée
    if offer.status == "nouveau" or offer.status == "existant":
        offer.status = "consulte"
        await db.commit()

    return JobOfferDetail.model_validate(offer)


# ============================================================================
# GET /jobs/{id}/enriched — Fiche enrichie
# ============================================================================

@router.get("/{job_id}/enriched", response_model=JobEnrichedResponse)
async def get_job_enriched(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(JobEnriched).where(JobEnriched.job_offer_id == job_id)
    )
    enriched = result.scalar_one_or_none()
    if not enriched:
        raise HTTPException(status_code=404, detail="Fiche enrichie introuvable")

    response = JobEnrichedResponse.model_validate(enriched)
    response.recalcul_remaining = ft.RECALCUL_MAX - enriched.recalcul_count
    return response


# ============================================================================
# PATCH /jobs/{id}/status — Mise à jour statut
# ============================================================================

@router.patch("/{job_id}/status")
async def update_status(
    job_id: int,
    body: StatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    offer = await db.get(JobOffer, job_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offre introuvable")

    offer.status = body.status
    if body.status == "postule":
        offer.applied_at = datetime.utcnow()

    await db.commit()
    return {"message": f"Statut mis à jour : {body.status}"}


# ============================================================================
# POST /jobs/{id}/enrich — Calcul initial Crew
# ============================================================================

@router.post("/{job_id}/enrich", response_model=JobEnrichedResponse)
async def enrich_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
):
    offer = await db.get(JobOffer, job_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offre introuvable")

    # Vérifier qu'une fiche n'existe pas déjà
    existing = await db.execute(
        select(JobEnriched).where(JobEnriched.job_offer_id == job_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Fiche enrichie déjà existante")

    profile_text = await build_profile_text(db)
    result = await run_enrichment_crew(
        offer_raw=offer.raw_data,
        profile_text=profile_text,
        initial_prompt="Analyse cette offre d'emploi en détail.",
    )

    enriched = JobEnriched(
        job_offer_id=job_id,
        score=offer.raw_data.get("_score", 0.0),
        parsed_data=result["parsed_data"],
        analysis=result["analysis"],
        summary=result["summary"],
        initial_prompt="Analyse cette offre d'emploi en détail.",
        recalcul_history=[],
        recalcul_count=0,
    )
    db.add(enriched)
    await db.commit()
    await db.refresh(enriched)

    response = JobEnrichedResponse.model_validate(enriched)
    response.recalcul_remaining = ft.RECALCUL_MAX
    return response


# ============================================================================
# POST /jobs/{id}/recalcul — Recalcul avec instruction
# ============================================================================

@router.post("/{job_id}/recalcul", response_model=JobEnrichedResponse)
async def recalcul_job(
    job_id: int,
    body: RecalculRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JobEnriched).where(JobEnriched.job_offer_id == job_id)
    )
    enriched = result.scalar_one_or_none()
    if not enriched:
        raise HTTPException(status_code=404, detail="Fiche enrichie introuvable")

    if enriched.recalcul_count >= ft.RECALCUL_MAX:
        raise HTTPException(
            status_code=403,
            detail=f"Limite de {ft.RECALCUL_MAX} recalculs atteinte pour cette offre"
        )

    offer = await db.get(JobOffer, job_id)
    profile_text = await build_profile_text(db)

    new_result = await run_enrichment_crew(
        offer_raw=offer.raw_data,
        profile_text=profile_text,
        initial_prompt=enriched.initial_prompt,
        instruction=body.instruction,
    )

    # Mise à jour de la fiche
    history = enriched.recalcul_history or []
    history.append({
        "instruction": body.instruction,
        "recalcul_at": datetime.utcnow().isoformat(),
    })

    enriched.parsed_data     = new_result["parsed_data"]
    enriched.analysis        = new_result["analysis"]
    enriched.summary         = new_result["summary"]
    enriched.recalcul_history = history
    enriched.recalcul_count  += 1

    await db.commit()
    await db.refresh(enriched)

    response = JobEnrichedResponse.model_validate(enriched)
    response.recalcul_remaining = ft.RECALCUL_MAX - enriched.recalcul_count
    return response


# ============================================================================
# POST /jobs/pipeline/trigger — Déclenchement manuel (dev uniquement)
# ============================================================================

@router.post("/pipeline/trigger", response_model=PipelineTriggerResponse)
async def trigger_pipeline(
    body: TriggerPipelineRequest,
    db: AsyncSession = Depends(get_db),
):
    if settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=403,
            detail="Déclenchement manuel désactivé en production"
        )

    from app.scheduler.job_pipeline import run_pipeline
    result = await run_pipeline(db=db, region=body.region)
    return result
import asyncio
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.company_profile import CompanyProfile
from app.models.job_offer import JobOffer
from app.schemas.company import (
    CompanyActionResponse,
    CompanyProfileCreate,
    CompanyProfileDetail,
    CompanyProfileSummary,
    CompanyRecalculRequest,
    CompanyRefreshRequest,
)
from app.services.company_crew.crew import (
    run_company_full_pipeline,
    run_company_refresh,
    run_company_recalcul,
    run_company_relaunch,
)

from app.models.job_offer import JobOffer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/companies", tags=["companies"])

RECALCUL_MAX = 3


# ------------------------------------------------------------
# Utilitaires
# ------------------------------------------------------------

def _normalize_name(raw: str) -> str:
    """Normalisation du nom entreprise : lowercase + strip formes juridiques."""
    suffixes = [" sa", " sas", " sarl", " sasu", " sci", " snc", " eurl", " inc", " ltd"]
    name = raw.strip().lower()
    for s in suffixes:
        if name.endswith(s):
            name = name[: -len(s)].strip()
    return name


async def _get_company_or_404(company_id: int, db: AsyncSession) -> CompanyProfile:
    result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.id == company_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Fiche entreprise introuvable")
    return company


# ------------------------------------------------------------
# LECTURE
# ------------------------------------------------------------

@router.get("", response_model=List[CompanyProfileSummary])
async def list_companies(db: AsyncSession = Depends(get_db)):
    """Liste résumée de toutes les fiches entreprises."""
    result = await db.execute(
        select(CompanyProfile).order_by(CompanyProfile.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/{company_id}", response_model=CompanyProfileDetail)
async def get_company(company_id: int, db: AsyncSession = Depends(get_db)):
    """Détail complet d'une fiche entreprise."""
    return await _get_company_or_404(company_id, db)


# ------------------------------------------------------------
# LECTURE — depuis une offre
# ------------------------------------------------------------

@router.get("/by-job/{job_id}", response_model=CompanyProfileDetail)
async def get_company_by_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Retourne la fiche entreprise liée à une offre d'emploi."""
    result = await db.execute(
        select(JobOffer).where(JobOffer.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    if not job.company_profile_id:
        raise HTTPException(status_code=404, detail="Aucune fiche entreprise liée à cette offre")
    return await _get_company_or_404(job.company_profile_id, db)


# ------------------------------------------------------------
# ACTIONS ASYNC
# ------------------------------------------------------------

@router.post("/generate", response_model=CompanyActionResponse)
async def generate_company(
    payload: CompanyProfileCreate,
    db: AsyncSession = Depends(get_db),
):
    """Génération complète — Agent 1 + Agent 2 + Agent 3.
    Consomme 2 recherches Serper. Ne relance pas si fiche déjà existante."""
    name = _normalize_name(payload.name_input)

    # Vérifier si la fiche existe déjà
    result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.name == name)
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Lier l'offre si fournie et pas encore liée
        if payload.job_offer_id:
            job_result = await db.execute(
                select(JobOffer).where(JobOffer.id == payload.job_offer_id)
            )
            job = job_result.scalar_one_or_none()
            if job and not job.company_profile_id:
                job.company_profile_id = existing.id
                await db.commit()
        return CompanyActionResponse(
            company_profile_id=existing.id,
            message="Fiche entreprise déjà existante — utilise la fiche en base"
        )

    # Créer l'entrée en base avec statuts pending
    company = CompanyProfile(
        name=name,
        name_input=payload.name_input,
    )
    db.add(company)
    await db.commit()
    await db.refresh(company)

    # Lier l'offre source si fournie
    if payload.job_offer_id:
        job_result = await db.execute(
            select(JobOffer).where(JobOffer.id == payload.job_offer_id)
        )
        job = job_result.scalar_one_or_none()
        if job:
            job.company_profile_id = company.id
            await db.commit()

    # Lancer le pipeline en arrière-plan
    # asyncio.create_task(run_company_full_pipeline(company.id))
    asyncio.create_task(run_company_full_pipeline(company.id, payload.job_offer_id))

    logger.info(f"[company] Pipeline complet déclenché — id={company.id} name={name}")

    return CompanyActionResponse(
        company_profile_id=company.id,
        message="Génération en cours"
    )


@router.post("/{company_id}/refresh", response_model=CompanyActionResponse)
async def refresh_company(
    company_id: int,
    payload: CompanyRefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """Actualiser les infos — Agent 2 + refresh actualités + Agent 3.
    Repart des URLs dans discovery. Ne consomme pas de crédit Serper."""
    company = await _get_company_or_404(company_id, db)

    if company.discovery_status != "done":
        raise HTTPException(
            status_code=400,
            detail="Discovery non disponible — impossible de rafraîchir sans URLs de référence"
        )

    # Remettre les statuts en pending
    company.legal_status = "pending"
    company.actualites_status = "pending"
    company.memo_status = "pending"
    await db.commit()

    asyncio.create_task(run_company_refresh(company_id))

    logger.info(f"[company] Refresh déclenché — id={company_id}")

    return CompanyActionResponse(
        company_profile_id=company_id,
        message="Actualisation en cours"
    )


@router.post("/{company_id}/recalcul", response_model=CompanyActionResponse)
async def recalcul_company(
    company_id: int,
    payload: CompanyRecalculRequest,
    db: AsyncSession = Depends(get_db),
):
    """Regénérer le mémo uniquement — Agent 3.
    Quota max 3 regénérations. Ne consomme aucun appel externe."""
    company = await _get_company_or_404(company_id, db)

    if company.recalcul_count >= RECALCUL_MAX:
        raise HTTPException(
            status_code=403,
            detail=f"Quota de regénération atteint ({RECALCUL_MAX} max)"
        )

    if company.memo_status == "pending":
        raise HTTPException(
            status_code=400,
            detail="Un mémo est déjà en cours de génération"
        )

    # Incrémenter le compteur et historiser l'instruction
    history = list(company.recalcul_history or [])
    history.append(payload.instruction or "")
    company.recalcul_count = company.recalcul_count + 1
    company.recalcul_history = history
    company.memo_status = "pending"
    await db.commit()

    asyncio.create_task(run_company_recalcul(company_id, payload.instruction))

    logger.info(f"[company] Recalcul mémo déclenché — id={company_id} count={company.recalcul_count}")

    return CompanyActionResponse(
        company_profile_id=company_id,
        message=f"Regénération en cours ({company.recalcul_count}/{RECALCUL_MAX})"
    )

@router.post("/{company_id}/relaunch", response_model=CompanyActionResponse)
async def relaunch_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Relance la génération complète — utile si discovery a échoué."""
    company = await _get_company_or_404(company_id, db)

    # récupérer job_offer_id
    result = await db.execute(
        select(JobOffer.id).where(JobOffer.company_profile_id == company_id).limit(1)
    )
    job_offer_id = result.scalar_one_or_none()

    company.discovery_status = "pending"
    company.legal_status = "pending"
    company.actualites_status = "pending"
    company.memo_status = "pending"
    await db.commit()

    # asyncio.create_task(run_company_relaunch(company_id))
    asyncio.create_task(run_company_full_pipeline(company_id, job_offer_id))

    logger.info(f"[company] Relaunch déclenché — id={company_id}")

    return CompanyActionResponse(
        company_profile_id=company_id,
        message="Relance en cours"
    )

# ------------------------------------------------------------
# SUPPRESSION — dev uniquement
# ------------------------------------------------------------

@router.delete("/{company_id}", status_code=204)
async def delete_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Suppression d'une fiche entreprise — dev uniquement."""
    if not settings.is_dev:
        raise HTTPException(status_code=403, detail="Action non disponible en production")

    company = await _get_company_or_404(company_id, db)
    await db.delete(company)
    await db.commit()

    logger.info(f"[company] Fiche supprimée — id={company_id}")
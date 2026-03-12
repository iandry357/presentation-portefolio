import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.company_profile import CompanyProfile
from app.services.company_crew.tasks import (
    run_discovery_chain,
    run_extractor_chain,
    run_actualites_chain,
    run_synthesizer_chain,
)

from sqlalchemy import select
from app.models.job_offer import JobOffer
from app.models.job_enriched import JobEnriched
from app.services.job_profile import build_profile_text_chat

def normalize_company_name(name: str) -> str:
    """
    Normalise le nom d'entreprise pour éviter les erreurs JSON lors des appels LLM.
    
    Transformations appliquées :
    - Apostrophes typographiques ' ' → '
    - Guillemets typographiques " " « » → "
    - Tirets longs – — → -
    - Espaces multiples/insécables → espace simple
    - Trim whitespace début/fin
    
    Args:
        name: Nom brut de l'entreprise
        
    Returns:
        Nom normalisé, safe pour JSON
        
    Exemples:
        >>> normalize_company_name("Dassault Systèmes, l'entreprise")
        "Dassault Systèmes, l'entreprise"
        >>> normalize_company_name("L'Oréal  –  Paris")
        "L'Oréal - Paris"
    """
    if not name:
        return name
    
    # Apostrophes typographiques → apostrophe droite
    name = name.replace("'", "'").replace("'", "'")
    
    # Guillemets typographiques → guillemets droits
    name = name.replace(""", '"').replace(""", '"')
    name = name.replace("«", '"').replace("»", '"')
    
    # Tirets longs → tiret simple
    name = name.replace("–", "-").replace("—", "-")
    
    # Espaces insécables et multiples → espace simple
    name = name.replace("\u00A0", " ")  # Espace insécable
    name = name.replace("\u202F", " ")  # Espace fine insécable
    
    # Réduire espaces multiples
    import re
    name = re.sub(r'\s+', ' ', name)
    
    # Trim
    name = name.strip()
    
    return name

logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# Utilitaire — chargement du profil en base
# ------------------------------------------------------------

async def _get_company(company_id: int, db: AsyncSession) -> CompanyProfile | None:
    result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.id == company_id)
    )
    return result.scalar_one_or_none()


async def _build_offer_context(job_offer_id: int | None, db: AsyncSession) -> str | None:
    """Charge la fiche enrichie si dispo, sinon l'offre brute. Retourne None si absent."""
    if not job_offer_id:
        return None
    result = await db.execute(
        select(JobEnriched).where(JobEnriched.job_offer_id == job_offer_id)
    )
    enriched = result.scalar_one_or_none()
    if enriched and enriched.summary:
        parts = []
        if enriched.summary:
            parts.append(f"Synthèse : {enriched.summary}")
        if enriched.parsed_data:
            parts.append(f"Données extraites : {json.dumps(enriched.parsed_data, ensure_ascii=False)}")
        return "\n".join(parts)

    # Fallback offre brute
    result = await db.execute(
        select(JobOffer).where(JobOffer.id == job_offer_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        return None
    parts = [
        f"Intitulé : {job.title or ''}",
        f"Description : {job.description or ''}",
        f"Entreprise : {job.company_name or ''}",
        f"Contrat : {job.contract_label or ''}",
        f"Expérience requise : {job.experience_label or ''}",
    ]
    return "\n".join(p for p in parts if p.split(": ")[1])


async def _get_job_offer_id_from_company(company_id: int, db: AsyncSession) -> int | None:
    """Récupère le premier job_offer_id lié à cette entreprise."""
    result = await db.execute(
        select(JobOffer.id).where(JobOffer.company_profile_id == company_id).limit(1)
    )
    row = result.scalar_one_or_none()
    return row


# ------------------------------------------------------------
# Pipeline complet — Agent 1 + Agent 2 + actualités + Agent 3
# Déclenché sur POST /companies/generate
# ------------------------------------------------------------

async def run_company_full_pipeline(company_id: int, job_offer_id: int | None = None) -> None:
    """
    Génération complète d'une fiche entreprise.
    Consomme 2 recherches Serper.
    Sauvegarde chaque couche indépendamment — dégradation gracieuse.
    """
    async with get_db_session() as db:
        company = await _get_company(company_id, db)
        if not company:
            logger.error(f"[company_crew] Entreprise introuvable — id={company_id}")
            return

        # company_name = company.name_input
        company_name = normalize_company_name(company.name_input)
        logger.info(f"[company_crew] Pipeline complet démarré — {company_name}")

        # ── Couche 1 : Discovery ──────────────────────────────
        try:
            discovery = run_discovery_chain(company_name)
            company.discovery = discovery
            company.discovery_status = "done"
            logger.info(f"[company_crew] Discovery OK — {company_name}")
        # except Exception as e:
        #     company.discovery_status = "failed"
        #     await db.commit()
        #     logger.error(f"[company_crew] Discovery FAILED — {company_name} — {e}")
        #     return  # discovery est bloquant — on arrête ici
        except Exception as e:
            company.discovery_status = "failed"
            company.legal_status = "failed"
            company.actualites_status = "failed"
            company.memo_status = "failed"
            await db.commit()
            logger.error(f"[company_crew] Discovery FAILED — {company_name} — {e}")
            return

        await db.commit()

        # ── Couche 2 : Legal data ─────────────────────────────
        try:
            legal = run_extractor_chain(discovery)
            company.legal_data = legal
            company.legal_status = "done"
            logger.info(f"[company_crew] Legal OK — {company_name}")
        except Exception as e:
            company.legal_status = "failed"
            legal = {}
            logger.error(f"[company_crew] Legal FAILED — {company_name} — {e}")

        await db.commit()

        # ── Couche 3 : Actualités ─────────────────────────────
        try:
            actualites = run_actualites_chain(discovery)
            company.actualites = actualites
            company.actualites_status = "done"
            company.actualites_updated_at = datetime.now(timezone.utc)
            logger.info(f"[company_crew] Actualités OK — {company_name}")
        except Exception as e:
            company.actualites_status = "failed"
            actualites = {}
            logger.error(f"[company_crew] Actualités FAILED — {company_name} — {e}")

        await db.commit()

        # ── Couche 4 : Mémo ───────────────────────────────────
        try:
            offer_context = await _build_offer_context(job_offer_id, db)
            profile_context = await build_profile_text_chat(db)

            memo = run_synthesizer_chain(
                discovery=discovery,
                legal=legal,
                actualites=actualites,
                offer_context=offer_context,
                profile_context=profile_context,
            )
            
            # memo = run_synthesizer_chain(
            #     discovery=discovery,
            #     legal=legal,
            #     actualites=actualites,
            # )

            company.memo = memo
            company.memo_status = "done"
            logger.info(f"[company_crew] Mémo OK — {company_name}")
        except Exception as e:
            company.memo_status = "failed"
            logger.error(f"[company_crew] Mémo FAILED — {company_name} — {e}")

        await db.commit()
        logger.info(f"[company_crew] Pipeline complet terminé — {company_name}")


# ------------------------------------------------------------
# Refresh — Agent 2 + actualités + Agent 3
# Déclenché sur POST /companies/{id}/refresh
# Repart des URLs dans discovery — 0 Serper
# ------------------------------------------------------------

async def run_company_refresh(company_id: int) -> None:
    """
    Actualise les données sans relancer Agent 1.
    Repart des URLs déjà en base dans discovery.
    """
    async with get_db_session() as db:
        company = await _get_company(company_id, db)
        if not company or not company.discovery:
            logger.error(f"[company_crew] Refresh impossible — discovery manquant id={company_id}")
            return

        # company_name = company.name_input
        company_name = normalize_company_name(company.name_input)
        discovery = company.discovery
        logger.info(f"[company_crew] Refresh démarré — {company_name}")

        # ── Couche 2 : Legal data ─────────────────────────────
        try:
            legal = run_extractor_chain(discovery)
            company.legal_data = legal
            company.legal_status = "done"
            logger.info(f"[company_crew] Refresh legal OK — {company_name}")
        except Exception as e:
            company.legal_status = "failed"
            legal = company.legal_data or {}
            logger.error(f"[company_crew] Refresh legal FAILED — {company_name} — {e}")

        await db.commit()

        # ── Couche 3 : Actualités ─────────────────────────────
        try:
            actualites = run_actualites_chain(discovery)
            company.actualites = actualites
            company.actualites_status = "done"
            company.actualites_updated_at = datetime.now(timezone.utc)
            logger.info(f"[company_crew] Refresh actualités OK — {company_name}")
        except Exception as e:
            company.actualites_status = "failed"
            actualites = company.actualites or {}
            logger.error(f"[company_crew] Refresh actualités FAILED — {company_name} — {e}")

        await db.commit()

        # ── Couche 4 : Mémo ───────────────────────────────────
        try:
            # memo = run_synthesizer_chain(
            #     discovery=discovery,
            #     legal=legal,
            #     actualites=actualites,
            # )
            job_offer_id = await _get_job_offer_id_from_company(company_id, db)
            offer_context = await _build_offer_context(job_offer_id, db)
            profile_context = await build_profile_text_chat(db)

            memo = run_synthesizer_chain(
                discovery=discovery,
                legal=legal,
                actualites=actualites,
                offer_context=offer_context,
                profile_context=profile_context,
            )
            company.memo = memo
            company.memo_status = "done"
            logger.info(f"[company_crew] Refresh mémo OK — {company_name}")
        except Exception as e:
            company.memo_status = "failed"
            logger.error(f"[company_crew] Refresh mémo FAILED — {company_name} — {e}")

        await db.commit()
        logger.info(f"[company_crew] Refresh terminé — {company_name}")


# ------------------------------------------------------------
# Recalcul mémo — Agent 3 uniquement
# Déclenché sur POST /companies/{id}/recalcul
# 0 appel externe — lit les colonnes existantes
# ------------------------------------------------------------

async def run_company_recalcul(company_id: int, instruction: str | None = None) -> None:
    """
    Regénère le mémo uniquement à partir des données déjà en base.
    instruction optionnelle — guidage libre du recalcul.
    """
    async with get_db_session() as db:
        company = await _get_company(company_id, db)
        if not company:
            logger.error(f"[company_crew] Recalcul impossible — id={company_id} introuvable")
            return

        # company_name = company.name_input
        company_name = normalize_company_name(company.name_input)
        logger.info(f"[company_crew] Recalcul mémo démarré — {company_name} instruction={bool(instruction)}")

        try:
            # memo = run_synthesizer_chain(
            #     discovery=company.discovery or {},
            #     legal=company.legal_data or {},
            #     actualites=company.actualites or {},
            #     instruction=instruction,
            # )
            job_offer_id = await _get_job_offer_id_from_company(company_id, db)
            offer_context = await _build_offer_context(job_offer_id, db)
            profile_context = await build_profile_text_chat(db)

            memo = run_synthesizer_chain(
                discovery=company.discovery or {},
                legal=company.legal_data or {},
                actualites=company.actualites or {},
                instruction=instruction,
                offer_context=offer_context,
                profile_context=profile_context,
            )
            company.memo = memo
            company.memo_status = "done"
            logger.info(f"[company_crew] Recalcul mémo OK — {company_name}")
        except Exception as e:
            company.memo_status = "failed"
            logger.error(f"[company_crew] Recalcul mémo FAILED — {company_name} — {e}")

        await db.commit()


async def run_company_relaunch(company_id: int) -> None:
    """Relance le pipeline complet depuis zéro — remet les 4 statuts à pending."""
    async with get_db_session() as db:
        company = await _get_company(company_id, db)
        if not company:
            logger.error(f"[company_crew] Relaunch impossible — id={company_id} introuvable")
            return
        company.discovery_status = "pending"
        company.legal_status = "pending"
        company.actualites_status = "pending"
        company.memo_status = "pending"
        await db.commit()

    await run_company_full_pipeline(company_id)
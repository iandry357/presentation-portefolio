import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core import france_travail_config as ft
from app.models.job_offer import JobOffer
from app.models.job_enriched import JobEnriched
from app.services.france_travail_client import predict_rome_codes, search_offers
from app.services.job_scoring import score_and_filter_offers, build_profile_text

logger = logging.getLogger(__name__)

# ============================================================================
# Cache des codes ROME (calculé une seule fois par session)
# ============================================================================

_rome_codes: Optional[list[str]] = None


async def _get_rome_codes(profile_text: str) -> list[str]:
    """Retourne les codes ROME depuis le cache ou les recalcule via ROMEO."""
    global _rome_codes
    if _rome_codes:
        return _rome_codes

    logger.info("Appel ROMEO pour prédiction des codes ROME...")
    predictions = await predict_rome_codes(profile_text)
    _rome_codes = [p["codeRome"] for p in predictions]
    logger.info(f"Codes ROME obtenus : {_rome_codes}")
    return _rome_codes


# ============================================================================
# Mise à jour des statuts existants
# ============================================================================

async def _update_statuses(db: AsyncSession, active_ft_ids: set[str]) -> None:
    """
    Met à jour les statuts des offres déjà en base :
    - existant : offres > 24h toujours actives
    - ferme    : offres absentes du dernier passage scheduler
    """
    result = await db.execute(
        select(JobOffer).where(JobOffer.status.notin_(["ferme", "postule"]))
    )
    offers = result.scalars().all()

    now = datetime.utcnow()
    for offer in offers:
        if offer.ft_id not in active_ft_ids:
            offer.status = "ferme"
            logger.info(f"Offre fermée : {offer.ft_id}")
        elif offer.status == "nouveau":
            age = now - offer.created_at.replace(tzinfo=None)
            if age > timedelta(hours=24):
                offer.status = "existant"

    await db.commit()


# ============================================================================
# Sauvegarde des nouvelles offres
# ============================================================================

def _map_offer_to_model(offer: dict) -> JobOffer:
    """Mappe une offre brute France Travail vers le model JobOffer."""
    lieu = offer.get("lieuTravail", {})
    entreprise = offer.get("entreprise", {})
    salaire = offer.get("salaire", {})
    contact = offer.get("contact", {})

    return JobOffer(
        ft_id=offer["id"],
        title=offer.get("intitule", ""),
        description=offer.get("description"),
        contract_type=offer.get("typeContrat"),
        contract_label=offer.get("typeContratLibelle"),
        work_time=offer.get("dureeTravailLibelleConverti"),
        experience_code=offer.get("experienceExige"),
        experience_label=offer.get("experienceLibelle"),
        rome_code=offer.get("romeCode"),
        location_label=lieu.get("libelle"),
        location_postal_code=lieu.get("codePostal"),
        location_lat=lieu.get("latitude"),
        location_lng=lieu.get("longitude"),
        company_name=entreprise.get("nom"),
        company_description=entreprise.get("description"),
        company_url=entreprise.get("url"),
        salary_label=salaire.get("libelle"),
        sector_label=offer.get("secteurActiviteLibelle"),
        naf_code=offer.get("codeNAF"),
        offer_url=contact.get("urlPostulation"),
        ft_published_at=offer.get("dateCreation"),
        ft_updated_at=offer.get("dateActualisation"),
        raw_data=offer,
        status="nouveau",
        last_seen_at=datetime.utcnow(),
    )


async def _save_new_offers(
    db: AsyncSession,
    scored_offers: list[dict],
) -> list[JobOffer]:
    """Sauvegarde les nouvelles offres en base (ignore les doublons)."""
    existing_result = await db.execute(select(JobOffer.ft_id))
    existing_ids = {row[0] for row in existing_result.fetchall()}

    new_offers = []
    for offer in scored_offers:
        if offer["id"] in existing_ids:
            # Mettre à jour last_seen_at pour les offres déjà connues
            await db.execute(
                select(JobOffer).where(JobOffer.ft_id == offer["id"])
            )
            continue

        job = _map_offer_to_model(offer)
        job.raw_data["_score"] = offer.get("_score", 0.0)
        db.add(job)
        new_offers.append(job)

    await db.commit()
    for job in new_offers:
        await db.refresh(job)

    logger.info(f"{len(new_offers)} nouvelle(s) offre(s) sauvegardée(s)")
    return new_offers


# ============================================================================
# Pipeline principal
# ============================================================================

async def run_pipeline(
    db: AsyncSession,
    region: Optional[str] = None,
) -> dict:
    """
    Pipeline complet :
    1. Construction du profil depuis la BDD
    2. Prédiction codes ROME via ROMEO
    3. Collecte des offres France Travail
    4. Scoring BM25 + embeddings + reranker
    5. Mise à jour des statuts existants
    6. Sauvegarde des nouvelles offres

    Note : l'enrichissement Crew est déclenché manuellement
    via POST /jobs/{id}/enrich depuis le frontend.

    Returns:
        {"message": str, "offers_collected": int, "offers_scored": int, "offers_enriched": int}
    """
    logger.info("=== Démarrage du pipeline Jobs ===")
    start = datetime.utcnow()

    # 1. Profil
    profile_text = await build_profile_text(db)

    # 2. Codes ROME
    rome_codes = await _get_rome_codes(profile_text)
    if not rome_codes:
        logger.warning("Aucun code ROME obtenu, pipeline arrêté")
        return {
            "message": "Aucun code ROME prédit",
            "offers_collected": 0,
            "offers_scored": 0,
            "offers_enriched": 0,
        }

    # 3. Collecte
    raw_offers = await search_offers(
        rome_codes=rome_codes,
        region=region or ft.DEFAULT_REGION,
        range_start=ft.OFFRES_RANGE_START,
        range_end=ft.OFFRES_MAX_RESULTS - 1,
    )

    if not raw_offers:
        logger.info("Aucune offre collectée")
        return {
            "message": "Aucune offre collectée",
            "offers_collected": 0,
            "offers_scored": 0,
            "offers_enriched": 0,
        }

    # 4. Scoring
    scored_offers = await score_and_filter_offers(raw_offers, db)

    # 5. Mise à jour statuts
    active_ft_ids = {o["id"] for o in raw_offers}
    await _update_statuses(db, active_ft_ids)

    # 6. Sauvegarde nouvelles offres
    new_offers = await _save_new_offers(db, scored_offers)

    duration = (datetime.utcnow() - start).seconds
    logger.info(
        f"=== Pipeline terminé en {duration}s : "
        f"{len(raw_offers)} collectées, "
        f"{len(scored_offers)} scorées, "
        f"{len(new_offers)} nouvelles ==="
    )

    return {
        "message": f"Pipeline terminé en {duration}s",
        "offers_collected": len(raw_offers),
        "offers_scored": len(scored_offers),
        "offers_enriched": len(new_offers),
    }


# ============================================================================
# Scheduler 3x/jour (matin, après-midi, fin de journée)
# ============================================================================

async def schedule_pipeline() -> None:
    """
    Fonction appelée par le scheduler APScheduler.
    Crée sa propre session DB indépendante.
    """
    logger.info("Scheduler : déclenchement automatique du pipeline")
    async with AsyncSessionLocal() as db:
        try:
            await run_pipeline(db=db)
        except Exception as e:
            logger.error(f"Erreur pipeline schedulé : {e}")
import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core import france_travail_config as ft
from app.models.job_offer import JobOffer
from app.models.job_enriched import JobEnriched
from app.services.france_travail_client import predict_rome_codes, search_offers, search_offers_by_keywords
from app.services.job_scoring import score_and_filter_offers
from app.services.job_profile import build_profile_text, build_rome_codes

logger = logging.getLogger(__name__)


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
        select(JobOffer).where(JobOffer.status.notin_(["ferme", "postule", "enregistre", "manuel"]))
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
        rome_libelle=offer.get("_rome_libelle"),
        rome_source_intitule=offer.get("_rome_source_intitule"),
        source_branch=offer.get("_source_branch"),
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
        # ft_published_at=offer.get("dateCreation"),
        # ft_updated_at=offer.get("dateActualisation"),
        ft_published_at=datetime.fromisoformat(offer["dateCreation"].replace("Z", "+00:00")) if offer.get("dateCreation") else None,
        ft_updated_at=datetime.fromisoformat(offer["dateActualisation"].replace("Z", "+00:00")) if offer.get("dateActualisation") else None,
        raw_data=offer,
        status="nouveau",
        last_seen_at=datetime.utcnow(),
    )


async def _save_new_offers(
    db: AsyncSession,
    scored_offers: list[dict],
) -> list[JobOffer]:
    """
    Sauvegarde les nouvelles offres en base.
    Met à jour label et score si l'offre existe déjà avec un label inférieur.
    """
    existing_result = await db.execute(
        select(JobOffer).where(
            JobOffer.ft_id.in_([o["id"] for o in scored_offers])
        )
    )
    existing_map = {job.ft_id: job for job in existing_result.scalars().all()}

    # Priorité des labels pour comparaison
    label_rank = {"basique": 0, "medium": 1, "priorité": 2}

    new_offers = []
    for offer in scored_offers:
        label = offer.get("_label", "basique")
        score = offer.get("_score", 0.0)

        if offer["id"] in existing_map:
            # Mise à jour si label amélioré
            existing = existing_map[offer["id"]]
            current_rank = label_rank.get(existing.label or "basique", 0)
            new_rank = label_rank.get(label, 0)
            if new_rank > current_rank:
                existing.label = label
                existing.score = score
                existing.last_seen_at = datetime.utcnow()
                logger.info(
                    f"Label mis à jour pour {offer['id']} : "
                    f"{existing.label} → {label}"
                )
            continue

        job = _map_offer_to_model(offer)
        job.label = label
        job.score = score
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
    2. Codes ROME via job_profile (Mistral → ROMEO par expérience)
    3. Collecte paginée jusqu'à OFFRES_NEW_TARGET nouvelles offres
    4. Scoring BM25 + embeddings + reranker → labels basique/medium/priorité
    5. Mise à jour statuts existants
    6. Sauvegarde / mise à jour label si amélioré
    """
    logger.info("=== Démarrage du pipeline Jobs ===")
    start = datetime.utcnow()

    # 1. Profil
    profile_text = await build_profile_text(db)

    # 2. Codes ROME
    rome_map = await build_rome_codes(db)
    if not rome_map:
        logger.warning("Aucun code ROME obtenu, pipeline arrêté")
        return {
            "message": "Aucun code ROME prédit",
            "offers_collected": 0,
            "offers_scored": 0,
            "offers_enriched": 0,
        }
    rome_codes = list(rome_map.keys())

    target_per_branch = ft.OFFRES_NEW_TARGET // 2

    # 3. Collecte paginée jusqu'à target_per_branch  nouvelles offres
    existing_result = await db.execute(select(JobOffer.ft_id))
    existing_ids = {row[0] for row in existing_result.fetchall()}

    all_raw_offers = []
    new_count = 0
    range_size = 100
    now = datetime.utcnow()

    # Génération des tranches de dates (du plus récent au plus ancien)
    tranches = []
    for i in range(0, ft.OFFRES_FENETRE_JOURS, ft.OFFRES_TRANCHE_JOURS):
        max_date = now - timedelta(days=i)
        min_date = now - timedelta(days=i + ft.OFFRES_TRANCHE_JOURS)
        tranches.append((
            min_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            max_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        ))

    for min_date, max_date in tranches:
        if new_count >= target_per_branch :
            logger.info(f"Objectif {target_per_branch } nouvelles offres atteint")
            break

        range_start = 0
        logger.info(f"Tranche {min_date} → {max_date}")

        while new_count < target_per_branch:
            batch = await search_offers(
                rome_codes=rome_codes,
                region=region or ft.DEFAULT_REGION,
                range_start=range_start,
                range_end=range_start + range_size - 1,
                min_creation_date=min_date,
                max_creation_date=max_date,
            )

            if not batch:
                logger.info(f"Tranche épuisée à range {range_start}")
                break

            for offer in batch:
                if offer.get("romeCode") in rome_map:
                    offer["_rome_source_intitule"] = rome_map[offer["romeCode"]]["intitule"]
                    offer["_rome_libelle"] = rome_map[offer["romeCode"]]["libelle"]
                    offer["_source_branch"] = "rome"

            all_raw_offers.extend(batch)
            new_in_batch = sum(1 for o in batch if o["id"] not in existing_ids)
            new_count += new_in_batch
            logger.info(
                f"Range {range_start}-{range_start + range_size - 1} : "
                f"{len(batch)} offres, {new_in_batch} nouvelles "
                f"(total nouvelles : {new_count}/{target_per_branch})"
            )

            if len(batch) < range_size:
                logger.info(f"Dernière page de la tranche atteinte")
                break

            range_start += range_size

    # Filtre rome_map appliqué sur le bras ROME uniquement
    all_raw_offers = [
        o for o in all_raw_offers
        if o.get("romeCode") in rome_map
    ]
    logger.info(f"{len(all_raw_offers)} offre(s) bras ROME après filtre rome_map")

    # Bras 2 — Collecte par intitulés Mistral (motsCles)
    intitules = list({v["intitule"] for v in rome_map.values()})
    existing_ft_ids = {o["id"] for o in all_raw_offers}
    kw_new_count = 0

    for min_date, max_date in tranches:
        if kw_new_count >= target_per_branch:
            logger.info(f"Objectif motsCles {target_per_branch} nouvelles offres atteint")
            break

        for intitule in intitules:
            if kw_new_count >= target_per_branch:
                break

            kw_batch = await search_offers_by_keywords(
                keywords=intitule,
                region=region or ft.DEFAULT_REGION,
                range_start=0,
                range_end=99,
                min_creation_date=min_date,
                max_creation_date=max_date,
            )
            for offer in kw_batch:
                if offer["id"] not in existing_ft_ids:
                    offer["_rome_source_intitule"] = intitule
                    offer["_rome_libelle"] = offer.get("romeLibelle")
                    offer["_source_branch"] = "mots_cles"
                    all_raw_offers.append(offer)
                    existing_ft_ids.add(offer["id"])
                    kw_new_count += 1

    logger.info(f"{len(all_raw_offers)} offre(s) après fusion ROME + motsCles")

    if not all_raw_offers:
        logger.info("Aucune offre collectée")
        return {
            "message": "Aucune offre collectée",
            "offers_collected": 0,
            "offers_scored": 0,
            "offers_enriched": 0,
        }

    # 5. Mise à jour statuts
    active_ft_ids = {o["id"] for o in all_raw_offers}

    

    if not all_raw_offers:
        logger.info("Aucune offre après filtre rome_map")
        return {
            "message": "Aucune offre après filtre rome_map",
            "offers_collected": 0,
            "offers_scored": 0,
            "offers_enriched": 0,
        }

    all_raw_offers = [
        o for o in all_raw_offers
        if o["id"] not in existing_ids
    ]
    logger.info(f"{len(all_raw_offers)} offre(s) inconnues à scorer")

    if not all_raw_offers:
        logger.info("Aucune nouvelle offre à scorer")
        return {
            "message": "Aucune nouvelle offre à scorer",
            "offers_collected": len(active_ft_ids),
            "offers_scored": 0,
            "offers_enriched": 0,
        }

    # 4. Scoring
    scored_offers = await score_and_filter_offers(all_raw_offers, db)

    # Sélection des 5 meilleures offres par priorité de label
    label_rank = {"priorité": 2, "medium": 1, "basique": 0}
    scored_offers.sort(key=lambda o: label_rank.get(o.get("_label", "basique"), 0), reverse=True)
    # scored_offers = scored_offers[:ft.TOP_OFFER_K]
    scored_offers = _select_top_offers(scored_offers, ft.TOP_OFFER_K)
    logger.info(
        f"Offres retenues pour sauvegarde : "
        f"{sum(1 for o in scored_offers if o.get('_label') == 'priorité')} priorité, "
        f"{sum(1 for o in scored_offers if o.get('_label') == 'medium')} medium, "
        f"{sum(1 for o in scored_offers if o.get('_label') == 'basique')} basique"
    )
    
    await _update_statuses(db, active_ft_ids)

    # 6. Sauvegarde
    new_offers = await _save_new_offers(db, scored_offers)

    duration = (datetime.utcnow() - start).seconds
    logger.info(
        f"=== Pipeline terminé en {duration}s : "
        f"{len(all_raw_offers)} collectées, "
        f"{len(scored_offers)} scorées, "
        f"{len(new_offers)} sauvegardées ==="
    )

    return {
        "message": f"Pipeline terminé en {duration}s",
        "offers_collected": len(all_raw_offers),
        "offers_scored": len(scored_offers),
        "offers_enriched": len(new_offers),
    }

def _select_top_offers(scored_offers: list[dict], top_k: int) -> list[dict]:
    """
    Sélectionne top_k offres en respectant :
    - Priorité des tiers : priorité → medium → basique
    - Distribution proportionnelle rome/mots_cles par tier
    - Rome favorisé à l'arrondi (ceil)
    - Slots non remplis dans un tier récupérés par le tier suivant
    """
    import math

    tiers = ["priorité", "medium", "basique"]
    by_tier = {
        tier: {
            "rome":      [o for o in scored_offers if o.get("_label") == tier and o.get("_source_branch") == "rome"],
            "mots_cles": [o for o in scored_offers if o.get("_label") == tier and o.get("_source_branch") == "mots_cles"],
        }
        for tier in tiers
    }

    selected = []
    remaining_slots = top_k

    for tier in tiers:
        if remaining_slots <= 0:
            break

        rome_pool     = by_tier[tier]["rome"]
        mots_cles_pool = by_tier[tier]["mots_cles"]
        total_in_tier  = len(rome_pool) + len(mots_cles_pool)

        if total_in_tier == 0:
            continue

        slots = min(remaining_slots, total_in_tier)
        ratio_rome = len(rome_pool) / total_in_tier

        # Rome favorisé à l'arrondi (ceil)
        slots_rome      = min(math.ceil(slots * ratio_rome), len(rome_pool))
        slots_mots_cles = min(slots - slots_rome, len(mots_cles_pool))

        # Récupération des slots non remplis par l'autre source
        if slots_rome + slots_mots_cles < slots:
            deficit = slots - slots_rome - slots_mots_cles
            if slots_rome < len(rome_pool):
                slots_rome += min(deficit, len(rome_pool) - slots_rome)
            elif slots_mots_cles < len(mots_cles_pool):
                slots_mots_cles += min(deficit, len(mots_cles_pool) - slots_mots_cles)

        selected.extend(rome_pool[:slots_rome])
        selected.extend(mots_cles_pool[:slots_mots_cles])
        remaining_slots -= (slots_rome + slots_mots_cles)

        logger.info(
            f"Tier '{tier}' : {slots_rome} rome, {slots_mots_cles} mots_cles sélectionnés"
        )

    return selected


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
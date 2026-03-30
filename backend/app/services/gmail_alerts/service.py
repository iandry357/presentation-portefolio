"""
GmailAlertsService — orchestrateur principal.
Coordonne : GmailReader → ParserRegistry → déduplication → insertion.
Appelé par le scheduler. Aucune dépendance frontend.
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.job_offer import JobOffer
from .reader import GmailReader
from .registry import ParserRegistry, SENDER_MAP
from .base_parser import OffreNormalisee

logger = logging.getLogger(__name__)

MAX_RESULTS_PER_SOURCE = 5


class GmailAlertsService:

    def __init__(self):
        self.reader = GmailReader()
        self.registry = ParserRegistry()

    async def run(self, db: AsyncSession) -> dict:
        """
        Parcourt toutes les sources, parse les emails, insère les offres nouvelles.
        Retourne un résumé {inserted, skipped, errors}.
        """
        inserted = 0
        skipped = 0
        errors = 0

        for sender in SENDER_MAP.keys():
            logger.info(f"[GmailAlertsService] Traitement source : {sender}")
            try:
                emails = self.reader.fetch_emails(sender, MAX_RESULTS_PER_SOURCE)
                for (sender_email, email_date, html) in emails:
                    offers = self.registry.parse(sender_email, html, email_date)
                    for offre in offers:
                        try:
                            result = await self._insert_if_new(db, offre)
                            if result:
                                inserted += 1
                            else:
                                skipped += 1
                        except Exception as e:
                            logger.error(f"[GmailAlertsService] Erreur insertion : {e}", exc_info=True)
                            errors += 1
            except Exception as e:
                logger.error(f"[GmailAlertsService] Erreur source {sender} : {e}", exc_info=True)
                errors += 1

        summary = {"inserted": inserted, "skipped": skipped, "errors": errors}
        logger.info(f"[GmailAlertsService] Terminé : {summary}")
        return summary

    async def _insert_if_new(self, db: AsyncSession, offre: OffreNormalisee) -> bool:
        """
        Insère l'offre si elle n'existe pas encore en base.
        Déduplication :
          - Offre FT email  → sur ft_id
          - Offre externe   → sur offer_url
        Retourne True si insérée, False si déjà présente.
        """
        if offre.ft_id:
            result = await db.execute(
                select(JobOffer).where(JobOffer.ft_id == offre.ft_id)
            )
        else:
            result = await db.execute(
                select(JobOffer).where(
                    JobOffer.ft_id.is_(None),
                    JobOffer.offer_url == offre.offer_url,
                )
            )

        exists = result.scalar_one_or_none()
        if exists:
            return False

        raw_data = {
            "intitule":           offre.title,
            "entreprise":         {"nom": offre.company} if offre.company else {},
            "lieuTravail":        {"libelle": offre.location} if offre.location else {},
            "typeContratLibelle": offre.contract,
            "description":        offre.description_excerpt,
        }

        job = JobOffer(
            ft_id=offre.ft_id,
            offer_url=offre.offer_url,
            title=offre.title,
            company_name=offre.company,
            location_label=offre.location,
            contract_type=offre.contract,
            salary_label=offre.salary_label,
            source_offer=offre.source_offer,
            source_branch=offre.source_branch,
            ft_published_at=offre.email_date,
            raw_data=raw_data,
            status="nouveau",
            label="basique",
            score=None,
        )

        db.add(job)
        await db.commit()
        await db.refresh(job)
        return True
"""
GmailSyncService — orchestrateur principal Gmail → BigQuery.
Adapté du backend : synchrone, sans FastAPI, sans PostgreSQL.
Déduplication BigQuery sur id_unique (même pattern que sync.py France Travail).
"""

import logging
import os
from datetime import datetime, timezone

from google.cloud import bigquery
from google.cloud.exceptions import NotFound

from .reader import GmailReader
from .registry import ParserRegistry, SENDER_MAP
from .base_parser import OffreNormalisee

logger = logging.getLogger(__name__)

MAX_RESULTS_PER_SOURCE = 10


# ─────────────────────────────────────────────
# Normalisation OffreNormalisee → ligne BigQuery
# ─────────────────────────────────────────────

def _build_row(offre: OffreNormalisee) -> dict:
    source_key = offre.source_offer
    id_source  = offre.ft_id or offre.offer_url or ""
    return {
        "id_unique":                 f"{source_key}_{id_source}",
        "source":                    source_key,
        "id_source":                 id_source,
        "date_publication":          offre.email_date.date().isoformat(),
        "date_collecte":             datetime.now(timezone.utc).isoformat(),
        "titre":                     offre.title,
        "description":               offre.description_excerpt,
        "entreprise_nom":            offre.company,
        "localisation_libelle":      offre.location,
        "localisation_commune":      None,
        "localisation_departement":  None,
        "localisation_lat":          None,
        "localisation_lng":          None,
        "type_contrat":              offre.contract,
        "type_contrat_libelle":      None,
        "experience_libelle":        None,
        "salaire_libelle":           offre.salary_label,
        "salaire_min":               None,
        "salaire_max":               None,
        "salaire_present":           offre.salary_label is not None,
        "code_rome":                 None,
        "libelle_rome":              None,
        "secteur_activite":          None,
        "secteur_activite_libelle":  None,
        "naf_code":                  None,
        "competences":               [],
        "url_offre":                 offre.offer_url,
        "alternance":                None,
        "recherche_mot_cle":         offre.recherche_mot_cle,
        "recherche_localisation":    offre.recherche_localisation,
    }


# ─────────────────────────────────────────────
# Insertion idempotente BigQuery
# ─────────────────────────────────────────────

def _insert_rows(
    bq_client: bigquery.Client,
    table_ref: str,
    rows: list[dict],
) -> dict:
    """
    Insère les lignes dans BigQuery après déduplication sur id_unique.
    Même pattern que sync.py France Travail.
    Retourne {inserted, skipped, errors}.
    """
    if not rows:
        return {"inserted": 0, "skipped": 0, "errors": 0}

    ids     = [r["id_unique"] for r in rows]
    ids_str = ", ".join(f"'{i}'" for i in ids)
    query   = f"""
        SELECT id_unique
        FROM `{table_ref}`
        WHERE id_unique IN ({ids_str})
    """

    try:
        existing = {row.id_unique for row in bq_client.query(query).result()}
    except NotFound:
        existing = set()
    except Exception as e:
        logger.error(f"[GmailSyncService] Erreur requête déduplication : {e}", exc_info=True)
        return {"inserted": 0, "skipped": 0, "errors": 1}

    new_rows = [r for r in rows if r["id_unique"] not in existing]
    skipped  = len(rows) - len(new_rows)

    if not new_rows:
        logger.info(f"[GmailSyncService] Lot ignoré — {skipped} offre(s) déjà présente(s)")
        return {"inserted": 0, "skipped": skipped, "errors": 0}

    errors = bq_client.insert_rows_json(table_ref, new_rows)
    if errors:
        logger.error(f"[GmailSyncService] Erreurs insertion BigQuery : {errors}")
        return {"inserted": 0, "skipped": skipped, "errors": len(errors)}

    logger.info(
        f"[GmailSyncService] {len(new_rows)} insérée(s), "
        f"{skipped} doublon(s) ignoré(s)"
    )
    return {"inserted": len(new_rows), "skipped": skipped, "errors": 0}


# ─────────────────────────────────────────────
# Orchestrateur principal
# ─────────────────────────────────────────────

class GmailSyncService:

    def __init__(self):
        self.reader   = GmailReader()
        self.registry = ParserRegistry()

    def run(self, bq_client: bigquery.Client, table_ref: str) -> dict:
        """
        Parcourt toutes les sources, parse les emails,
        déduplique et insère dans BigQuery.
        Retourne un résumé {inserted, skipped, errors}.
        """
        all_offers: dict[str, OffreNormalisee] = {}
        errors = 0

        # ── Collecte + parsing ──────────────────────────────────
        for sender in SENDER_MAP.keys():
            logger.info(f"[GmailSyncService] Traitement source : {sender}")
            try:
                emails = self.reader.fetch_emails(sender, MAX_RESULTS_PER_SOURCE)
                for (sender_email, email_date, html) in emails:
                    offers = self.registry.parse(sender_email, html, email_date)
                    for offre in offers:
                        # Déduplication en mémoire sur id_unique
                        key = offre.ft_id or offre.offer_url
                        if key and key not in all_offers:
                            all_offers[key] = offre
            except Exception as e:
                logger.error(
                    f"[GmailSyncService] Erreur source {sender} : {e}",
                    exc_info=True,
                )
                errors += 1

        logger.info(
            f"[GmailSyncService] {len(all_offers)} offre(s) collectée(s) "
            f"après déduplication mémoire"
        )

        # ── Normalisation ───────────────────────────────────────
        rows = [_build_row(o) for o in all_offers.values()]

        # ── Insertion BigQuery ──────────────────────────────────
        result = _insert_rows(bq_client, table_ref, rows)
        result["errors"] += errors

        logger.info(f"[GmailSyncService] Terminé : {result}")
        return result
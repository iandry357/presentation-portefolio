"""
Collecteur des offres déjà collectées — Beelix.
Lit le mart Top Offres (offres représentantes, fenêtre glissante), le code NAF de entreprises_ref
et la description de stg_offres. Lecture seule, compte de service SG.
"""
import logging
from typing import Dict, List

from google.cloud import bigquery
from google.oauth2 import service_account

from pipeline.config import (
    BQ_SRC_ENTREPRISES,
    BQ_SRC_MART,
    BQ_SRC_OFFRES,
    FENETRE_JOURS,
    GCP_PROJECT_ID,
    GCP_SA_KEY_PATH,
)

logger = logging.getLogger(__name__)

# Offres représentantes de la fenêtre ; les offres masquées par un filtre dur (stage, alternance,
# hors IDF) sont exclues, celles masquées pour score bas sont gardées (score propre au profil candidat).
QUERY = f"""
    SELECT
        m.id_unique,
        m.source,
        m.titre,
        m.entreprise_nom,
        m.entreprise_normalise,
        m.localisation_libelle,
        m.type_contrat_libelle,
        m.salaire_libelle,
        m.url_offre,
        m.date_publication,
        m.date_collecte,
        m.type_entreprise,
        m.secteur AS secteur_libre,
        r.naf_code,
        r.naf_libelle,
        o.description
    FROM `{BQ_SRC_MART}` AS m
    LEFT JOIN `{BQ_SRC_ENTREPRISES}` AS r
        ON r.nom_normalise = m.entreprise_normalise
    LEFT JOIN `{BQ_SRC_OFFRES}` AS o
        ON o.id_unique = m.id_unique
    WHERE m.date_collecte >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @jours DAY)
      AND m.id_unique = m.groupe_doublon
      AND (m.motif_masque IS NULL OR m.motif_masque = 'score_bas')
"""


def _get_client() -> bigquery.Client:
    """Client BigQuery avec le compte de service SG."""
    credentials = service_account.Credentials.from_service_account_file(
        str(GCP_SA_KEY_PATH),
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(project=GCP_PROJECT_ID, credentials=credentials)


def collect() -> List[Dict]:
    """
    Lit les offres de la fenêtre glissante.

    Returns:
        Une ligne par offre (dictionnaire), dates converties en texte ISO.
    """
    client = _get_client()
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("jours", "INT64", FENETRE_JOURS)]
    )
    rows = client.query(QUERY, job_config=job_config).result()

    offres = []
    for row in rows:
        offre = dict(row.items())
        offre["date_publication"] = offre["date_publication"].isoformat() if offre["date_publication"] else None
        offre["date_collecte"] = offre["date_collecte"].isoformat() if offre["date_collecte"] else None
        offres.append(offre)

    logger.info(f"✅ Offres BigQuery — {len(offres)} offres sur {FENETRE_JOURS} jours")
    return offres

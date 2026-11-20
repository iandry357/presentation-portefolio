"""
Collecteur des offres Wavestone déjà collectées.
Lit le mart Top Offres (offres représentantes, fenêtre glissante) filtré sur les noms normalisés de Wavestone,
avec la description de stg_offres. Lecture seule, compte de service SG.
Score, liste et cible proche : pertinence des offres pour le profil candidat (vue Recrutement).
La raison du score (texte du LLM) n'est pas reprise : la page est publique.
"""
import logging
from typing import Dict, List

from google.cloud import bigquery
from google.oauth2 import service_account

from pipeline.config import (
    BQ_SRC_CIBLES,
    BQ_SRC_MART,
    BQ_SRC_OFFRES,
    FENETRE_JOURS,
    GCP_PROJECT_ID,
    GCP_SA_KEY_PATH,
    WAVESTONE_NOMS_NORMALISES,
)

logger = logging.getLogger(__name__)

# Offres représentantes de la fenêtre ; les offres masquées par un filtre dur (stage, alternance,
# hors IDF) sont exclues, celles masquées pour score bas sont gardées.
QUERY = f"""
    SELECT
        m.id_unique,
        m.source,
        m.titre,
        m.titre_normalise,
        m.entreprise_nom,
        m.localisation_libelle,
        m.type_contrat_libelle,
        m.salaire_libelle,
        m.url_offre,
        m.date_publication,
        m.date_collecte,
        m.score,
        m.categorie,
        m.cible_proche,
        c.intitule AS cible_intitule,
        m.liste,
        o.description
    FROM `{BQ_SRC_MART}` AS m
    LEFT JOIN `{BQ_SRC_OFFRES}` AS o
        ON o.id_unique = m.id_unique
    LEFT JOIN (
        SELECT cible_id, ANY_VALUE(intitule) AS intitule
        FROM `{BQ_SRC_CIBLES}`
        WHERE statut = 'validee'
        GROUP BY cible_id
    ) AS c
        ON c.cible_id = m.cible_proche
    WHERE m.date_collecte >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @jours DAY)
      AND m.id_unique = m.groupe_doublon
      AND (m.motif_masque IS NULL OR m.motif_masque = 'score_bas')
      AND m.entreprise_normalise IN UNNEST(@noms)
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
    Lit les offres Wavestone de la fenêtre glissante.

    Returns:
        Une ligne par offre (dictionnaire), dates converties en texte ISO.
    """
    client = _get_client()
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("jours", "INT64", FENETRE_JOURS),
            bigquery.ArrayQueryParameter("noms", "STRING", WAVESTONE_NOMS_NORMALISES),
        ]
    )
    rows = client.query(QUERY, job_config=job_config).result()

    offres = []
    for row in rows:
        offre = dict(row.items())
        offre["date_publication"] = offre["date_publication"].isoformat() if offre["date_publication"] else None
        offre["date_collecte"] = offre["date_collecte"].isoformat() if offre["date_collecte"] else None
        offres.append(offre)

    logger.info(f"✅ Offres BigQuery — {len(offres)} offres Wavestone sur {FENETRE_JOURS} jours")
    return offres

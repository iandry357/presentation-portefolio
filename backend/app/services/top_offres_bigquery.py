"""
Lecture BigQuery du MVP Top Offres (dataset top_offres).
Credentials lus depuis GCP_SERVICE_ACCOUNT_JSON_TOP_OFFRES (compte pipeline-top-offres).
Utilisé par le routeur backend/routers/top_offres.
"""

import json
import logging
from datetime import date, datetime
from typing import Optional

from google.cloud import bigquery
from google.oauth2 import service_account

from app.core.config import settings

logger = logging.getLogger(__name__)

# Paramètres
TABLE_STATS = "mart_stats"
LISTES_TOP = ["a_lire", "zone_grise", "masque"]
TABLE_CIBLES = "cibles"

# Colonnes de mart_top_du_jour renvoyées au routeur
COLONNES_TOP = [
    "id_unique", "groupe_doublon", "source", "titre", "titre_normalise",
    "entreprise_nom", "entreprise_normalise", "localisation_libelle",
    "type_contrat_libelle", "salaire_libelle", "url_offre", "date_publication",
    "date_collecte", "score", "categorie", "raison", "alertes", "cible_proche",
    "similarite", "liste", "motif_masque", "date_run", "secteur", "type_entreprise",
    "origine_entreprise", "entreprise_exclue",
]

# Colonnes renvoyées pour les offres d'une entreprise
COLONNES_OFFRE_ENTREPRISE = [
    "id_unique", "source", "titre", "localisation_libelle", "type_contrat_libelle",
    "salaire_libelle", "url_offre", "date_publication", "date_collecte", "score",
    "categorie", "liste", "raison",
]


def _get_bq_client() -> bigquery.Client:
    """Construit le client BigQuery depuis les credentials JSON du compte Top Offres."""
    if not settings.GCP_SERVICE_ACCOUNT_JSON_TOP_OFFRES:
        raise RuntimeError("GCP_SERVICE_ACCOUNT_JSON_TOP_OFFRES non configuré")

    sa_info = json.loads(settings.GCP_SERVICE_ACCOUNT_JSON_TOP_OFFRES)
    credentials = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/bigquery"],
    )
    return bigquery.Client(
        project=settings.BQ_PROJECT_ID,
        credentials=credentials,
    )


def _table(nom: str) -> str:
    return f"`{settings.BQ_PROJECT_ID}.{settings.BQ_DATASET_TOP_OFFRES}.{nom}`"


def _serialiser(lignes) -> list[dict]:
    """Lignes BigQuery -> dicts ; dates et horodatages en chaînes ISO (sérialisation JSON)."""
    resultat = []
    for ligne in lignes:
        donnees = dict(ligne)
        for cle, valeur in list(donnees.items()):
            if isinstance(valeur, (date, datetime)):
                donnees[cle] = valeur.isoformat()
        resultat.append(donnees)
    return resultat


def fetch_top_candidates(jours: int, inclure_exclues: bool = False) -> list[dict]:
    """
    Offres candidates au top du jour : listes a_lire, zone_grise et masque de mart_top_du_jour,
    collectées dans les `jours` derniers jours. Triées score DESC, similarite DESC.
    Le retrait des offres déjà traitées et la limite par entreprise sont faits par le routeur.
    """
    client = _get_bq_client()
    filtre_exclues = "" if inclure_exclues else "AND NOT COALESCE(entreprise_exclue, FALSE)"

    query = f"""
        SELECT {", ".join(COLONNES_TOP)}
        FROM {_table(settings.BQ_TABLE_TOP_DU_JOUR)}
        WHERE liste IN UNNEST(@listes)
          AND CAST(date_collecte AS DATE) >= DATE_SUB(CURRENT_DATE(), INTERVAL @jours DAY)
          {filtre_exclues}
        ORDER BY score DESC, similarite DESC, id_unique
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ArrayQueryParameter("listes", "STRING", LISTES_TOP),
        bigquery.ScalarQueryParameter("jours", "INT64", jours),
    ])
    lignes = _serialiser(client.query(query, job_config=job_config).result())

    logger.info(f"[top_offres_bigquery] {len(lignes)} candidates (jours={jours}, inclure_exclues={inclure_exclues})")
    return lignes


def fetch_stats(jours: int) -> list[dict]:
    """Statistiques publiques : lignes de mart_stats (format long) des `jours` derniers jours."""
    client = _get_bq_client()

    query = f"""
        SELECT jour, dimension, valeur, nb_offres
        FROM {_table(TABLE_STATS)}
        WHERE CAST(jour AS DATE) >= DATE_SUB(CURRENT_DATE(), INTERVAL @jours DAY)
        ORDER BY jour DESC, dimension, nb_offres DESC
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("jours", "INT64", jours),
    ])
    return _serialiser(client.query(query, job_config=job_config).result())


def fetch_cibles() -> dict[str, str]:
    """Intitulés des cibles validées : {cible_id: intitule} (libellés des graphiques)."""
    client = _get_bq_client()

    query = f"""
        SELECT cible_id, intitule
        FROM {_table(TABLE_CIBLES)}
        WHERE statut = 'validee'
    """
    return {ligne["cible_id"]: ligne["intitule"] for ligne in client.query(query).result()}


def fetch_offer(id_unique: str) -> Optional[dict]:
    """Une ligne de mart_top_du_jour pour un id_unique (None si absente)."""
    client = _get_bq_client()

    query = f"""
        SELECT {", ".join(COLONNES_TOP)}
        FROM {_table(settings.BQ_TABLE_TOP_DU_JOUR)}
        WHERE id_unique = @id_unique
        LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("id_unique", "STRING", id_unique),
    ])
    lignes = _serialiser(client.query(query, job_config=job_config).result())
    return lignes[0] if lignes else None


def fetch_entreprises(jours: int, inclure_exclues: bool = False) -> list[dict]:
    """
    Agrégat par entreprise des offres scorées de mart_top_du_jour sur les `jours` derniers jours.
    Une offre republiée (même groupe de doublons) ne compte qu'une fois ; les offres sans catégorie
    (écartées par un filtre dur : stage, alternance, hors Île-de-France) ne sont pas comptées.
    Filtres, tri et limite sont appliqués par le routeur (les types corrigés sont dans PostgreSQL).
    """
    client = _get_bq_client()
    filtre_exclues = "" if inclure_exclues else "AND NOT COALESCE(entreprise_exclue, FALSE)"

    query = f"""
        WITH groupes AS (
            SELECT
                entreprise_normalise,
                groupe_doublon,
                ARRAY_AGG(entreprise_nom IGNORE NULLS ORDER BY date_collecte DESC LIMIT 1)[SAFE_OFFSET(0)] AS entreprise_nom,
                ANY_VALUE(secteur) AS secteur,
                ANY_VALUE(naf_libelle) AS naf_libelle,
                ANY_VALUE(type_entreprise) AS type_entreprise,
                ANY_VALUE(entreprise_exclue) AS entreprise_exclue,
                ANY_VALUE(categorie) AS categorie,
                ANY_VALUE(liste) AS liste,
                MAX(score) AS score,
                MAX(date_collecte) AS date_collecte
            FROM {_table(settings.BQ_TABLE_TOP_DU_JOUR)}
            WHERE entreprise_normalise != ''
              AND categorie IS NOT NULL
              AND CAST(date_collecte AS DATE) >= DATE_SUB(CURRENT_DATE(), INTERVAL @jours DAY)
              {filtre_exclues}
            GROUP BY entreprise_normalise, groupe_doublon
        )
        SELECT
            entreprise_normalise,
            ARRAY_AGG(entreprise_nom IGNORE NULLS ORDER BY date_collecte DESC LIMIT 1)[SAFE_OFFSET(0)] AS entreprise_nom,
            ANY_VALUE(secteur) AS secteur,
            ANY_VALUE(naf_libelle) AS naf_libelle,
            ANY_VALUE(type_entreprise) AS type_entreprise,
            LOGICAL_OR(COALESCE(entreprise_exclue, FALSE)) AS entreprise_exclue,
            COUNT(*) AS nb_offres,
            COUNTIF(categorie = 'coeur') AS nb_coeur,
            COUNTIF(categorie = 'adjacent') AS nb_adjacent,
            COUNTIF(categorie = 'hors_cible') AS nb_hors_cible,
            COUNTIF(liste = 'a_lire') AS nb_a_lire,
            COUNTIF(liste = 'zone_grise') AS nb_zone_grise,
            MAX(score) AS score_max,
            ROUND(AVG(score), 1) AS score_moyen,
            MAX(date_collecte) AS derniere_offre
        FROM groupes
        GROUP BY entreprise_normalise
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("jours", "INT64", jours),
    ])
    lignes = _serialiser(client.query(query, job_config=job_config).result())

    logger.info(f"[top_offres_bigquery] {len(lignes)} entreprises (jours={jours}, inclure_exclues={inclure_exclues})")
    return lignes


def fetch_offres_entreprise(entreprise_normalise: str, jours: int) -> list[dict]:
    """Offres scorées d'une entreprise sur les `jours` derniers jours : une par groupe de doublons
    (la plus récemment collectée), triées score DESC puis date de collecte DESC."""
    client = _get_bq_client()

    query = f"""
        SELECT {", ".join(COLONNES_OFFRE_ENTREPRISE)}
        FROM {_table(settings.BQ_TABLE_TOP_DU_JOUR)}
        WHERE entreprise_normalise = @entreprise
          AND categorie IS NOT NULL
          AND CAST(date_collecte AS DATE) >= DATE_SUB(CURRENT_DATE(), INTERVAL @jours DAY)
        QUALIFY ROW_NUMBER() OVER (PARTITION BY groupe_doublon ORDER BY date_collecte DESC, id_unique) = 1
        ORDER BY score DESC, date_collecte DESC, id_unique
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("entreprise", "STRING", entreprise_normalise),
        bigquery.ScalarQueryParameter("jours", "INT64", jours),
    ])
    return _serialiser(client.query(query, job_config=job_config).result())

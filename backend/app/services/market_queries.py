"""
Catalogue des requêtes pré-enregistrées pour l'Observatoire Marché.
Seules les requêtes de ce catalogue sont exécutables — aucun Text-to-SQL exposé.

Socle commun (toutes sources) : Q01–Q07
Extensions FT API uniquement  : Q08–Q10
Requête signature              : Q11 — entreprises finales actives

Q01–Q10 interrogent les tables agrégées produites par dbt
(gcp/dbt_transformation/models/intermediate/) plutôt que offres_brutes
directement — réduit le volume scanné par requête.
Q11 reste sur offres_brutes : logique dynamique (score, exclusion
entreprises en temps réel) non pré-calculable par dbt.
"""

import logging
import os
from typing import Any

from google.cloud import bigquery

from .excluded_companies import get_excluded

from .bigquery_client import _get_bq_client

logger = logging.getLogger(__name__)

PROJECT  = os.environ.get("BQ_PROJECT_ID", "gen-lang-client-0989575872")
DATASET  = "emploi_marche"

TABLE                  = f"`{PROJECT}.{DATASET}.offres_brutes`"
TABLE_AGG_JOUR          = f"`{PROJECT}.{DATASET}.int_offres_agg_jour`"
TABLE_AGG_ENTREPRISE    = f"`{PROJECT}.{DATASET}.int_offres_agg_entreprise`"
TABLE_AGG_LOCALISATION  = f"`{PROJECT}.{DATASET}.int_offres_agg_localisation`"

MAX_SCAN = "1024MB"  # quota BigQuery par requête


# ── Helpers ───────────────────────────────────────────────────────────────────

def _periode_to_days(periode: str) -> int:
    return {"7j": 7, "30j": 30, "90j": 90}[periode]


def _source_filter(source: str) -> str:
    if source == "toutes":
        return ""
    return f"AND source = '{source}'"


def _run(sql: str) -> list[dict[str, Any]]:
    # client = bigquery.Client(project=PROJECT)
    client = _get_bq_client()
    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=1024 * 1024 * 1024,  # 1 GB
    )
    job = client.query(sql, job_config=job_config)
    rows = job.result()
    return [dict(row) for row in rows]


# ── Catalogue ─────────────────────────────────────────────────────────────────

CATALOGUE: dict[str, dict] = {
    "Q01": {
        "titre":       "Volume d'offres collectées dans le temps",
        "description": "Nombre d'offres par jour sur la période sélectionnée",
        "colonnes":    ["date_publication", "nb_offres"],
        "rendu":       "courbe",
    },
    "Q02": {
        "titre":       "Répartition par source",
        "description": "Nombre d'offres par plateforme source",
        "colonnes":    ["source", "nb_offres"],
        "rendu":       "camembert",
    },
    "Q03": {
        "titre":       "Top entreprises qui recrutent",
        "description": "Entreprises avec le plus d'offres publiées",
        "colonnes":    ["entreprise_nom", "nb_offres"],
        "rendu":       "barres_horizontales",
    },
    "Q04": {
        "titre":       "Top localisations",
        "description": "Villes et zones avec le plus d'offres",
        "colonnes":    ["localisation_libelle", "nb_offres"],
        "rendu":       "barres_horizontales",
    },
    "Q05": {
        "titre":       "Proportion d'offres avec salaire renseigné",
        "description": "Part des offres mentionnant un salaire",
        "colonnes":    ["salaire_present", "nb_offres", "pourcentage"],
        "rendu":       "indicateur",
    },
    "Q06": {
        "titre":       "Nouvelles offres aujourd'hui vs hier",
        "description": "Comparaison du volume de collecte sur 2 jours",
        "colonnes":    ["jour", "nb_offres"],
        "rendu":       "indicateur_comparatif",
    },
    "Q07": {
        "titre":       "Volume d'offres par source dans le temps",
        "description": "Évolution comparative des sources semaine par semaine",
        "colonnes":    ["semaine", "source", "nb_offres"],
        "rendu":       "courbe_multi",
    },
    # Extensions FT API uniquement
    "Q08": {
        "titre":       "Répartition par type de contrat",
        "description": "CDI / CDD / Freelance / Alternance — France Travail API uniquement",
        "colonnes":    ["type_contrat", "nb_offres"],
        "rendu":       "camembert",
        "source_requise": "france_travail_api",
    },
    "Q09": {
        "titre":       "Top codes ROME",
        "description": "Métiers les plus représentés — France Travail API uniquement",
        "colonnes":    ["code_rome", "libelle_rome", "nb_offres"],
        "rendu":       "barres_horizontales",
        "source_requise": "france_travail_api",
    },
    "Q10": {
        "titre":       "Répartition par département",
        "description": "Concentration géographique — France Travail API uniquement",
        "colonnes":    ["localisation_departement", "nb_offres"],
        "rendu":       "barres_horizontales",
        "source_requise": "france_travail_api",
    },
    # Requête signature
    "Q11": {
        "titre":       "Entreprises finales en recrutement actif data/IA",
        "description": "Entreprises non-ESN avec plusieurs postes data/IA ouverts sur la période",
        "colonnes":    ["entreprise_nom", "nb_titres_distincts", "nb_sources", "premiere_offre", "derniere_offre", "duree_jours", "score_signal"],
        "rendu":       "tableau",
    },
}


def get_catalogue() -> dict[str, dict]:
    return CATALOGUE


def execute_query(
    query_id: str,
    periode: str = "30j",
    source: str = "toutes",
) -> list[dict[str, Any]]:
    if query_id not in CATALOGUE:
        raise ValueError(f"query_id inconnu : {query_id}")

    meta = CATALOGUE[query_id]
    days = _periode_to_days(periode)
    src  = _source_filter(source)

    # Requêtes avec source imposée
    if "source_requise" in meta:
        src = f"AND source = '{meta['source_requise']}'"

    fn = _QUERIES.get(query_id)
    if not fn:
        raise NotImplementedError(f"Requête {query_id} non implémentée")

    sql = fn(days, src)
    logger.info(f"[MarketQueries] Exécution {query_id} — période={periode} source={source}")
    return _run(sql)


# ── SQL par query_id ──────────────────────────────────────────────────────────
# Q01-Q10 : lecture sur les tables agrégées dbt (int_offres_agg_*)
# Q11     : inchangée, lecture directe sur offres_brutes

def _q01(days: int, src: str) -> str:
    return f"""
    SELECT
      date_publication,
      SUM(nb_offres) AS nb_offres
    FROM {TABLE_AGG_JOUR}
    WHERE date_publication >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
      {src}
    GROUP BY date_publication
    ORDER BY date_publication ASC
    """

def _q02(days: int, src: str) -> str:
    return f"""
    SELECT
      source,
      SUM(nb_offres) AS nb_offres
    FROM {TABLE_AGG_JOUR}
    WHERE date_publication >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
      {src}
    GROUP BY source
    ORDER BY nb_offres DESC
    """

def _q03(days: int, src: str) -> str:
    return f"""
    SELECT
      entreprise_nom,
      SUM(nb_offres) AS nb_offres
    FROM {TABLE_AGG_ENTREPRISE}
    WHERE date_publication >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
      {src}
    GROUP BY entreprise_nom
    ORDER BY nb_offres DESC
    """

def _q04(days: int, src: str) -> str:
    return f"""
    SELECT
      localisation_libelle,
      SUM(nb_offres) AS nb_offres
    FROM {TABLE_AGG_LOCALISATION}
    WHERE date_publication >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
      {src}
    GROUP BY localisation_libelle
    ORDER BY nb_offres DESC
    """

def _q05(days: int, src: str) -> str:
    return f"""
    SELECT
      salaire_present,
      SUM(nb_offres) AS nb_offres,
      ROUND(SUM(nb_offres) * 100.0 / SUM(SUM(nb_offres)) OVER (), 1) AS pourcentage
    FROM {TABLE_AGG_JOUR}
    WHERE date_publication >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
      {src}
    GROUP BY salaire_present
    ORDER BY salaire_present DESC
    """

def _q06(days: int, src: str) -> str:
    return f"""
    SELECT
      CASE
        WHEN date_publication = CURRENT_DATE() THEN "aujourd'hui"
        WHEN date_publication = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY) THEN 'hier'
      END AS jour,
      SUM(nb_offres) AS nb_offres
    FROM {TABLE_AGG_JOUR}
    WHERE date_publication >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
      {src}
    GROUP BY date_publication
    ORDER BY date_publication DESC
    """

def _q07(days: int, src: str) -> str:
    return f"""
    SELECT
      DATE_TRUNC(date_publication, WEEK) AS semaine,
      source,
      SUM(nb_offres) AS nb_offres
    FROM {TABLE_AGG_JOUR}
    WHERE date_publication >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
      {src}
    GROUP BY semaine, source
    ORDER BY semaine ASC, nb_offres DESC
    """

def _q08(days: int, src: str) -> str:
    return f"""
    SELECT
      type_contrat,
      SUM(nb_offres) AS nb_offres
    FROM {TABLE_AGG_JOUR}
    WHERE date_publication >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
      AND source = 'france_travail_api'
    GROUP BY type_contrat
    ORDER BY nb_offres DESC
    """

def _q09(days: int, src: str) -> str:
    return f"""
    SELECT
      code_rome,
      libelle_rome,
      SUM(nb_offres) AS nb_offres
    FROM {TABLE_AGG_JOUR}
    WHERE date_publication >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
      AND source = 'france_travail_api'
      AND code_rome IS NOT NULL
    GROUP BY code_rome, libelle_rome
    ORDER BY nb_offres DESC
    """

def _q10(days: int, src: str) -> str:
    return f"""
    SELECT
      localisation_departement,
      SUM(nb_offres) AS nb_offres
    FROM {TABLE_AGG_JOUR}
    WHERE date_publication >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
      AND source = 'france_travail_api'
    GROUP BY localisation_departement
    ORDER BY nb_offres DESC
    """

def _q11(days: int, src: str) -> str:
    excluded = get_excluded()
    excl_sql = ""
    if excluded:
        escaped = [e.replace("'", "\\'") for e in excluded]
        liste   = ", ".join(f"'{e}'" for e in escaped)
        excl_sql = f"AND entreprise_nom NOT IN ({liste})"

    return f"""
    SELECT
      entreprise_nom,
      STRING_AGG(DISTINCT LOWER(TRIM(titre)), ' | ' ORDER BY LOWER(TRIM(titre))) AS titres,
      COUNT(DISTINCT LOWER(TRIM(titre))) AS nb_titres_distincts,
      COUNT(DISTINCT source) AS nb_sources,
      MIN(date_publication) AS premiere_offre,
      MAX(date_publication) AS derniere_offre,
      DATE_DIFF(MAX(date_publication), MIN(date_publication), DAY) AS duree_jours,
      ROUND(
        (COUNT(DISTINCT LOWER(TRIM(titre))) * 2)
        + (COUNT(DISTINCT source) * 3)
        + (DATE_DIFF(MAX(date_publication), MIN(date_publication), DAY) / 5)
      , 1) AS score_signal
    FROM {TABLE}
    WHERE
      date_publication >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
      AND entreprise_nom IS NOT NULL
      AND entreprise_nom != ''
      {excl_sql}
      AND (
        LOWER(titre) LIKE '%data%'
        OR LOWER(titre) LIKE '% ia %'
        OR LOWER(titre) LIKE '% ai %'
        OR LOWER(titre) LIKE '%machine learning%'
        OR LOWER(titre) LIKE '%intelligence artificielle%'
        OR LOWER(titre) LIKE '%artificial intelligence%'
      )
      AND titre NOT LIKE '%onsult%'
    GROUP BY entreprise_nom
    ORDER BY duree_jours DESC, nb_titres_distincts DESC
    """


_QUERIES = {
    "Q01": _q01, "Q02": _q02, "Q03": _q03, "Q04": _q04,
    "Q05": _q05, "Q06": _q06, "Q07": _q07, "Q08": _q08,
    "Q09": _q09, "Q10": _q10, "Q11": _q11,
}
"""
BigQueryClient — lecture paginée des offres depuis BigQuery.
Credentials lus depuis GCP_SERVICE_ACCOUNT_JSON (variable d'env).
Utilisé par le router /explore.
"""

import json
import logging
from typing import Optional

from google.cloud import bigquery
from google.oauth2 import service_account

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_bq_client() -> bigquery.Client:
    """Construit le client BigQuery depuis les credentials JSON."""
    if not settings.GCP_SERVICE_ACCOUNT_JSON:
        raise RuntimeError("GCP_SERVICE_ACCOUNT_JSON non configuré")

    sa_info = json.loads(settings.GCP_SERVICE_ACCOUNT_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        sa_info,
        # scopes=["https://www.googleapis.com/auth/bigquery.readonly"],
        scopes=["https://www.googleapis.com/auth/bigquery"],
    )
    return bigquery.Client(
        project=settings.BQ_PROJECT_ID,
        credentials=credentials,
    )


TABLE_REF = "{project}.{dataset}.{table}".format(
    project="{BQ_PROJECT_ID}",
    dataset="{BQ_DATASET}",
    table="{BQ_TABLE}",
)


def _build_table_ref() -> str:
    return (
        f"`{settings.BQ_PROJECT_ID}"
        f".{settings.BQ_DATASET}"
        f".{settings.BQ_TABLE}`"
    )


def fetch_offers(
    page: int = 1,
    page_size: int = 10,
    source: Optional[str] = None,
    type_contrat: Optional[str] = None,
    localisation_libelle: Optional[str] = None,
    periode_jours: Optional[int] = None,
    titre: Optional[str] = None,
    entreprise_nom: Optional[str] = None,
) -> dict:
    """
    Lecture paginée des offres depuis BigQuery avec filtres optionnels.
    Retourne {total, page, page_size, offers}.
    """
    client = _get_bq_client()
    table = _build_table_ref()

    # Construction des filtres WHERE
    conditions = []
    params = []

    if source:
        conditions.append("source = @source")
        params.append(bigquery.ScalarQueryParameter("source", "STRING", source))

    if type_contrat:
        conditions.append("type_contrat = @type_contrat")
        params.append(bigquery.ScalarQueryParameter("type_contrat", "STRING", type_contrat))

    if localisation_libelle:
        conditions.append("localisation_libelle = @localisation_libelle")
        params.append(bigquery.ScalarQueryParameter("localisation_libelle", "STRING", localisation_libelle))

    if periode_jours:
        conditions.append(
            "date_publication >= DATE_SUB(CURRENT_DATE(), INTERVAL @periode_jours DAY)"
        )
        params.append(bigquery.ScalarQueryParameter("periode_jours", "INT64", periode_jours))

    if titre:
        conditions.append("LOWER(titre) LIKE LOWER(@titre)")
        params.append(bigquery.ScalarQueryParameter("titre", "STRING", f"%{titre}%"))

    if entreprise_nom:
        conditions.append("entreprise_nom = @entreprise_nom")
        params.append(bigquery.ScalarQueryParameter("entreprise_nom", "STRING", entreprise_nom))

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Requête count
    count_query = f"SELECT COUNT(*) as total FROM {table} {where_clause}"
    count_job_config = bigquery.QueryJobConfig(query_parameters=params)
    count_result = client.query(count_query, job_config=count_job_config).result()
    total = next(count_result).total

    # Requête paginée
    offset = (page - 1) * page_size
    data_query = f"""
        SELECT
            id_unique,
            source,
            titre,
            entreprise_nom,
            localisation_libelle,
            type_contrat,
            type_contrat_libelle,
            experience_libelle,
            salaire_libelle,
            salaire_min,
            salaire_max,
            salaire_present,
            code_rome,
            libelle_rome,
            url_offre,
            date_publication,
            date_collecte
        FROM {table}
        {where_clause}
        ORDER BY date_publication DESC, id_unique ASC
        LIMIT @page_size OFFSET @offset
    """

    data_params = params + [
        bigquery.ScalarQueryParameter("page_size", "INT64", page_size),
        bigquery.ScalarQueryParameter("offset", "INT64", offset),
    ]
    data_job_config = bigquery.QueryJobConfig(query_parameters=data_params)
    rows = client.query(data_query, job_config=data_job_config).result()

    offers = [dict(row) for row in rows]

    # Conversion date → string pour sérialisation JSON
    for offer in offers:
        for key in ("date_publication", "date_collecte"):
            if offer.get(key) is not None:
                offer[key] = str(offer[key])

    logger.info(
        f"[BigQueryClient] {len(offers)} offres retournées "
        f"(page {page}/{-(-total // page_size)}, total {total})"
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": -(-total // page_size),
        "offers": offers,
    }


def fetch_filter_options() -> dict:
    """
    Retourne les valeurs distinctes pour les filtres :
    sources, types de contrat, régions disponibles.
    """
    client = _get_bq_client()
    table = _build_table_ref()

    query = f"""
        SELECT
            ARRAY_AGG(DISTINCT source IGNORE NULLS ORDER BY source) as sources,
            ARRAY_AGG(DISTINCT type_contrat IGNORE NULLS ORDER BY type_contrat) as types_contrat,
            ARRAY_AGG(DISTINCT localisation_libelle IGNORE NULLS ORDER BY localisation_libelle) as regions,
            # ARRAY_AGG(DISTINCT entreprise_nom IGNORE NULLS ORDER BY entreprise_nom) as entreprise_nom
            ARRAY(
                SELECT entreprise_nom
                FROM (
                    SELECT entreprise_nom, COUNT(*) as nb
                    FROM {table}
                    WHERE entreprise_nom IS NOT NULL
                    GROUP BY entreprise_nom
                    HAVING nb > 5
                    ORDER BY nb DESC
                )
            ) as entreprise_nom
        FROM {table}
    """

    result = next(client.query(query).result())
    return {
        "sources": list(result.sources or []),
        "types_contrat": list(result.types_contrat or []),
        "regions": list(result.regions or []),
        "entreprise_nom": list(result.entreprise_nom or []),
    }
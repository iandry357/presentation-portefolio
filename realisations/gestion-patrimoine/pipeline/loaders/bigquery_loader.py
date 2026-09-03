"""
Chargement des articles chunkés dans BigQuery.
Table unique articles_cgi dans le dataset referentiel_patrimoine.
"""
import json
import logging
import time
from datetime import datetime
from typing import Dict, List

from google.cloud import bigquery
from google.oauth2 import service_account

from pipeline.config import (
    GCP_PROJECT_ID,
    GCP_SA_KEY_PATH,
    BQ_DATASET,
    BQ_TABLE_ARTICLES,
)

logger = logging.getLogger(__name__)

BQ_SCHEMA = [
    bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("source", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("date", "DATE", mode="NULLABLE"),
    bigquery.SchemaField("title", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("content", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("metadata", "STRING", mode="NULLABLE"),  # JSON sérialisé
    bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
]


def _get_client() -> bigquery.Client:
    """Initialise le client BigQuery avec le service account dédié."""
    credentials = service_account.Credentials.from_service_account_file(
        str(GCP_SA_KEY_PATH),
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(project=GCP_PROJECT_ID, credentials=credentials)


def _ensure_table(client: bigquery.Client) -> str:
    """Crée la table BigQuery si elle n'existe pas. Retourne la référence complète."""
    table_ref = f"{GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE_ARTICLES}"
    try:
        client.get_table(table_ref)
    except Exception:
        table = bigquery.Table(table_ref, schema=BQ_SCHEMA)
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="ingested_at",
        )
        client.create_table(table)
        logger.info(f"✅ Table créée: {table_ref}")
    return table_ref


def _get_existing_ids(client: bigquery.Client, table_ref: str) -> set:
    """Récupère les IDs déjà présents dans la table BigQuery."""
    query = f"SELECT id FROM `{table_ref}`"
    rows = client.query(query).result()
    return {row.id for row in rows}


def _prepare_rows(docs: List[Dict]) -> List[Dict]:
    """Prépare les documents pour insertion BigQuery."""
    now = datetime.utcnow().isoformat()
    rows = []
    for doc in docs:
        rows.append({
            "id": doc["id"],
            "source": doc["source"],
            "date": doc.get("date"),
            "title": doc.get("title", ""),
            "content": doc.get("content", ""),
            "metadata": json.dumps(doc.get("metadata", {}), ensure_ascii=False),
            "ingested_at": now,
        })
    return rows


def load(docs: List[Dict]) -> Dict[str, int]:
    """
    Charge les documents (articles chunkés) dans BigQuery.
    Déduplication par id.

    Returns:
        Résumé {"articles_cgi": nb_insérés}
    """
    if not docs:
        logger.warning("⚠️ BigQuery — aucun document à charger")
        return {}

    client = _get_client()
    table_ref = _ensure_table(client)

    # Laisse le temps à une table nouvellement créée d'être visible en requête
    time.sleep(2)

    existing_ids = _get_existing_ids(client, table_ref)
    new_docs = [d for d in docs if d["id"] not in existing_ids]

    skipped = len(docs) - len(new_docs)
    if skipped:
        logger.info(f"⏭️ BigQuery — {skipped} docs déjà présents, ignorés")

    if not new_docs:
        return {BQ_TABLE_ARTICLES: 0}

    rows = _prepare_rows(new_docs)
    errors = client.insert_rows_json(table_ref, rows)

    if errors:
        logger.error(f"❌ BigQuery insert errors: {errors}")
        return {BQ_TABLE_ARTICLES: 0}

    logger.info(f"✅ BigQuery — {len(rows)} docs insérés dans {table_ref}")
    return {BQ_TABLE_ARTICLES: len(rows)}
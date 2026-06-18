"""
Chargement des documents dans BigQuery.
Un dataset par source — sanofi_clinical_trials, sanofi_pubmed, sanofi_news.
"""
import json
import logging
from datetime import datetime
from typing import List, Dict

from google.cloud import bigquery
from google.oauth2 import service_account

from pipeline.config import (
    GCP_PROJECT_ID,
    GCP_SA_KEY_PATH,
    BQ_DATASET_CLINICAL_TRIALS,
    BQ_DATASET_PUBMED,
    BQ_DATASET_NEWS,
    BQ_TABLE_CLINICAL_TRIALS,
    BQ_TABLE_PUBMED,
    BQ_TABLE_NEWS,
    BQ_DATASET_PRESS_RELEASES,
    BQ_TABLE_PRESS_RELEASES,
)

logger = logging.getLogger(__name__)

# Mapping source → (dataset, table)
SOURCE_MAP = {
    "clinicaltrials": (BQ_DATASET_CLINICAL_TRIALS, BQ_TABLE_CLINICAL_TRIALS),
    "pubmed": (BQ_DATASET_PUBMED, BQ_TABLE_PUBMED),
    "google_news": (BQ_DATASET_NEWS, BQ_TABLE_NEWS),
    "press_releases": (BQ_DATASET_PRESS_RELEASES, BQ_TABLE_PRESS_RELEASES),
}

# Schéma BigQuery commun à toutes les tables
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


def _ensure_table(client: bigquery.Client, dataset_id: str, table_id: str) -> None:
    """Crée la table BigQuery si elle n'existe pas."""
    table_ref = f"{GCP_PROJECT_ID}.{dataset_id}.{table_id}"
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


def _prepare_rows(docs: List[Dict]) -> List[Dict]:
    """Prépare les documents pour insertion BigQuery."""
    now = datetime.utcnow().isoformat()
    rows = []
    for doc in docs:
        rows.append({
            "id": doc["id"],
            "source": doc["source"],
            "date": doc["date"],
            "title": doc["title"],
            "content": doc["content"],
            "metadata": json.dumps(doc.get("metadata", {}), ensure_ascii=False),
            "ingested_at": now,
        })
    return rows

# def _get_existing_ids(client: bigquery.Client, dataset_id: str, table_id: str) -> set:
#     """Récupère les IDs déjà présents dans la table BigQuery."""
#     table_ref = f"{GCP_PROJECT_ID}.{dataset_id}.{table_id}"
#     try:
#         client.get_table(table_ref)
#     except Exception:
#         return set()
    
#     query = f"SELECT id FROM `{table_ref}`"
#     rows = client.query(query).result()
#     return {row.id for row in rows}

def _get_existing_ids(client: bigquery.Client, dataset_id: str, table_id: str) -> set:
    """Récupère les IDs déjà présents dans la table BigQuery."""
    table_ref = f"{GCP_PROJECT_ID}.{dataset_id}.{table_id}"
    try:
        client.get_table(table_ref)
    except Exception:
        return set()
    query = f"SELECT id FROM `{table_ref}`"
    rows = client.query(query).result()
    return {row.id for row in rows}


def _get_existing_titles(client: bigquery.Client, dataset_id: str, table_id: str) -> set:
    """Récupère les titres déjà présents dans la table BigQuery."""
    table_ref = f"{GCP_PROJECT_ID}.{dataset_id}.{table_id}"
    try:
        client.get_table(table_ref)
    except Exception:
        return set()
    query = f"SELECT title FROM `{table_ref}`"
    rows = client.query(query).result()
    return {row.title for row in rows}

def _update_content(client: bigquery.Client, dataset_id: str, table_id: str, title: str, content: str) -> None:
    """UPDATE content pour un article existant dont le content est HTML brut."""
    table_ref = f"{GCP_PROJECT_ID}.{dataset_id}.{table_id}"
    escaped = content.replace("'", "\\'")
    escaped_title = title.replace("'", "\\'")
    query = f"""
        UPDATE `{table_ref}`
        SET content = '{escaped}'
        WHERE title = '{escaped_title}'
        AND content LIKE '%<a href=%'
    """
    try:
        client.query(query).result()
    except Exception as e:
        logger.error(f"❌ BQ UPDATE content failed for title '{title[:50]}': {e}")

def _update_url(client: bigquery.Client, dataset_id: str, table_id: str, title: str, new_url: str) -> None:
    """UPDATE metadata.url pour un article existant dont l'URL a changé."""
    table_ref = f"{GCP_PROJECT_ID}.{dataset_id}.{table_id}"
    escaped_title = title.replace("'", "\\'")
    escaped_url = new_url.replace("'", "\\'")
    # query = f"""
    #     UPDATE `{table_ref}`
    #     SET metadata = JSON_SET(metadata, '$.url', '{escaped_url}')
    #     WHERE title = '{escaped_title}'
    #     AND JSON_VALUE(metadata, '$.url') != '{escaped_url}'
    # """
    query = f"""
        UPDATE `{table_ref}`
        SET metadata = REGEXP_REPLACE(
            metadata,
            r'"url":\\s*"[^"]*"',
            '"url": "{escaped_url}"'
        )
        WHERE title = '{escaped_title}'
        AND JSON_VALUE(metadata, '$.url') != '{escaped_url}'
    """
    try:
        client.query(query).result()
    except Exception as e:
        logger.error(f"❌ BQ UPDATE url failed for title '{title[:50]}': {e}")

def load(docs: List[Dict]) -> Dict[str, int]:
    """
    Charge les documents dans BigQuery.
    Groupe par source et insère dans la table correspondante.

    Returns:
        Résumé {source: nb_insérés}
    """
    if not docs:
        logger.warning("⚠️ BigQuery — aucun document à charger")
        return {}

    client = _get_client()
    summary = {}

    # Grouper par source
    by_source: Dict[str, List[Dict]] = {}
    for doc in docs:
        src = doc["source"]
        by_source.setdefault(src, []).append(doc)

    for source, source_docs in by_source.items():
        if source not in SOURCE_MAP:
            logger.warning(f"⚠️ Source inconnue ignorée: {source}")
            continue

        dataset_id, table_id = SOURCE_MAP[source]
        _ensure_table(client, dataset_id, table_id)
        import time
        time.sleep(2)

        # Déduplication
        # existing_ids = _get_existing_ids(client, dataset_id, table_id)
        # new_docs = [d for d in source_docs if d["id"] not in existing_ids]

        # Déduplication — par titre pour google_news, par ID pour les autres
        # if source == "google_news":
        if source in ("google_news", "press_releases"):
            existing = _get_existing_titles(client, dataset_id, table_id)
            new_docs = [d for d in source_docs if d["title"] not in existing]
            if source == "google_news":
                for d in source_docs:
                    if d["title"] in existing:
                        # UPDATE content si HTML brut
                        if d["content"] and "<a href=" not in d["content"]:
                            _update_content(client, dataset_id, table_id, d["title"], d["content"])
                        # UPDATE url si différente
                        new_url = d.get("metadata", {}).get("url", "")
                        if new_url:
                            _update_url(client, dataset_id, table_id, d["title"], new_url)
        else:
            existing = _get_existing_ids(client, dataset_id, table_id)
            new_docs = [d for d in source_docs if d["id"] not in existing]

        skipped = len(source_docs) - len(new_docs)

        if skipped:
            logger.info(f"⏭️ BigQuery [{source}]: {skipped} docs déjà présents, ignorés")

        if not new_docs:
            summary[source] = 0
            continue

        rows = _prepare_rows(new_docs)
        table_ref = f"{GCP_PROJECT_ID}.{dataset_id}.{table_id}"

        errors = client.insert_rows_json(table_ref, rows)
        if errors:
            logger.error(f"❌ BigQuery insert errors [{source}]: {errors}")
            summary[source] = 0
        else:
            summary[source] = len(rows)
            logger.info(f"✅ BigQuery — {len(rows)} docs insérés dans {table_ref}")

    return summary
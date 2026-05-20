import json
import os
from google.cloud import bigquery
from google.oauth2 import service_account

PROJECT_ID = "gen-lang-client-0989575872"

TABLES = {
    "clinical_trials": "sanofi_clinical_trials.raw_studies",
    "pubmed": "sanofi_pubmed.raw_articles",
    "news": "sanofi_news.raw_news",
    "press_releases": "sanofi_press_releases.raw_press_releases",
}

COLUMNS = "id, source, date, title, content, metadata"


def _get_client() -> bigquery.Client:
    sa_path = os.getenv("GCP_SA_SANOFI_PATH")
    if sa_path:
        creds = service_account.Credentials.from_service_account_file(sa_path)
        return bigquery.Client(project=PROJECT_ID, credentials=creds)
    return bigquery.Client(project=PROJECT_ID)


def _parse_metadata(row: dict) -> dict:
    try:
        row["metadata"] = json.loads(row["metadata"]) if row.get("metadata") else {}
    except (json.JSONDecodeError, TypeError):
        row["metadata"] = {}
    return row


def _fetch(table_key: str) -> list[dict]:
    client = _get_client()
    table = TABLES[table_key]
    query = f"SELECT {COLUMNS} FROM `{PROJECT_ID}.{table}` ORDER BY date DESC"
    rows = client.query(query).result()
    return [_parse_metadata(dict(row)) for row in rows]


def get_clinical_trials() -> list[dict]:
    return _fetch("clinical_trials")


def get_pubmed_articles() -> list[dict]:
    return _fetch("pubmed")


def get_news() -> list[dict]:
    return _fetch("news")

def get_press_releases() -> list[dict]:
    return _fetch("press_releases")
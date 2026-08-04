"""
BigQuery Client — Banque de France
Lecture des articles de veille depuis banque_de_france_veille.articles_bruts
Filtre sur source='google_news' — exclut les decisions ACPR (source='acpr_decision'),
qui vivent dans un registre de langue tres different (texte juridique long) et
polluerait le topic modeling s'il etait melange a la veille actualites.
"""

import json
import os

from google.cloud import bigquery
from google.oauth2 import service_account

PROJECT_ID = "gen-lang-client-0989575872"

TABLES = {
    "news": "banque_de_france_veille.articles_bruts",
}

COLUMNS = "id, source, date, title, content, metadata, ingested_at"

# Perimetre veille uniquement — les decisions ACPR sont exclues ici
# (meme logique que le filtre applique cote RAG).
SOURCE_FILTER = "google_news"


def _get_client() -> bigquery.Client:
    sa_path = os.getenv("SA_KEY_PATH", "/app/gcp_sa_banque.json")
    if sa_path and os.path.exists(sa_path):
        creds = service_account.Credentials.from_service_account_file(sa_path)
        return bigquery.Client(project=PROJECT_ID, credentials=creds)
    return bigquery.Client(project=PROJECT_ID)


def _parse_metadata(row: dict) -> dict:
    try:
        meta = row.get("metadata")
        if isinstance(meta, dict):
            row["metadata"] = meta
        elif isinstance(meta, str):
            row["metadata"] = json.loads(meta)
        else:
            row["metadata"] = {}
    except (json.JSONDecodeError, TypeError):
        row["metadata"] = {}
    return row


def _fetch(table_key: str) -> list[dict]:
    client = _get_client()
    table = TABLES[table_key]
    query = (
        f"SELECT {COLUMNS} FROM `{PROJECT_ID}.{table}` "
        f"WHERE source = '{SOURCE_FILTER}' "
        f"QUALIFY ROW_NUMBER() OVER ("
        f"    PARTITION BY LOWER(TRIM(REGEXP_REPLACE(title, r'\\s+', ' '))) "
        f"    ORDER BY ingested_at DESC"
        f") = 1 "
        f"ORDER BY date DESC"
    )
    rows = client.query(query).result()
    return [_parse_metadata(dict(row)) for row in rows]


def get_news() -> list[dict]:
    return _fetch("news")
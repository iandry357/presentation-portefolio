"""
Debug URLs — inspecte les URLs réelles en BigQuery pour Sanofi.
Usage: docker-compose run --rm pipeline python scripts/debug_bq_urls.py
"""
import json
from google.cloud import bigquery
from google.oauth2 import service_account
from pipeline.config import GCP_PROJECT_ID, GCP_SA_KEY_PATH

credentials = service_account.Credentials.from_service_account_file(str(GCP_SA_KEY_PATH))
client = bigquery.Client(project=GCP_PROJECT_ID, credentials=credentials)

query = """
    SELECT title, metadata
    FROM `gen-lang-client-0989575872.sanofi_news.raw_news`
    ORDER BY ingested_at DESC
    LIMIT 5
"""

rows = client.query(query).result()
for row in rows:
    meta = json.loads(row.metadata) if isinstance(row.metadata, str) else row.metadata
    print(f"title: {row.title[:60]}")
    print(f"url  : {meta.get('url', '')}")
    print()
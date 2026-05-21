"""
Vérifie le contenu metadata des press releases depuis BigQuery.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import GCP_PROJECT_ID
# from bq_client import get_press_releases, get_news
from pipeline.loaders.bigquery_loader import _get_client
from pipeline.config import GCP_PROJECT_ID, BQ_DATASET_NEWS, BQ_TABLE_NEWS, BQ_DATASET_PRESS_RELEASES, BQ_TABLE_PRESS_RELEASES

def fetch(dataset, table):
    client = _get_client()
    query = f"SELECT id, title, metadata FROM `{GCP_PROJECT_ID}.{dataset}.{table}` LIMIT 3"
    return [dict(row) for row in client.query(query).result()]

print("=== PRESS RELEASES ===")
# docs = get_press_releases()
docs = fetch(BQ_DATASET_PRESS_RELEASES, BQ_TABLE_PRESS_RELEASES)
for doc in docs[:3]:
    print(f"title : {doc.get('title', '')[:60]}")
    print(f"metadata : {doc.get('metadata')}")
    print()

print("=== GOOGLE NEWS ===")
# docs = get_news()
docs = fetch(BQ_DATASET_NEWS, BQ_TABLE_NEWS)
for doc in docs[:3]:
    print(f"title : {doc.get('title', '')[:60]}")
    print(f"metadata : {doc.get('metadata')}")
    print()
"""
Script de vérification — compare les compteurs BigQuery vs ChromaDB.
Usage: docker-compose run --rm pipeline python scripts/check_data.py
"""
import chromadb
from chromadb.config import Settings
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
    CHROMA_HOST,
    CHROMA_PORT,
    CHROMA_USER,
    CHROMA_PASSWORD,
    CHROMA_COLLECTION_CLINICAL_TRIALS,
    CHROMA_COLLECTION_PUBMED,
    CHROMA_COLLECTION_NEWS,
    BQ_DATASET_PRESS_RELEASES,
    BQ_TABLE_PRESS_RELEASES,
    CHROMA_COLLECTION_PRESS_RELEASES,
)

# ─────────────────────────────────────────
# BigQuery
# ─────────────────────────────────────────

credentials = service_account.Credentials.from_service_account_file(
    str(GCP_SA_KEY_PATH),
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)
bq_client = bigquery.Client(project=GCP_PROJECT_ID, credentials=credentials)

bq_counts = {}
for dataset, table, label in [
    (BQ_DATASET_CLINICAL_TRIALS, BQ_TABLE_CLINICAL_TRIALS, "clinicaltrials"),
    (BQ_DATASET_PUBMED, BQ_TABLE_PUBMED, "pubmed"),
    (BQ_DATASET_NEWS, BQ_TABLE_NEWS, "google_news"),
    (BQ_DATASET_PRESS_RELEASES, BQ_TABLE_PRESS_RELEASES, "press_releases"),
]:
    try:
        query = f"SELECT COUNT(*) as cnt FROM `{GCP_PROJECT_ID}.{dataset}.{table}`"
        result = list(bq_client.query(query).result())
        bq_counts[label] = result[0].cnt
    except Exception as e:
        bq_counts[label] = f"ERREUR: {e}"

# ─────────────────────────────────────────
# ChromaDB
# ─────────────────────────────────────────

chroma_client = chromadb.HttpClient(
    host=CHROMA_HOST,
    port=CHROMA_PORT,
    settings=Settings(
        chroma_client_auth_provider="chromadb.auth.basic_authn.BasicAuthClientProvider",
        chroma_client_auth_credentials=f"{CHROMA_USER}:{CHROMA_PASSWORD}",
        anonymized_telemetry=False,
    ),
)

chroma_counts = {}
for collection_name, label in [
    (CHROMA_COLLECTION_CLINICAL_TRIALS, "clinicaltrials"),
    (CHROMA_COLLECTION_PUBMED, "pubmed"),
    (CHROMA_COLLECTION_NEWS, "google_news"),
    (CHROMA_COLLECTION_PRESS_RELEASES, "press_releases"),
]:
    try:
        col = chroma_client.get_collection(collection_name)
        chroma_counts[label] = col.count()
    except Exception as e:
        chroma_counts[label] = f"ERREUR: {e}"

# ─────────────────────────────────────────
# Rapport
# ─────────────────────────────────────────

print("\n" + "=" * 55)
print(f"{'Source':<20} {'BigQuery':>10} {'ChromaDB':>10} {'OK?':>8}")
print("=" * 55)

all_ok = True
for label in ["clinicaltrials", "pubmed", "google_news", "press_releases"]:
    bq = bq_counts.get(label, "?")
    ch = chroma_counts.get(label, "?")
    ok = "✅" if bq == ch else "❌"
    if bq != ch:
        all_ok = False
    print(f"{label:<20} {str(bq):>10} {str(ch):>10} {ok:>8}")

print("=" * 55)
if all_ok:
    print("✅ BigQuery et ChromaDB sont synchronisés.")
else:
    print("❌ Désynchronisation détectée — relancer le pipeline.")
print()
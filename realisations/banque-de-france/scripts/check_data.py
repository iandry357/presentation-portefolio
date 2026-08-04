"""
Script de vérification — compare les compteurs BigQuery vs ChromaDB.
Table BigQuery unique (articles_bruts, colonne source) et collection
ChromaDB unique, partagées entre google_news et acpr_decision.
Usage: docker-compose run --rm pipeline python scripts/check_data.py
"""
import chromadb
from chromadb.config import Settings
from google.cloud import bigquery
from google.oauth2 import service_account

from pipeline.config import (
    GCP_PROJECT_ID,
    GCP_SA_KEY_PATH,
    BQ_DATASET,
    BQ_TABLE_NEWS,
    CHROMA_HOST,
    CHROMA_PORT,
    CHROMA_USER,
    CHROMA_PASSWORD,
    CHROMA_COLLECTION,
)

SOURCES = ["google_news", "acpr_decision"]

# ─────────────────────────────────────────
# BigQuery
# ─────────────────────────────────────────

credentials = service_account.Credentials.from_service_account_file(
    str(GCP_SA_KEY_PATH),
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)
bq_client = bigquery.Client(project=GCP_PROJECT_ID, credentials=credentials)

bq_counts = {}
try:
    query = f"""
        SELECT source, COUNT(*) as cnt
        FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE_NEWS}`
        GROUP BY source
    """
    for row in bq_client.query(query).result():
        bq_counts[row.source] = row.cnt
except Exception as e:
    for src in SOURCES:
        bq_counts[src] = f"ERREUR: {e}"

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
try:
    collection = chroma_client.get_collection(CHROMA_COLLECTION)
    for src in SOURCES:
        result = collection.get(where={"source": src})
        chroma_counts[src] = len(result["ids"])
except Exception as e:
    for src in SOURCES:
        chroma_counts[src] = f"ERREUR: {e}"

# ─────────────────────────────────────────
# Rapport
# ─────────────────────────────────────────

print("\n" + "=" * 55)
print(f"{'Source':<20} {'BigQuery':>10} {'ChromaDB':>10} {'OK?':>8}")
print("=" * 55)

all_ok = True
for src in SOURCES:
    bq = bq_counts.get(src, 0)
    ch = chroma_counts.get(src, 0)
    ok = "✅" if bq == ch else "❌"
    if bq != ch:
        all_ok = False
    print(f"{src:<20} {str(bq):>10} {str(ch):>10} {ok:>8}")

print("=" * 55)
if all_ok:
    print("✅ BigQuery et ChromaDB sont synchronisés.")
else:
    print("❌ Désynchronisation détectée — relancer le pipeline.")
print()
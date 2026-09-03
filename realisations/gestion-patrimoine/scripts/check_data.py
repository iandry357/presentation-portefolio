"""
Script de vérification — compare les compteurs BigQuery vs ChromaDB.
Table BigQuery unique (articles_cgi) et collection ChromaDB unique
(referentiel_patrimoine), une seule source (legifrance) mais comparaison
détaillée par thématique pour repérer une désynchronisation partielle.
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
    BQ_TABLE_ARTICLES,
    CHROMA_HOST,
    CHROMA_PORT,
    CHROMA_USER,
    CHROMA_PASSWORD,
    CHROMA_COLLECTION,
    THEMATIQUES,
)

THEMATIQUE_KEYS = list(THEMATIQUES.keys())

# ─────────────────────────────────────────
# BigQuery — comptage par thématique (extraite du JSON metadata)
# ─────────────────────────────────────────

credentials = service_account.Credentials.from_service_account_file(
    str(GCP_SA_KEY_PATH),
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)
bq_client = bigquery.Client(project=GCP_PROJECT_ID, credentials=credentials)

bq_counts = {}
bq_total = 0
try:
    query = f"""
        SELECT JSON_EXTRACT_SCALAR(metadata, '$.thematique') AS thematique, COUNT(*) as cnt
        FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE_ARTICLES}`
        GROUP BY thematique
    """
    for row in bq_client.query(query).result():
        bq_counts[row.thematique] = row.cnt
        bq_total += row.cnt
except Exception as e:
    for k in THEMATIQUE_KEYS:
        bq_counts[k] = f"ERREUR: {e}"

# ─────────────────────────────────────────
# ChromaDB — comptage par thématique (metadata directe)
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
chroma_total = 0
try:
    collection = chroma_client.get_collection(CHROMA_COLLECTION)
    for k in THEMATIQUE_KEYS:
        result = collection.get(where={"thematique": k})
        n = len(result["ids"])
        chroma_counts[k] = n
        chroma_total += n
except Exception as e:
    for k in THEMATIQUE_KEYS:
        chroma_counts[k] = f"ERREUR: {e}"

# ─────────────────────────────────────────
# Rapport
# ─────────────────────────────────────────

print("\n" + "=" * 55)
print(f"{'Thématique':<25} {'BigQuery':>10} {'ChromaDB':>10} {'OK?':>8}")
print("=" * 55)

all_ok = True
for k in THEMATIQUE_KEYS:
    bq = bq_counts.get(k, 0)
    ch = chroma_counts.get(k, 0)
    ok = "✅" if bq == ch else "❌"
    if bq != ch:
        all_ok = False
    print(f"{k:<25} {str(bq):>10} {str(ch):>10} {ok:>8}")

print("-" * 55)
total_ok = "✅" if bq_total == chroma_total else "❌"
if bq_total != chroma_total:
    all_ok = False
print(f"{'TOTAL':<25} {str(bq_total):>10} {str(chroma_total):>10} {total_ok:>8}")

print("=" * 55)
if all_ok:
    print("✅ BigQuery et ChromaDB sont synchronisés.")
else:
    print("❌ Désynchronisation détectée — relancer le pipeline.")
print()
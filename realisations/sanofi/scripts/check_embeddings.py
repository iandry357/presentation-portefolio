"""
Script de vérification des embeddings ChromaDB.
Vérifie que chaque collection a bien des vecteurs de la bonne dimension.
Usage: docker-compose run --rm pipeline python scripts/check_embeddings.py
"""
import chromadb
from chromadb.config import Settings
from pipeline.config import (
    CHROMA_HOST,
    CHROMA_PORT,
    CHROMA_USER,
    CHROMA_PASSWORD,
    CHROMA_COLLECTION_CLINICAL_TRIALS,
    CHROMA_COLLECTION_PUBMED,
    CHROMA_COLLECTION_NEWS,
    VOYAGE_EMBEDDING_DIMENSIONS,
)

client = chromadb.HttpClient(
    host=CHROMA_HOST,
    port=CHROMA_PORT,
    settings=Settings(
        chroma_client_auth_provider="chromadb.auth.basic_authn.BasicAuthClientProvider",
        chroma_client_auth_credentials=f"{CHROMA_USER}:{CHROMA_PASSWORD}",
        anonymized_telemetry=False,
    ),
)

collections = [
    (CHROMA_COLLECTION_CLINICAL_TRIALS, "clinicaltrials"),
    (CHROMA_COLLECTION_PUBMED, "pubmed"),
    (CHROMA_COLLECTION_NEWS, "google_news"),
]

print("\n" + "=" * 65)
print(f"{'Collection':<30} {'Docs':>6} {'Dim':>6} {'Dim OK?':>8} {'Sample OK?':>10}")
print("=" * 65)

all_ok = True
for collection_name, label in collections:
    try:
        col = client.get_collection(collection_name)
        count = col.count()

        # Récupère un sample avec embeddings
        sample = col.get(limit=1, include=["embeddings"])
        embeddings = sample.get("embeddings", [])

        # if embeddings and embeddings[0]:
        if embeddings is not None and len(embeddings) > 0 and embeddings[0] is not None:
            dim = len(embeddings[0])
            dim_ok = "✅" if dim == VOYAGE_EMBEDDING_DIMENSIONS else "❌"
            sample_ok = "✅"
            if dim != VOYAGE_EMBEDDING_DIMENSIONS:
                all_ok = False
        else:
            dim = 0
            dim_ok = "❌"
            sample_ok = "❌"
            all_ok = False

        print(f"{collection_name:<30} {count:>6} {dim:>6} {dim_ok:>8} {sample_ok:>10}")

    except Exception as e:
        print(f"{collection_name:<30} {'ERREUR':>6} — {e}")
        all_ok = False

print("=" * 65)
print(f"Dimension attendue : {VOYAGE_EMBEDDING_DIMENSIONS}")
if all_ok:
    print("✅ Tous les embeddings sont valides.")
else:
    print("❌ Problème détecté — relancer le pipeline.")
print()
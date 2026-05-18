"""
Script de test retrieval ChromaDB — teste une requête sémantique sur les 3 collections.
Usage: docker-compose run --rm pipeline python scripts/test_retrieval.py
"""
import voyageai
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
    VOYAGE_API_KEY,
    VOYAGE_EMBEDDING_MODEL,
    VOYAGE_EMBEDDING_DIMENSIONS,
)

# ─────────────────────────────────────────
# Question de test
# ─────────────────────────────────────────
QUESTION = "Quels sont les essais cliniques Sanofi en oncologie ?"
N_RESULTS = 3

print(f"\n🔍 Question : {QUESTION}")
print("=" * 65)

# ─────────────────────────────────────────
# Embedding de la question
# ─────────────────────────────────────────
voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
result = voyage_client.embed(
    [QUESTION],
    model=VOYAGE_EMBEDDING_MODEL,
    input_type="query",
    output_dimension=VOYAGE_EMBEDDING_DIMENSIONS,
)
query_embedding = result.embeddings[0]
print(f"✅ Embedding question généré — dim={len(query_embedding)}")

# ─────────────────────────────────────────
# Retrieval sur les 3 collections
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

collections = [
    (CHROMA_COLLECTION_CLINICAL_TRIALS, "clinicaltrials"),
    (CHROMA_COLLECTION_PUBMED, "pubmed"),
    (CHROMA_COLLECTION_NEWS, "google_news"),
]

for collection_name, label in collections:
    print(f"\n📚 Collection : {collection_name}")
    print("-" * 50)
    try:
        col = chroma_client.get_collection(collection_name)
        results = col.query(
            query_embeddings=[query_embedding],
            n_results=N_RESULTS,
            include=["documents", "metadatas", "distances"],
        )

        for i, doc_id in enumerate(results["ids"][0]):
            distance = results["distances"][0][i]
            score = round(1 - distance, 4)
            meta = results["metadatas"][0][i]
            content = results["documents"][0][i]

            print(f"\n  [{i+1}] ID    : {doc_id}")
            print(f"       Score : {score}")
            print(f"       Titre : {meta.get('title', 'N/A')[:80]}")
            print(f"       Extrait : {content[:150]}...")

    except Exception as e:
        print(f"❌ Erreur : {e}")

print("\n" + "=" * 65)
print("✅ Test retrieval terminé.")
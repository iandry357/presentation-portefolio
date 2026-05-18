"""
Script d'inspection ChromaDB — affiche la structure des documents stockés.
Usage: docker-compose run --rm pipeline python scripts/inspect_chromadb.py
"""
import json
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

for collection_name, label in collections:
    print("\n" + "=" * 65)
    print(f"Collection : {collection_name} ({label})")
    print("=" * 65)

    try:
        col = client.get_collection(collection_name)
        total = col.count()
        print(f"Total documents : {total}")

        # Récupère 2 samples sans embeddings pour lisibilité
        sample = col.get(
            limit=2,
            include=["documents", "metadatas", "embeddings"],
        )

        for i in range(len(sample["ids"])):
            print(f"\n--- Document {i + 1} ---")
            print(f"ID       : {sample['ids'][i]}")
            print(f"Metadata : {json.dumps(sample['metadatas'][i], indent=2, ensure_ascii=False)}")
            content = sample["documents"][i]
            print(f"Content  : {content[:300]}{'...' if len(content) > 300 else ''}")
            emb = sample["embeddings"][i]
            print(f"Embedding: dim={len(emb)}, first_5={[round(v, 4) for v in emb[:5]]}")

    except Exception as e:
        print(f"❌ Erreur : {e}")

print("\n" + "=" * 65)
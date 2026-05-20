import os
import chromadb
from chromadb.config import Settings

COLLECTION_CLINICAL_TRIALS = "sanofi_clinical_trials"


def _get_client() -> chromadb.HttpClient:
    host = os.getenv("CHROMA_HOST", "51.68.130.23")
    port = int(os.getenv("CHROMA_PORT", "8000"))
    user = os.getenv("CHROMA_USER", "admin")
    password = os.getenv("CHROMA_PASSWORD", "")

    return chromadb.HttpClient(
        host=host,
        port=port,
        settings=Settings(
            chroma_client_auth_provider="chromadb.auth.basic_authn.BasicAuthClientProvider",
            chroma_client_auth_credentials=f"{user}:{password}",
        ),
    )


def get_embeddings_clinical_trials() -> dict[str, list[float]]:
    client = _get_client()
    collection = client.get_collection(COLLECTION_CLINICAL_TRIALS)

    total = collection.count()
    results = collection.get(
        limit=total,
        include=["embeddings"],
    )

    embeddings_map = {}
    for doc_id, embedding in zip(results["ids"], results["embeddings"]):
        embeddings_map[doc_id] = embedding

    print(f"ChromaDB — {len(embeddings_map)} embeddings récupérés pour clinical_trials")
    return embeddings_map
"""
ChromaDB Client — SG Assurances
Collection : sg_assurances_news (dimension 768)
Serveur partagé OVH : 51.68.130.23:8000
"""

import os

import chromadb
from chromadb.config import Settings

COLLECTION_SG_NEWS = "sg_assurances_news"


def _get_client() -> chromadb.HttpClient:
    host     = os.getenv("CHROMA_HOST",     "51.68.130.23")
    port     = int(os.getenv("CHROMA_PORT", "8000"))
    user     = os.getenv("CHROMA_USER",     "admin")
    password = os.getenv("CHROMA_PASSWORD", "")

    return chromadb.HttpClient(
        host=host,
        port=port,
        settings=Settings(
            chroma_client_auth_provider="chromadb.auth.basic_authn.BasicAuthClientProvider",
            chroma_client_auth_credentials=f"{user}:{password}",
        ),
    )


def query_news(query_embedding: list[float], n_results: int = 5) -> list[dict]:
    """
    Recherche sémantique dans les articles de veille SG Assurances.

    Args:
        query_embedding : vecteur de la requête (dim 768)
        n_results       : nombre de résultats à retourner

    Returns:
        Liste de documents avec id, content, metadata, distance
    """
    client     = _get_client()
    collection = client.get_collection(COLLECTION_SG_NEWS)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    docs = []
    for i, doc_id in enumerate(results["ids"][0]):
        docs.append({
            "id":       doc_id,
            "content":  results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": round(results["distances"][0][i], 4),
        })

    return docs


def get_all_embeddings() -> dict[str, list[float]]:
    """
    Récupère tous les embeddings de la collection SG Assurances.
    Utilisé pour visualisation ou clustering.

    Returns:
        Dict {doc_id: embedding}
    """
    client     = _get_client()
    collection = client.get_collection(COLLECTION_SG_NEWS)

    total   = collection.count()
    results = collection.get(
        limit=total,
        include=["embeddings"],
    )

    embeddings_map = {}
    for doc_id, embedding in zip(results["ids"], results["embeddings"]):
        embeddings_map[doc_id] = embedding

    print(f"[chroma] {len(embeddings_map)} embeddings récupérés — sg_assurances_news")
    return embeddings_map
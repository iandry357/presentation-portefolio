"""
Chargement des documents dans ChromaDB avec embeddings VoyageAI.
Une collection par source — sanofi_clinical_trials, sanofi_pubmed, sanofi_news.
"""
import logging
from typing import List, Dict

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

logger = logging.getLogger(__name__)

# Mapping source → collection ChromaDB
COLLECTION_MAP = {
    "clinicaltrials": CHROMA_COLLECTION_CLINICAL_TRIALS,
    "pubmed": CHROMA_COLLECTION_PUBMED,
    "google_news": CHROMA_COLLECTION_NEWS,
}

# Batch size VoyageAI (limite API)
VOYAGE_BATCH_SIZE = 128


def _get_chroma_client() -> chromadb.HttpClient:
    """Initialise le client ChromaDB avec auth Basic."""
    return chromadb.HttpClient(
        host=CHROMA_HOST,
        port=CHROMA_PORT,
        # settings=Settings(
        #     chroma_client_auth_provider="chromadb.auth.basic_authn.BasicAuthClientProvider",
        #     chroma_client_auth_credentials=f"{CHROMA_USER}:{CHROMA_PASSWORD}",
        # ),
        settings=Settings(
            chroma_client_auth_provider="chromadb.auth.basic_authn.BasicAuthClientProvider",
            chroma_client_auth_credentials=f"{CHROMA_USER}:{CHROMA_PASSWORD}",
            anonymized_telemetry=False,
        ),
    )


def _get_collection(client: chromadb.HttpClient, name: str) -> chromadb.Collection:
    """Récupère ou crée une collection ChromaDB."""
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def _embed_batch(texts: List[str], voyage_client: voyageai.Client) -> List[List[float]]:
    """Génère les embeddings VoyageAI pour un batch de textes."""
    result = voyage_client.embed(
        texts,
        model=VOYAGE_EMBEDDING_MODEL,
        input_type="document",
        output_dimension=VOYAGE_EMBEDDING_DIMENSIONS,
    )
    return result.embeddings


def load(docs: List[Dict]) -> Dict[str, int]:
    """
    Charge les documents dans ChromaDB avec embeddings VoyageAI.
    Groupe par source et insère dans la collection correspondante.
    Déduplication par ID — upsert si document déjà présent.

    Returns:
        Résumé {source: nb_insérés}
    """
    if not docs:
        logger.warning("⚠️ ChromaDB — aucun document à charger")
        return {}

    chroma_client = _get_chroma_client()
    voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
    summary = {}

    # Grouper par source
    by_source: Dict[str, List[Dict]] = {}
    for doc in docs:
        src = doc["source"]
        by_source.setdefault(src, []).append(doc)

    for source, source_docs in by_source.items():
        if source not in COLLECTION_MAP:
            logger.warning(f"⚠️ Source inconnue ignorée: {source}")
            continue

        collection_name = COLLECTION_MAP[source]
        collection = _get_collection(chroma_client, collection_name)

        # Traitement par batch
        total = 0
        for i in range(0, len(source_docs), VOYAGE_BATCH_SIZE):
            batch = source_docs[i:i + VOYAGE_BATCH_SIZE]

            ids = [doc["id"] for doc in batch]
            texts = [doc["content"] for doc in batch]
            metadatas = [
                {
                    "source": doc["source"],
                    "date": doc["date"],
                    "title": doc["title"],
                    **{k: str(v) for k, v in doc.get("metadata", {}).items()
                       if isinstance(v, (str, int, float, bool))},
                }
                for doc in batch
            ]

            try:
                embeddings = _embed_batch(texts, voyage_client)
                collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=texts,
                    metadatas=metadatas,
                )
                total += len(batch)
                logger.info(f"✅ ChromaDB [{collection_name}] — batch {i // VOYAGE_BATCH_SIZE + 1}: {len(batch)} docs")
            except Exception as e:
                logger.error(f"❌ ChromaDB upsert error [{collection_name}] batch {i}: {e}")

        summary[source] = total
        logger.info(f"✅ ChromaDB — {total} docs dans '{collection_name}'")

    return summary
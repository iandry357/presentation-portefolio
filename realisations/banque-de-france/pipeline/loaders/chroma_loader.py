"""
Chargement des documents dans ChromaDB avec embeddings sentence-transformers.
Collection unique — partagée entre veille (google_news) et décisions ACPR (acpr_decision).
"""
import logging
from typing import Dict, List

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from pipeline.config import (
    CHROMA_COLLECTION,
    CHROMA_HOST,
    CHROMA_PASSWORD,
    CHROMA_PORT,
    CHROMA_USER,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
)

logger = logging.getLogger(__name__)

# Mapping source → collection ChromaDB
COLLECTION_MAP = {
    "google_news":   CHROMA_COLLECTION,
    "acpr_decision": CHROMA_COLLECTION,
}

# Batch size — sentence-transformers local, pas de limite API
BATCH_SIZE = 64

# Modèle chargé une seule fois en mémoire
_model: SentenceTransformer = None


def _get_model() -> SentenceTransformer:
    """Charge le modèle sentence-transformers (singleton)."""
    global _model
    if _model is None:
        logger.info(f"🔄 Chargement modèle embeddings: {EMBEDDING_MODEL}")
        _model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info(f"✅ Modèle chargé — dim: {EMBEDDING_DIMENSIONS}")
    return _model


def _get_chroma_client() -> chromadb.HttpClient:
    """Initialise le client ChromaDB avec auth Basic."""
    return chromadb.HttpClient(
        host=CHROMA_HOST,
        port=CHROMA_PORT,
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


def _embed_batch(texts: List[str], model: SentenceTransformer) -> List[List[float]]:
    """Génère les embeddings sentence-transformers pour un batch de textes."""
    embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return embeddings.tolist()


def load(docs: List[Dict]) -> Dict[str, int]:
    """
    Charge les documents dans ChromaDB avec embeddings sentence-transformers.
    Groupe par source et insère dans la collection correspondante.
    Déduplication par ID — upsert si document déjà présent.

    Returns:
        Résumé {source: nb_insérés}
    """
    if not docs:
        logger.warning("⚠️ ChromaDB — aucun document à charger")
        return {}

    chroma_client = _get_chroma_client()
    model = _get_model()
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

        total = 0
        for i in range(0, len(source_docs), BATCH_SIZE):
            batch = source_docs[i:i + BATCH_SIZE]

            ids = [doc["id"] for doc in batch]
            texts = [doc["content"] for doc in batch]
            metadatas = [
                {
                    "source": doc["source"],
                    "date": doc.get("date", ""),
                    "title": doc["title"],
                    **{k: str(v) for k, v in doc.get("metadata", {}).items()
                       if isinstance(v, (str, int, float, bool))},
                }
                for doc in batch
            ]

            try:
                embeddings = _embed_batch(texts, model)
                collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=texts,
                    metadatas=metadatas,
                )
                total += len(batch)
                logger.info(f"✅ ChromaDB [{collection_name}] — batch {i // BATCH_SIZE + 1}: {len(batch)} docs")
            except Exception as e:
                logger.error(f"❌ ChromaDB upsert error [{collection_name}] batch {i}: {e}")

        summary[source] = total
        logger.info(f"✅ ChromaDB — {total} docs dans '{collection_name}'")

    return summary
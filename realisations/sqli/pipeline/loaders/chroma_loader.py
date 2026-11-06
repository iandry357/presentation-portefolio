"""
Chargement des documents dans ChromaDB avec embeddings OVH.
Embeddings : Embedding Service OVH (port 8004, dim 768), réveillé via l'orchestrateur.
Collection : sqli_veille.
"""
import logging
import time
from typing import Dict, List

import chromadb
import requests
from chromadb.config import Settings

from pipeline.config import (
    CHROMA_COLLECTION,
    CHROMA_HOST,
    CHROMA_PASSWORD,
    CHROMA_PORT,
    CHROMA_USER,
    EMBEDDING_SERVICE_PORT,
    OVH_ML_HOST,
    OVH_ORCHESTRATOR_PORT,
)

logger = logging.getLogger(__name__)

# Mapping source → collection ChromaDB
COLLECTION_MAP = {
    "google_news": CHROMA_COLLECTION,
    "sqli_site": CHROMA_COLLECTION,
}

ORCHESTRATOR_URL = f"http://{OVH_ML_HOST}:{OVH_ORCHESTRATOR_PORT}"
EMBEDDING_BASE_URL = f"http://{OVH_ML_HOST}:{EMBEDDING_SERVICE_PORT}"
EMBEDDING_SERVICE_KEY = "embedding-service"

WAKE_TIMEOUT_SECONDS = 120
POLL_INTERVAL_SECONDS = 2

# Taille des batchs envoyés au service d'embedding
BATCH_SIZE = 64


def _wake_embedding_service() -> None:
    """Démarre l'Embedding Service via l'orchestrateur et attend son /health."""
    try:
        requests.post(f"{ORCHESTRATOR_URL}/wake/{EMBEDDING_SERVICE_KEY}", timeout=10)
    except Exception as e:
        logger.warning(f"⚠️ Wake signal failed for {EMBEDDING_SERVICE_KEY}: {e}")

    elapsed = 0
    while elapsed < WAKE_TIMEOUT_SECONDS:
        try:
            resp = requests.get(f"{EMBEDDING_BASE_URL}/health", timeout=5)
            if resp.status_code == 200:
                logger.info(f"✅ {EMBEDDING_SERVICE_KEY} prêt")
                return
        except Exception:
            pass
        time.sleep(POLL_INTERVAL_SECONDS)
        elapsed += POLL_INTERVAL_SECONDS

    raise TimeoutError(
        f"{EMBEDDING_SERVICE_KEY} indisponible après {WAKE_TIMEOUT_SECONDS}s"
    )


def _heartbeat() -> None:
    """Réinitialise le timer d'inactivité de l'orchestrateur — fire-and-forget."""
    try:
        requests.post(f"{ORCHESTRATOR_URL}/heartbeat/{EMBEDDING_SERVICE_KEY}", timeout=3)
    except Exception as e:
        logger.debug(f"Heartbeat failed for {EMBEDDING_SERVICE_KEY}: {e}")


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


def _embed_batch(texts: List[str]) -> List[List[float]]:
    """Génère les embeddings via l'Embedding Service OVH pour un batch de textes."""
    resp = requests.post(
        f"{EMBEDDING_BASE_URL}/embed",
        json={"texts": texts},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]


def load(docs: List[Dict]) -> Dict[str, int]:
    """
    Charge les documents dans ChromaDB avec embeddings OVH.
    Groupe par source et insère dans la collection correspondante.
    Déduplication par ID — upsert si document déjà présent.

    Returns:
        Résumé {source: nb_insérés}
    """
    if not docs:
        logger.warning("⚠️ ChromaDB — aucun document à charger")
        return {}

    _wake_embedding_service()
    chroma_client = _get_chroma_client()
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
                embeddings = _embed_batch(texts)
                collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=texts,
                    metadatas=metadatas,
                )
                _heartbeat()
                total += len(batch)
                logger.info(f"✅ ChromaDB [{collection_name}] — batch {i // BATCH_SIZE + 1}: {len(batch)} docs")
            except Exception as e:
                logger.error(f"❌ ChromaDB upsert error [{collection_name}] batch {i}: {e}")

        summary[source] = total
        logger.info(f"✅ ChromaDB — {total} docs dans '{collection_name}'")

    return summary

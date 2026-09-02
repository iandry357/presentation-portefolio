"""
Chargement des articles chunkés dans ChromaDB.
Collection unique referentiel_patrimoine — embeddings générés via
l'embedding-service partagé (port 8004), réveillé à la demande via
l'orchestrateur OVH.
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
    EMBEDDING_SERVICE_KEY,
    EMBEDDING_SERVICE_URL,
    OVH_ORCHESTRATOR_URL,
    WAKE_POLL_INTERVAL_SEC,
    WAKE_TIMEOUT_SEC,
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 64


# ─────────────────────────────────────────
# Réveil de l'embedding-service — pipeline standalone, appel direct et sync
# (pas de backend FastAPI ici, donc pas de httpx.AsyncClient : requests suffit)
# ─────────────────────────────────────────
def _wait_for_embedding_health() -> bool:
    """Poll le /health de l'embedding-service directement jusqu'à 200 OK."""
    url = f"{EMBEDDING_SERVICE_URL}/health"
    elapsed = 0
    while elapsed < WAKE_TIMEOUT_SEC:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                logger.info(f"✅ {EMBEDDING_SERVICE_KEY} health OK")
                return True
        except Exception:
            pass
        time.sleep(WAKE_POLL_INTERVAL_SEC)
        elapsed += WAKE_POLL_INTERVAL_SEC
    return False


def _wake_embedding_service() -> None:
    """Démarre l'embedding-service via l'orchestrateur OVH et attend qu'il soit prêt."""
    try:
        requests.post(f"{OVH_ORCHESTRATOR_URL}/wake/{EMBEDDING_SERVICE_KEY}", timeout=10)
    except Exception as e:
        logger.warning(f"⚠️ Wake signal failed for {EMBEDDING_SERVICE_KEY}: {e}")

    ready = _wait_for_embedding_health()
    if not ready:
        raise TimeoutError(
            f"{EMBEDDING_SERVICE_KEY} did not become healthy within {WAKE_TIMEOUT_SEC}s"
        )


# ─────────────────────────────────────────
# Clients
# ─────────────────────────────────────────
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


def _get_collection(client: chromadb.HttpClient) -> chromadb.Collection:
    """Récupère ou crée la collection referentiel_patrimoine."""
    return client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def _embed_batch(texts: List[str]) -> List[List[float]]:
    """Génère les embeddings via l'embedding-service HTTP (POST /embed)."""
    resp = requests.post(
        f"{EMBEDDING_SERVICE_URL}/embed",
        json={"texts": texts},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]


def _build_metadata(doc: Dict) -> Dict:
    """
    Construit les métadonnées Chroma pour un chunk.

    Coerce explicitement les None en chaîne vide — ChromaDB rejette les
    métadonnées None, et `doc.get(clé, défaut)` ne protège pas contre une
    clé présente avec la valeur None (cas de "date", qui peut être None
    par choix : pas de fallback "aujourd'hui" pour une date d'effet
    juridique absente).
    """
    meta = doc.get("metadata", {})
    return {
        "source": doc.get("source") or "",
        "date": doc.get("date") or "",
        "title": doc.get("title") or "",
        "numero": meta.get("numero") or "",
        "etat": meta.get("etat") or "",
        "date_debut": meta.get("date_debut") or "",
        "date_fin": meta.get("date_fin") or "",
        "thematique": meta.get("thematique") or "",
        "url_source": meta.get("url_source") or "",
        "chunk_index": meta.get("chunk_index", 0),
        "chunk_total": meta.get("chunk_total", 1),
        "parent_id": meta.get("parent_id") or doc["id"],
    }


def load(docs: List[Dict]) -> Dict[str, int]:
    """
    Charge les documents (articles chunkés) dans ChromaDB avec embeddings
    générés via l'embedding-service partagé. Upsert par id.

    Returns:
        Résumé {"referentiel_patrimoine": nb_chargés}
    """
    if not docs:
        logger.warning("⚠️ ChromaDB — aucun document à charger")
        return {}

    _wake_embedding_service()

    chroma_client = _get_chroma_client()
    collection = _get_collection(chroma_client)

    total = 0
    for i in range(0, len(docs), BATCH_SIZE):
        batch = docs[i:i + BATCH_SIZE]

        ids = [doc["id"] for doc in batch]
        texts = [doc.get("content", "") for doc in batch]
        metadatas = [_build_metadata(doc) for doc in batch]

        try:
            embeddings = _embed_batch(texts)
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
            total += len(batch)
            logger.info(f"✅ ChromaDB [{CHROMA_COLLECTION}] — batch {i // BATCH_SIZE + 1}: {len(batch)} docs")
        except Exception as e:
            logger.error(f"❌ ChromaDB upsert error batch {i}: {e}")

    logger.info(f"✅ ChromaDB — {total} docs dans '{CHROMA_COLLECTION}'")
    return {CHROMA_COLLECTION: total}
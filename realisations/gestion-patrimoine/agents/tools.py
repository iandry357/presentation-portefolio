"""
tools.py — Outil search_referentiel exposé au function calling (ReAct) de
assistant_agent.py. Tourne côté ml-service (FastAPI, port 8008, OVH).

Architecture validée :
- Recherche vectorielle pure via ChromaDB (collection referentiel_patrimoine),
  pas de BM25 ni de rerank.
- Embeddings générés via l'embedding-service partagé (port 8004), jamais de
  sentence-transformers embarqué dans cette image.
- embedding-service est wake-on-demand (pas toujours actif, contrairement à
  ChromaDB) : ce fichier vérifie son /health avant chaque recherche et le
  réveille via l'orchestrateur OVH si nécessaire (garde défensive — le
  backend le réveille déjà normalement en amont via orchestrator_client.py,
  mais ml-service ne peut pas supposer que cet appel a réussi ou que le
  service ne s'est pas rendormi entre-temps).
- Filtré sur la métadonnée thematique (égalité stricte).
- top_k = 3 (SEARCH_TOP_K, config.py).
- Format de sortie aligné sur les métadonnées réellement présentes dans
  ChromaDB (cf. pipeline/loaders/chroma_loader.py) : pas de champ
  chemin_hierarchique (abandonné à l'implémentation), uniquement
  numero_article + url_source, en plus du texte du chunk.
"""

import logging
import time

import chromadb
import requests
from chromadb.config import Settings

from ml.config import (
    CHROMA_COLLECTION,
    CHROMA_HOST,
    CHROMA_PASSWORD,
    CHROMA_PORT,
    CHROMA_USER,
    EMBEDDING_SERVICE_KEY,
    EMBEDDING_SERVICE_URL,
    OVH_ORCHESTRATOR_URL,
    SEARCH_TOP_K,
    WAKE_POLL_INTERVAL_SEC,
    WAKE_TIMEOUT_SEC,
)

logger = logging.getLogger(__name__)

_chroma_client = None  # instancié paresseusement, réutilisé entre les appels


# --------------------------------------------------------------------------
# Réveil défensif de l'embedding-service
# --------------------------------------------------------------------------

def _embedding_service_en_ligne() -> bool:
    try:
        resp = requests.get(f"{EMBEDDING_SERVICE_URL}/health", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def _attendre_embedding_service() -> bool:
    elapsed = 0
    while elapsed < WAKE_TIMEOUT_SEC:
        if _embedding_service_en_ligne():
            logger.info(f"✅ {EMBEDDING_SERVICE_KEY} health OK")
            return True
        time.sleep(WAKE_POLL_INTERVAL_SEC)
        elapsed += WAKE_POLL_INTERVAL_SEC
    return False


def _assurer_embedding_service_reveille() -> None:
    if _embedding_service_en_ligne():
        return

    logger.info(f"⏳ {EMBEDDING_SERVICE_KEY} non disponible, envoi du signal wake...")
    try:
        requests.post(f"{OVH_ORCHESTRATOR_URL}/wake/{EMBEDDING_SERVICE_KEY}", timeout=10)
    except Exception as exc:
        logger.warning(f"⚠️ Signal wake échoué pour {EMBEDDING_SERVICE_KEY} : {exc}")

    if not _attendre_embedding_service():
        raise TimeoutError(
            f"{EMBEDDING_SERVICE_KEY} indisponible après {WAKE_TIMEOUT_SEC}s d'attente"
        )


# --------------------------------------------------------------------------
# Client ChromaDB (toujours-actif, pas de wake nécessaire)
# --------------------------------------------------------------------------

def _get_chroma_collection() -> chromadb.Collection:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.HttpClient(
            host=CHROMA_HOST,
            port=CHROMA_PORT,
            settings=Settings(
                chroma_client_auth_provider="chromadb.auth.basic_authn.BasicAuthClientProvider",
                chroma_client_auth_credentials=f"{CHROMA_USER}:{CHROMA_PASSWORD}",
                anonymized_telemetry=False,
            ),
        )
    return _chroma_client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


# --------------------------------------------------------------------------
# Embedding de la requête
# --------------------------------------------------------------------------

def _embed_query(query: str) -> list[float]:
    resp = requests.post(
        f"{EMBEDDING_SERVICE_URL}/embed",
        json={"texts": [query]},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"][0]


# --------------------------------------------------------------------------
# Fonction principale — outil exposé à assistant_agent.py
# --------------------------------------------------------------------------

def search_referentiel(query: str, thematique: str) -> list[dict]:
    """
    Recherche vectorielle sur referentiel_patrimoine, filtrée par thématique.

    :param query: terme de recherche produit par assistant_agent (action "search_referentiel")
    :param thematique: une des 5 thématiques, filtre exact sur la métadonnée
    :return: liste de dicts {"texte": str, "numero_article": str, "url_source": str},
        vide si aucun résultat pertinent trouvé
    """
    _assurer_embedding_service_reveille()

    embedding = _embed_query(query)
    collection = _get_chroma_collection()

    resultats = collection.query(
        query_embeddings=[embedding],
        n_results=SEARCH_TOP_K,
        where={"thematique": thematique},
    )

    documents = resultats.get("documents", [[]])[0]
    metadatas = resultats.get("metadatas", [[]])[0]

    return [
        {
            "texte": doc,
            "numero_article": meta.get("numero", ""),
            "url_source": meta.get("url_source", ""),
        }
        for doc, meta in zip(documents, metadatas)
    ]
import logging
import time

import numpy as np
import requests

from pipeline import config

logger = logging.getLogger(__name__)

TIMEOUT_WAKE_SECONDS = 10
TIMEOUT_HEALTH_SECONDS = 5
TIMEOUT_HEARTBEAT_SECONDS = 3
TIMEOUT_EMBED_SECONDS = 60


def _attendre_health() -> bool:
    url = f"{config.EMBEDDING_URL}/health"
    ecoule = 0
    while ecoule < config.WAKE_TIMEOUT_SECONDS:
        try:
            if requests.get(url, timeout=TIMEOUT_HEALTH_SECONDS).status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(config.WAKE_POLL_INTERVAL_SECONDS)
        ecoule += config.WAKE_POLL_INTERVAL_SECONDS
    return False


def reveiller_service() -> None:
    """Démarre le service d'embedding via l'orchestrateur et attend son /health (bloquant)."""
    try:
        requests.post(
            f"{config.ORCHESTRATOR_BASE_URL}/wake/{config.EMBEDDING_SERVICE_KEY}",
            timeout=TIMEOUT_WAKE_SECONDS,
        )
    except requests.RequestException as e:
        logger.warning("Signal de réveil échoué : %s", e)
    if not _attendre_health():
        raise TimeoutError(
            f"Service d'embedding non disponible après {config.WAKE_TIMEOUT_SECONDS}s"
        )
    logger.info("Service d'embedding prêt")


def heartbeat() -> None:
    """Réinitialise le timer d'inactivité — fire-and-forget."""
    try:
        requests.post(
            f"{config.ORCHESTRATOR_BASE_URL}/heartbeat/{config.EMBEDDING_SERVICE_KEY}",
            timeout=TIMEOUT_HEARTBEAT_SECONDS,
        )
    except requests.RequestException as e:
        logger.debug("Heartbeat échoué : %s", e)


def embedder(textes: list[str]) -> np.ndarray:
    """Embeddings par lots de TAILLE_LOT_EMBED ; vecteurs normalisés par le service (cosinus = produit scalaire)."""
    if not textes:
        return np.empty((0, config.EMBEDDING_DIMENSIONS), dtype=np.float32)
    vecteurs = []
    for i in range(0, len(textes), config.TAILLE_LOT_EMBED):
        lot = textes[i:i + config.TAILLE_LOT_EMBED]
        heartbeat()
        resp = requests.post(
            f"{config.EMBEDDING_URL}/embed", json={"texts": lot}, timeout=TIMEOUT_EMBED_SECONDS
        )
        resp.raise_for_status()
        donnees = resp.json()
        if donnees["dim"] != config.EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Dimension reçue {donnees['dim']} != attendue {config.EMBEDDING_DIMENSIONS}"
            )
        vecteurs.extend(donnees["embeddings"])
    return np.asarray(vecteurs, dtype=np.float32)


def meilleure_cible(vec_titres: np.ndarray, vec_cibles: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Pour chaque titre : indice de la cible la plus proche et similarité cosinus max."""
    similarites = vec_titres @ vec_cibles.T
    indices = similarites.argmax(axis=1)
    return indices, similarites[np.arange(len(indices)), indices]

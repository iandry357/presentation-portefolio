import json
import logging
import time

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from pipeline import config

logger = logging.getLogger(__name__)

TIMEOUT_LLM_SECONDS = 600  # gemma3:12b déborde de la VRAM : lent (cibles)
TEMPERATURE = 0
NB_TENTATIVES = 3
PAUSE_ENTRE_TENTATIVES_SECONDS = 5


class LLMError(Exception):
    """Erreur d'appel à Ollama ou réponse non exploitable."""


class LLMJsonInvalide(LLMError):
    """Réponse reçue mais non décodable en JSON."""


def lister_modeles() -> list[str]:
    resp = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=10)
    resp.raise_for_status()
    return [m["name"] for m in resp.json().get("models", [])]


@retry(
    retry=retry_if_exception_type(requests.ConnectionError),
    stop=stop_after_attempt(NB_TENTATIVES),
    wait=wait_fixed(PAUSE_ENTRE_TENTATIVES_SECONDS),
    reraise=True,
)
def _appeler_chat(payload: dict) -> requests.Response:
    return requests.post(f"{config.OLLAMA_URL}/api/chat", json=payload, timeout=TIMEOUT_LLM_SECONDS)


def generer_json(
    modele: str, systeme: str, utilisateur: str, schema: dict, thinking: bool = False, num_ctx: int | None = None
) -> dict:
    """Appel Ollama avec sortie contrainte par un schéma JSON ; retourne le JSON décodé."""
    payload = {
        "model": modele,
        "messages": [
            {"role": "system", "content": systeme},
            {"role": "user", "content": utilisateur},
        ],
        "stream": False,
        "format": schema,
        "think": thinking,
        "options": {"temperature": TEMPERATURE},
    }
    if num_ctx:
        payload["options"]["num_ctx"] = num_ctx
    debut = time.perf_counter()
    resp = _appeler_chat(payload)
    if resp.status_code == 400 and "thinking" in resp.text:
        # Modèle sans mode raisonnement : on retire le paramètre
        payload.pop("think")
        resp = _appeler_chat(payload)
    if resp.status_code != 200:
        raise LLMError(f"Ollama HTTP {resp.status_code} : {resp.text[:300]}")
    logger.info("Ollama %s : %.1f s", modele, time.perf_counter() - debut)

    contenu = resp.json().get("message", {}).get("content", "")
    try:
        return json.loads(contenu)
    except json.JSONDecodeError as e:
        raise LLMJsonInvalide(f"Réponse non JSON : {contenu[:200]}") from e

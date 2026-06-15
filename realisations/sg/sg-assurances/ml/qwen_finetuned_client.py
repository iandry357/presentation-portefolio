"""
Qwen Finetuned Client — Appel Vertex AI Endpoint modèle fine-tuné
Réutilise les helpers de qwen_base_client.
"""

import logging

from qwen_base_client import (
    DEFAULT_MAX_TOKENS,
    TIMEOUT,
    _get_endpoint_url,
    _get_token,
)
import httpx

logger = logging.getLogger(__name__)


def predict(prompt: str, max_new_tokens: int = DEFAULT_MAX_TOKENS) -> dict:
    """
    Envoie une requête au Vertex Endpoint — modèle fine-tuné.

    Args:
        prompt         : question ou texte à soumettre
        max_new_tokens : nombre max de tokens générés

    Returns:
        {"generated_text": str, "model_type": "finetuned"}
    """
    token = _get_token()
    url   = _get_endpoint_url()

    payload = {
        "instances": [
            {
                "prompt":         prompt,
                "max_new_tokens": max_new_tokens,
            }
        ]
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }

    logger.info(f"[qwen-finetuned] Appel Vertex Endpoint...")
    response = httpx.post(url, json=payload, headers=headers, timeout=TIMEOUT)
    response.raise_for_status()

    data        = response.json()
    predictions = data.get("predictions", [{}])
    first       = predictions[0] if predictions else {}

    return {
        "generated_text": first.get("generated_text", ""),
        "model_type":     "finetuned",
    }
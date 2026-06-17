"""
Qwen Base Client — Appel Vertex AI Endpoint modèle base
Authentification via Service Account GCP.
"""

import json
import logging
import os
from pathlib import Path

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# Config
# ─────────────────────────────────────────
PROJECT_ID    = "gen-lang-client-0989575872"
LOCATION      = "europe-west4"
SA_KEY_PATH   = Path(os.getenv("SA_KEY_PATH", "/app/gcp_sa_sg.json"))
ENDPOINT_INFO = Path(os.getenv("ENDPOINT_INFO_PATH", "/app/models/qwen_endpoint_id.json"))

DEFAULT_MAX_TOKENS = 200
TIMEOUT            = 60.0

# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────
def _get_token() -> str:
    """Retourne un token d'accès GCP depuis le Service Account."""
    credentials = service_account.Credentials.from_service_account_file(
        str(SA_KEY_PATH),
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    credentials.refresh(Request())
    return credentials.token


def _get_endpoint_url() -> str:
    """Lit l'endpoint resource name depuis le fichier JSON sauvegardé."""
    if not ENDPOINT_INFO.exists():
        raise FileNotFoundError(f"[qwen-base] Endpoint info introuvable : {ENDPOINT_INFO}")

    with open(ENDPOINT_INFO, encoding="utf-8") as f:
        info = json.load(f)

    resource_name = info["endpoint_resource_name"]
    # projects/{project}/locations/{location}/endpoints/{endpoint_id}
    endpoint_id = resource_name.split("/")[-1]

    return (
        f"https://{LOCATION}-aiplatform.googleapis.com/v1/"
        f"projects/{PROJECT_ID}/locations/{LOCATION}/"
        f"endpoints/{endpoint_id}:predict"
    )


# ─────────────────────────────────────────
# Predict
# ─────────────────────────────────────────
def predict(prompt: str, max_new_tokens: int = DEFAULT_MAX_TOKENS) -> dict:
    """
    Envoie une requête au Vertex Endpoint — modèle base.

    Args:
        prompt         : question ou texte à soumettre
        max_new_tokens : nombre max de tokens générés

    Returns:
        {"generated_text": str, "model_type": "base"}
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

    logger.info(f"[qwen-base] Appel Vertex Endpoint...")
    response = httpx.post(url, json=payload, headers=headers, timeout=TIMEOUT)
    response.raise_for_status()

    data        = response.json()
    predictions = data.get("predictions", [{}])
    first       = predictions[0] if predictions else {}

    return {
        "generated_text": first.get("generated_text", ""),
        "model_type":     "base",
    }
"""
Qwen Finetuned Client — Appel llama-server OVH (remplace Vertex AI Endpoint)
API compatible OpenAI sur port 8005.
"""

import logging
import httpx

logger = logging.getLogger(__name__)

LLAMA_SERVER_URL = "http://172.17.0.1:8005/v1/chat/completions"
DEFAULT_MAX_TOKENS = 200
TIMEOUT = 120.0


def predict(prompt: str, max_new_tokens: int = DEFAULT_MAX_TOKENS) -> dict:
    payload = {
        "model":      "qwen",
        "messages":   [{"role": "user", "content": prompt}],
        "max_tokens": max_new_tokens,
    }

    logger.info("[qwen-finetuned] Appel llama-server OVH:8005...")
    response = httpx.post(LLAMA_SERVER_URL, json=payload, timeout=TIMEOUT)
    response.raise_for_status()

    data    = response.json()
    content = data["choices"][0]["message"]["content"]

    return {
        "generated_text": content,
        "model_type":     "finetuned",
    }
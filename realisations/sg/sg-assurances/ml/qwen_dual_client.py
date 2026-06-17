"""
Qwen Dual Client — Appels séquentiels base puis fine-tuné
Séquentiel intentionnel — quota T4 limité à 1 GPU simultané.
"""

import logging

import qwen_base_client
import qwen_finetuned_client

logger = logging.getLogger(__name__)

DEFAULT_MAX_TOKENS = 200


def predict(prompt: str, max_new_tokens: int = DEFAULT_MAX_TOKENS) -> dict:
    """
    Appelle séquentiellement le modèle base puis le fine-tuné.

    Args:
        prompt         : question ou texte à soumettre
        max_new_tokens : nombre max de tokens générés

    Returns:
        {
            "base":      {"generated_text": str, "model_type": "base"},
            "finetuned": {"generated_text": str, "model_type": "finetuned"}
        }
    """
    logger.info(f"[qwen-dual] Appel séquentiel — base puis finetuned")

    # Appel 1 — base
    logger.info(f"[qwen-dual] Etape 1/2 — base model...")
    base_result = qwen_base_client.predict(
        prompt=prompt,
        max_new_tokens=max_new_tokens,
    )
    logger.info(f"[qwen-dual] Etape 1/2 — base terminé")

    # Appel 2 — finetuned
    logger.info(f"[qwen-dual] Etape 2/2 — finetuned model...")
    finetuned_result = qwen_finetuned_client.predict(
        prompt=prompt,
        max_new_tokens=max_new_tokens,
    )
    logger.info(f"[qwen-dual] Etape 2/2 — finetuned terminé")

    return {
        "base":      base_result,
        "finetuned": finetuned_result,
    }
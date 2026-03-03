 
"""
Client LLM avec fallback automatique Mistral → Groq.
Gère timeout, retry, calcul coûts.
"""
import time
from typing import Dict, List
import litellm
from litellm import completion
from app.core.config import settings
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Configuration LiteLLM
litellm.set_verbose = False  # Désactiver logs verbeux en prod
litellm.success_callback = []  # Pas de callback externe

# Pricing (USD per 1M tokens)
PRICING = {
    "gemini/gemini-2.5-flash": {"input": 0.30, "output": 0.30},
    "mistral-small-latest": {"input": 0.25, "output": 0.25},
    "groq/llama-3-70b-8192": {"input": 0.0, "output": 0.0}  # Gratuit
}


def calculate_cost(model: str, tokens: int) -> float:
    """Calcule coût basé sur le model et tokens utilisés."""
    if model not in PRICING:
        return 0.0
    
    # Simplifié : on compte input+output ensemble
    price_per_million = PRICING[model]["input"]
    return (tokens * price_per_million) / 1_000_000


async def generate_with_fallback(
    system_prompt: str,
    user_prompt: str,
    history: List[Dict] = [],
    max_tokens: int = 5000,
    temperature: float = 0.3,
    models: Optional[List[str]] = None,
) -> Dict:
    """
    Génère réponse LLM avec fallback automatique.
    
    Stratégie: Mistral → Groq → Erreur
    
    Returns:
        {
            "response": str,
            "tokens_used": int,
            "provider_used": str,
            "latency_ms": int,
            "cost": float
        }
    """
    # Liste des modèles à tenter (ordre de priorité)
    # models = [
    #     ("gemini/gemini-2.5-flash", settings.GEMINI_API_KEY),
    #     ("mistral/mistral-small-latest", settings.MISTRAL_API_KEY),
    #     ("groq/llama-3-70b-8192", settings.GROQ_API_KEY)
    # ]

    _all_models = {
        "gemini": ("gemini/gemini-2.5-flash", settings.GEMINI_API_KEY),
        "mistral": ("mistral/mistral-small-latest", settings.MISTRAL_API_KEY),
        "groq": ("groq/llama-3-70b-8192", settings.GROQ_API_KEY),
    }
    _default_order = ["gemini", "mistral", "groq"]
    selected = models if models else _default_order
    models_to_try = [_all_models[m] for m in selected if m in _all_models]

    
    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": user_prompt}
    ]
    
    last_error = None
    
    for model, api_key in models_to_try:
        if not api_key:
            logger.warning(f"⚠️ {model} skipped (no API key)")
            continue
            
        try:
            start_time = time.perf_counter()
            
            logger.info(f"🔄 Trying {model}...")
            
            # Appel LiteLLM
            response = completion(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                api_key=api_key,
                timeout=10.0  # 10s timeout par provider
            )
            
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            tokens_used = response.usage.total_tokens
            cost = calculate_cost(model, tokens_used)
            
            result = {
                "response": response.choices[0].message.content,
                "tokens_used": tokens_used,
                "provider_used": model,
                "latency_ms": latency_ms,
                "cost": cost
            }
            
            logger.info(
                f"✅ {model} success: {tokens_used} tokens, "
                f"{latency_ms}ms, ${cost:.6f}"
            )
            return result
            
        except Exception as e:
            logger.warning(f"❌ {model} failed: {e}")
            last_error = e
            continue
    
    # Tous les providers ont échoué
    error_msg = f"All LLM providers failed. Last error: {last_error}"
    logger.error(error_msg)
    raise Exception(error_msg)
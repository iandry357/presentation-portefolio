 
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

logger = logging.getLogger(__name__)

# Configuration LiteLLM
litellm.set_verbose = False  # Désactiver logs verbeux en prod
litellm.success_callback = []  # Pas de callback externe

# Pricing (USD per 1M tokens)
PRICING = {
    "mistral-small-latest": {"input": 0.25, "output": 0.25},
    "openai/gpt-oss-120b": {"input": 0.59, "output": 0.79},
    "groq/llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "groq/llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "gemini/gemini-2.5-flash": {"input": 0.30, "output": 0.30},
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
    max_tokens: int = 5000,
    temperature: float = 0.3
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
    models = [
        ("mistral/mistral-small-latest", settings.MISTRAL_API_KEY),
        ("openai/gpt-oss-120b", settings.OPENAI_API_KEY),
        ("groq/llama-3.1-8b-instant", settings.GROQ_API_KEY),
        ("groq/llama-3.3-70b-versatile", settings.GROQ_API_KEY ),
        ("gemini/gemini-2.5-flash", settings.GEMINI_API_KEY)
    ]
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    last_error = None
    
    for model, api_key in models:
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
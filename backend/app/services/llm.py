from typing import List, Dict
from app.core.llm_client import generate_with_fallback
import logging

logger = logging.getLogger(__name__)


async def generate_response(question: str, context_chunks: List[Dict]) -> Dict:
    """
    Génère réponse via LLM (Mistral → Groq fallback) avec contexte RAG.
    
    Returns:
        {
            "response": str,
            "tokens_used": int,
            "provider_used": str,
            "latency_ms": int,
            "cost": float
        }
    """
    # Construction du contexte
    context = "\n\n".join([
        f"[{chunk['type'].upper()}] {chunk['title']}\n{chunk['description'][:500]}"
        for chunk in context_chunks
    ])
    
    # Prompts
    system_prompt = """Tu es un assistant qui répond aux questions sur le parcours professionnel d'Ian'ch RAKOTONIAINA.
Utilise UNIQUEMENT les informations fournies dans le contexte pour répondre.
Si la réponse n'est pas dans le contexte, dis-le clairement.
Sois concis, précis et professionnel."""
    
    user_prompt = f"""Contexte (CV d'Ian'ch) :
{context}

Question : {question}

Réponds en français, de manière concise et structurée."""
    
    # Appel LLM avec fallback
    result = await generate_with_fallback(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=500,
        temperature=0.3
    )
    
    return result
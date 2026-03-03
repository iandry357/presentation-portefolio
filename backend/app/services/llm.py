from typing import List, Dict
from app.core.llm_client import generate_with_fallback
import logging

logger = logging.getLogger(__name__)


# async def generate_response(question: str, context_chunks: List[Dict]) -> Dict:
async def generate_response(question: str, context_chunks: List[Dict], history_summary: str = "") -> Dict:
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
#     system_prompt = """Tu es un assistant qui répond aux questions sur le parcours professionnel d'Yan'ch RAKOTONIAINA.
# Sois courtois, sympathique. Oriente la personne sur les informations concernant Yan'ch
# Utilise UNIQUEMENT les informations fournies dans le contexte pour répondre.
# Il faut que tu privilégies les expériences professionnelles par rapport à sa formation sauf si questions concernant sa formation
# Si la réponse n'est pas dans le contexte, dis-le clairement."""

#     system_prompt = """Tu es un assistant qui répond aux questions sur le parcours professionnel d'Yan'ch RAKOTONIAINA.
# Sois courtois, sympathique. Oriente la personne sur les informations concernant Yan'ch
# Il faut que tu privilégies les expériences professionnelles par rapport à sa formation sauf si questions concernant sa formation
# Si la réponse n'est pas dans le contexte, dis-le clairement."""

    system_prompt = """Tu es un assistant qui répond aux questions sur le parcours professionnel d'Iandry (prononcé Yan'ch) RAKOTONIAINA"""
    
    user_prompt = f"""Contexte (CV d'Yan'ch) :
{context}

{f"Contexte conversation précédente : {history_summary}" if history_summary else ""}

Question : {question}

Sois sympathique si la question concerne une question sociale mais oriente toujours vers les informations concernant de Yan'ch.
Réponds en français, synthétique, percutant, simple et structurée. Mets en avant les réalisations et la méthodologies.
Il faut que tu restes bien sur un raisonnement où la chronologie est très importante, il ne faut pas sauter des années car chaque année est importante pour mon parcours.
Privilégie l'énurmation par bullets points dans la narration pour ne pas avoir un grop bloc de texte à chaque fois et que la lecture soit plus symphatique.
N'invente rien du tout, si la question est assez éloignée du contexte propose des informations pour recentrer les questions"""
    
    # Appel LLM avec fallback
    result = await generate_with_fallback(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        history=history,
        max_tokens=5000,
        temperature=0.3
    )
    
    return result
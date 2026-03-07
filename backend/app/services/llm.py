from typing import List, Dict
from app.core.llm_client import generate_with_fallback
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def format_period(chunk):
    start = chunk.get("start_date")
    end = chunk.get("end_date")
    if not start:
        return "Période non spécifiée"
    end_str = str(end) if end else "aujourd'hui"
    return f"{start} à {end_str}"


# async def generate_response(question: str, context_chunks: List[Dict]) -> Dict:
# async def generate_response(question: str, context_chunks: List[Dict], history_summary: str = "") -> Dict:
async def generate_response(question: str, context_chunks: List[Dict], history: List[Dict] = []) -> Dict:
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
    # context = "\n\n".join([
    #     f"[{chunk['type'].upper()}] {chunk['title']}\n{chunk['description']}"
    #     for chunk in context_chunks
    # ])
    # context = "\n\n".join([
    #     f"[{chunk['type'].upper()}] {chunk['title']}\n"
    #     f"Période : {chunk['start_date']} à {chunk.get('end_date', 'aujourd\'hui') if chunk.get('start_date') else 'Non spécifiée'}\n"
    #     f"{chunk['description']}"
    #     for chunk in context_chunks
    # ])
    
    context = "\n\n".join([
        f"[{chunk['type'].upper()}] {chunk['title']}\n"
        f"Période : {format_period(chunk)}\n"
        f"{chunk['description']}"
        for chunk in context_chunks
    ])
    current_date = datetime.now().strftime("%Y-%M-%d")

    # Bloc conversationnel depuis les messages bruts
    history_block = ""
    if history:
        exchanges = "\n".join([
            f"{'Utilisateur' if m['role'] == 'user' else 'Assistant'} : {m['content']}"
            for m in history
        ])
        history_block = f"\nHistorique de la conversation :\n{exchanges}\n"
    
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
{history_block}
Question : {question}

Sois sympathique si la question concerne une question sociale mais oriente toujours vers les informations concernant Yan'ch.
Réponds en français, synthétique, percutant, simple et structurée. Mets en avant les réalisations et les méthodologies.
Il faut que tu restes bien sur un raisonnement où la chronologie est très importante, il ne faut pas sauter des années car chaque année est importante pour mon parcours.
Privilégie l'énumération par bullets points dans la narration pour ne pas avoir un gros bloc de texte à chaque fois et que la lecture soit plus sympathique.

RÈGLE GENERAL : si tu fais un résumé global du parcours, termine TOUJOURS par une invitation courte à approfondir un sujet précis.

RÈGLE ABSOLUE : tu ne peux mentionner QUE des entreprises, projets, technologies 
et dates explicitement présents dans le contexte fourni ci-dessus.
Si une information n'est pas dans le contexte, dis EXPLICITEMENT 
"cette information n'est pas dans mon contexte" et propose de recentrer.
Il est INTERDIT d'inventer ou déduire des noms d'entreprises, de missions ou de périodes.

RÈGLE DATES : chaque expérience a ses propres dates dans le contexte au format YYYY-MM-DD.
Tu dois utiliser EXCLUSIVEMENT ces dates pour chaque expérience.
La date d'aujourd'hui ne correspond à aucune expérience passée.

RÈGLE TEMPORELLE : La date d'aujourd'hui est le {current_date}.
Utilise-la UNIQUEMENT pour calculer des durées relatives comme "il y a X ans" ou "depuis X mois".
Cette date ne correspond à AUCUNE expérience dans le contexte.
Il est INTERDIT de l'utiliser comme date de début ou de fin d'une expérience."""    
    # Appel LLM avec fallback
    result = await generate_with_fallback(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=5000,
        temperature=0.3
    )
    
    return result
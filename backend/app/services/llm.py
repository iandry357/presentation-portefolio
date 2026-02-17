from typing import List, Dict
from app.core.llm_client import generate_with_fallback
import logging

logger = logging.getLogger(__name__)


# async def generate_response(question: str, context_chunks: List[Dict]) -> Dict:
async def generate_response(
    question: str, 
    context_chunks: List[Dict],
    history: List[Dict] = []
) -> Dict:
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
        # f"[{chunk['type'].upper()}] {chunk['title']}\n{chunk['description'][:500]}"
        f"[{chunk['type'].upper()}] {chunk['title']} \n {chunk['description']} "
        for chunk in context_chunks
    ])
    
    # Prompts
#     system_prompt = """Tu es un assistant qui répond aux questions sur le parcours professionnel d'Ian'ch RAKOTONIAINA.
# Sois courtois, sympathique. Oriente la personne sur les informations concernant Ian'ch
# Utilise UNIQUEMENT les informations fournies dans le contexte pour répondre.
# Il faut que tu privilégies les expériences professionnelles par rapport à sa formation sauf si questions concernant sa formation
# Si la réponse n'est pas dans le contexte, dis-le clairement."""

#     system_prompt = """Tu es un assistant qui répond aux questions sur le parcours professionnel d'Ian'ch RAKOTONIAINA.
# Sois courtois, sympathique. Oriente la personne sur les informations concernant Ian'ch
# Il faut que tu privilégies les expériences professionnelles par rapport à sa formation sauf si questions concernant sa formation
# Si la réponse n'est pas dans le contexte, dis-le clairement."""

    # system_prompt = """Tu es un assistant qui répond aux questions sur le parcours professionnel d'Iandry (prononcé Ian'ch) RAKOTONIAINA"""
    system_prompt = """Tu es un assistant qui répond aux questions sur le parcours professionnel d'Iandry (prononcé Ian'ch) RAKOTONIAINA.

RÈGLE CRITIQUE : Si un historique de conversation est fourni ci-dessous, tu DOIS l'utiliser pour :
- Comprendre les pronoms ("il", "ça", "cette expérience")
- Résoudre les questions courtes ("combien de temps ?", "quels stacks ?")
- Maintenir le contexte temporel (si on vient de parler de 2021, les questions suivantes concernent probablement 2021)

Si la question actuelle est ambiguë MAIS que l'historique donne le contexte, réponds dans le contexte de l'historique."""
    
#     user_prompt = f"""Contexte (CV d'Ian'ch) :
# {context}

# Question : {question}

# Sois sympathique si la question concerne une question sociale mais oriente toujours vers les informations concernant de Ian'ch.
# Réponds en français, synthétique, percutant, simple et structurée. Mets en avant les réalisations et la méthodologies.
# Il faut que tu restes bien sur un raisonnement où la chronologie est très importante, il ne faut pas sauter des années car chaque année est importante pour mon parcours.
# Privilégie l'énurmation par bullets points dans la narration pour ne pas avoir un grop bloc de texte à chaque fois et que la lecture soit plus symphatique.
# N'invente rien du tout, si la question est assez éloignée du contexte propose des informations pour recentrer les questions"""

    # Construction historique avec instruction explicite
    history_section = ""
    context_instruction = ""
    
    if history:
        history_section = "=== CONTEXTE DE NOTRE CONVERSATION ===\n"
        for msg in history:
            role_label = "UTILISATEUR" if msg["role"] == "user" else "TOI (ASSISTANT)"
            content_preview = msg["content"][:300] + "..." if len(msg["content"]) > 300 else msg["content"]
            history_section += f"{role_label}: {content_preview}\n"
        history_section += "=== FIN DU CONTEXTE ===\n\n"
        
        context_instruction = """⚠️ RÈGLE ABSOLUE : La question ci-dessous fait probablement référence à ce qui a été dit dans le CONTEXTE DE CONVERSATION ci-dessus.
- NE LISTE PAS tout le CV sauf si explicitement demandé.

"""
    history_section = ""
    context_instruction = ""
    
    user_prompt = f"""{history_section}{context_instruction}== Contexte CV d'Iandry (Ian'ch) ==
{context}

Question actuelle : {question}

Sois sympathique si la question concerne une question sociale répond et oriente toujours vers les informations concernant de Ian'ch.
Réponds en français, synthétique, percutant, simple et structurée. Mets en avant les réalisations et la méthodologies.
Il faut que tu restes bien sur un raisonnement où la chronologie est très importante, il ne faut pas sauter des années car chaque année est importante pour mon parcours.
Privilégie l'énurmation par bullets points dans la narration pour ne pas avoir un grop bloc de texte à chaque fois et que la lecture soit plus symphatique.
N'invente rien du tout, si la question est assez éloignée du contexte propose des informations pour recentrer les questions"""

#     user_prompt = f"""{history_section}{context_instruction}=== CV D'IAN'CH (IANDRY RAKOTONIAINA) ===
# {context}

# === QUESTION ACTUELLE ===
# {question}

# INSTRUCTIONS DE RÉPONSE :
# - Réponds en français, synthétique, percutant
# - Utilise des bullets points pour la lisibilité
# - Respecte la chronologie (ne saute pas d'années)
# - Si la question est ambiguë mais que le contexte conversation clarifie, réponds dans ce contexte
# - ⚠️ IMPORTANT : Si tu as déjà fourni des infos dans l'historique ci-dessus, APPORTE DES DÉTAILS SUPPLÉMENTAIRES ou un angle différent. Ne répète pas mot pour mot ce que tu viens de dire.
# - N'invente rien, reste factuel"""
    
    # Appel LLM avec fallback
    result = await generate_with_fallback(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=5000,
        temperature=0.3
    )
    
    return result
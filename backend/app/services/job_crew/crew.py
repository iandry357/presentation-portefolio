import json
import logging
from crewai import Crew, Process
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.job_crew.agents import (
    build_parser_agent,
    build_analyste_agent,
    build_redacteur_agent,
)
from app.services.job_crew.tasks import (
    build_parser_task,
    build_analyste_task,
    build_redacteur_task,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Helpers
# ============================================================================

def _offer_to_text(offer_raw: dict) -> str:
    """Construit un texte complet de l'offre pour le Crew."""
    parts = [
        f"Intitulé : {offer_raw.get('intitule', '')}",
        f"Description : {offer_raw.get('description', '')}",
        f"Type de contrat : {offer_raw.get('typeContratLibelle', '')}",
        f"Expérience : {offer_raw.get('experienceLibelle', '')}",
        f"Salaire : {offer_raw.get('salaire', {}).get('libelle', '')}",
        f"Durée travail : {offer_raw.get('dureeTravailLibelleConverti', '')}",
        f"Secteur : {offer_raw.get('secteurActiviteLibelle', '')}",
        f"Entreprise : {offer_raw.get('entreprise', {}).get('nom', '')}",
        f"Description entreprise : {offer_raw.get('entreprise', {}).get('description', '')}",
        f"Compétences : {', '.join(c.get('libelle', '') for c in offer_raw.get('competences', []))}",
        f"Qualités professionnelles : {', '.join(q.get('libelle', '') for q in offer_raw.get('qualitesProfessionnelles', []))}",
        f"Contexte travail : {offer_raw.get('contexteTravail', {}).get('horaires', '')}",
    ]
    return "\n".join(p for p in parts if p.split(": ")[1])


def _safe_parse_json(text: str) -> dict:
    """Parse le JSON retourné par un agent, gère les cas mal formatés."""
    try:
        # Nettoyer les blocs markdown si présents
        clean = text.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        return json.loads(clean.strip())
    except Exception as e:
        logger.warning(f"Impossible de parser le JSON de l'agent : {e}")
        return {}


# ============================================================================
# Orchestrateur principal
# ============================================================================

async def run_enrichment_crew(
    offer_raw: dict,
    profile_text: str,
    initial_prompt: str,
    instruction: str = None,
) -> dict:
    """
    Lance le Crew d'enrichissement pour une offre.

    Args:
        offer_raw      : données brutes de l'offre France Travail
        profile_text   : texte profil construit depuis la BDD
        initial_prompt : prompt de base défini une fois (calcul initial)
        instruction    : instruction libre pour recalcul (optionnel)

    Returns:
        {
            "parsed_data": dict,
            "analysis": dict,
            "summary": str,
        }
    """
    offer_text = _offer_to_text(offer_raw)

    # Construction des agents
    parser_agent   = build_parser_agent()
    analyste_agent = build_analyste_agent(profile_text)
    redacteur_agent = build_redacteur_agent()

    # Construction des tasks
    parser_task = build_parser_task(
        agent=parser_agent,
        offer_text=f"{initial_prompt}\n\n{offer_text}" if initial_prompt else offer_text,
    )

    analyste_task = build_analyste_task(
        agent=analyste_agent,
        context_tasks=[parser_task],
    )

    redacteur_task = build_redacteur_task(
        agent=redacteur_agent,
        context_tasks=[parser_task, analyste_task],
        instruction=instruction,
    )

    # Assemblage du Crew
    crew = Crew(
        agents=[parser_agent, analyste_agent, redacteur_agent],
        tasks=[parser_task, analyste_task, redacteur_task],
        process=Process.sequential,
        verbose=False,
    )

    logger.info(f"Lancement du Crew pour l'offre : {offer_raw.get('intitule', 'N/A')}")

    result = crew.kickoff()

    # Récupération des outputs par task
    parsed_data = _safe_parse_json(parser_task.output.raw)
    analysis    = _safe_parse_json(analyste_task.output.raw)
    summary     = redacteur_task.output.raw

    logger.info(f"Crew terminé pour : {offer_raw.get('intitule', 'N/A')}")

    return {
        "parsed_data": parsed_data,
        "analysis":    analysis,
        "summary":     summary,
    }
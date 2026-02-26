from crewai import Task
from crewai.agents.agent_builder.base_agent import BaseAgent


# ============================================================================
# Task 1 - Parser
# ============================================================================

def build_parser_task(agent: BaseAgent, offer_text: str) -> Task:
    return Task(
        description=(
            f"Analyse cette offre d'emploi et extrais les informations suivantes "
            f"de manière structurée en JSON :\n\n"
            f"OFFRE :\n{offer_text}\n\n"
            f"Champs à extraire :\n"
            f"- job_objective (string ou null) : objectif principal du poste en une phrase\n"
            f"- soft_skills (list[string]) : qualités humaines, comportementales mentionnées le style de l'entreprise\n"
            f"- salary_min (float ou null) : salaire minimum en euros\n"
            f"- salary_max (float ou null) : salaire maximum en euros\n"
            f"- salary_period (string ou null) : 'mensuel' ou 'annuel'\n"
            f"- experience_years (int ou null) : années d'expérience requises\n"
            f"- experience_level (string ou null) : 'débutant', 'junior', 'confirmé', 'senior'\n"
            f"- tech_stack (list[string]) : technologies, langages, outils mentionnés\n"
            f"- contract_type (string ou null) : type de contrat\n"
            f"- remote (string ou null) : 'full', 'partial', 'none' selon les infos disponibles\n"
            f"- key_responsibilities (list[string]) : principales responsabilités\n"
            f"- benefits (list[string]) : avantages mentionnés\n"
        ),
        expected_output=(
            "Un objet JSON valide contenant uniquement les champs demandés. "
            "Aucun texte avant ou après le JSON. "
            "Utilise null pour les champs non trouvés."
        ),
        agent=agent,
    )


# ============================================================================
# Task 2 - Analyste
# ============================================================================

def build_analyste_task(agent: BaseAgent, context_tasks: list) -> Task:
    return Task(
        description=(
            "À partir du résultat du parsing de l'offre (fourni en contexte), analyse la compatibilité "
            "entre le profil du candidat et cette offre. "
            "Produis une analyse structurée en JSON avec les champs suivants :\n\n"
            "- match_score (int 0-100) : score global de compatibilité\n"
            "- strengths (list[string]) : points forts du profil pour ce poste\n"
            "- gaps (list[string]) : écarts ou compétences manquantes\n"
            "- differentiators (list[string]) : éléments différenciants du profil\n"
            "- recommendation (string) : 'forte', 'moyenne', 'faible'\n"
        ),
        expected_output=(
            "Un objet JSON valide contenant uniquement les champs demandés. "
            "Aucun texte avant ou après le JSON. "
            "Le match_score doit être un entier entre 0 et 100."
        ),
        agent=agent,
        context=context_tasks,
    )


# ============================================================================
# Task 3 - Rédacteur
# ============================================================================

def build_redacteur_task(
    agent: BaseAgent,
    context_tasks: list,
    instruction: str = None,
) -> Task:
    base_description = (
        "À partir du parsing et de l'analyse de compatibilité, "
        "rédige une fiche synthétique de l'offre en français. "
        "La fiche doit être claire, concise et actionnable. "
        "Structure la fiche avec ces sections :\n\n"
        "- **Contexte** : contexte global du poste et de l'entreprise\n"
        "- **Objectif** : mission principale du poste\n"
        "- **Attentes** : ce que l'employeur recherche\n"
        "- **Stack & Environnement** : technologies et environnement de travail\n"
        "- **Conditions** : salaire, contrat, remote, avantages\n"
        "- **Verdict** : synthèse de la compatibilité profil/offre en 2-3 phrases\n"
    )

    if instruction:
        base_description += (
            f"\n\nINSTRUCTION SPÉCIFIQUE POUR CE RECALCUL :\n{instruction}\n"
            f"Applique cette instruction en priorité dans ta rédaction."
        )

    return Task(
        description=base_description,
        expected_output=(
            "Une fiche rédigée en markdown avec les 6 sections demandées. "
            "Ton clair et professionnel. Maximum 400 mots."
        ),
        agent=agent,
        context=context_tasks,
    )
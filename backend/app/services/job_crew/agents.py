from crewai import Agent, LLM
from app.core.config import settings

# ============================================================================
# LLMs par environnement
# ============================================================================

def _llm_parser() -> LLM:
    """GPT-5-nano en dev, GPT-5-mini en prod."""
    model = (
        "openai/gpt-5-mini"    # prod
        if settings.ENVIRONMENT == "production"
        else "openai/gpt-5-nano"  # dev - à remplacer par le nom exact
    )
    return LLM(model=model, api_key=settings.OPENAI_API_KEY, temperature=0.1)


def _llm_analyste() -> LLM:
    """Magistral-small pour les deux environnements."""
    return LLM(
        model="mistral/magistral-small-latest",
        api_key=settings.MISTRAL_API_KEY,
        temperature=0.3,
    )


def _llm_redacteur() -> LLM:
    """Mistral-small en dev, Mistral-large en prod."""
    model = (
        "mistral/mistral-large-latest"
        if settings.ENVIRONMENT == "production"
        else "mistral/mistral-small-latest"
    )
    return LLM(model=model, api_key=settings.MISTRAL_API_KEY, temperature=0.5)


# ============================================================================
# Agents
# ============================================================================

def build_parser_agent() -> Agent:
    return Agent(
        role="Parseur d'offres d'emploi",
        goal=(
            "Extraire de manière structurée et précise toutes les informations "
            "clés d'une offre d'emploi : salaire, niveau d'expérience requis, "
            "stack technique, type de contrat, avantages et contexte du poste."
        ),
        backstory=(
            "Tu es un expert en analyse d'offres d'emploi. "
            "Tu lis les descriptions avec précision et tu extrais uniquement "
            "les informations factuelles sans interprétation."
        ),
        llm=_llm_parser(),
        verbose=False,
    )


def build_analyste_agent(profile_text: str) -> Agent:
    return Agent(
        role="Analyste de compatibilité profil/offre",
        goal=(
            "Analyser la compatibilité entre le profil du candidat et l'offre d'emploi. "
            "Identifier les points forts, les écarts et les éléments différenciants."
        ),
        backstory=(
            f"Tu es un consultant en recrutement expert. "
            f"Tu connais parfaitement le profil du candidat : {profile_text}. "
            f"Tu évalues objectivement l'adéquation entre ce profil et chaque offre."
        ),
        llm=_llm_analyste(),
        verbose=False,
    )


def build_redacteur_agent() -> Agent:
    return Agent(
        role="Rédacteur de fiches synthétiques",
        goal=(
            "Produire une fiche synthétique claire et lisible d'une offre d'emploi "
            "à partir des informations parsées et de l'analyse de compatibilité."
        ),
        backstory=(
            "Tu es un rédacteur spécialisé dans la présentation d'opportunités professionnelles. "
            "Tu synthétises les informations complexes en fiches concises et actionnables, "
            "en français, adaptées à une lecture rapide."
        ),
        llm=_llm_redacteur(),
        verbose=False,
    )
from app.core.config import settings
import os
os.environ.setdefault("USER_AGENT", settings.USER_AGENT)

# from langchain_openai import ChatOpenAI
# from langchain_mistralai import ChatMistralAI
# from langchain_community.utilities import GoogleSerperAPIWrapper
# from langchain_community.document_loaders import WebBaseLoader

def _get_langchain():
    from langchain_openai import ChatOpenAI
    from langchain_mistralai import ChatMistralAI
    return ChatOpenAI, ChatMistralAI

def _get_serper():
    from langchain_community.utilities import GoogleSerperAPIWrapper
    return GoogleSerperAPIWrapper

def _get_web_loader():
    from langchain_community.document_loaders import WebBaseLoader
    return WebBaseLoader

# ------------------------------------------------------------
# Modèles
# ------------------------------------------------------------

def make_discovery_llm():
    ChatOpenAI, _ = _get_langchain()
    """Agent 1 — extraction factuelle identité officielle."""
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
    )


def make_extractor_llm():
    _, ChatMistralAI = _get_langchain()
    """Agent 2 — extraction légale, activité, image employeur."""
    return ChatMistralAI(
        model="mistral-small-latest",
        temperature=0,
        api_key=settings.MISTRAL_API_KEY,
    )


def make_synthesizer_llm():
    _, ChatMistralAI = _get_langchain()
    """Agent 3 — rédaction mémo Markdown.
    magistral-small en prod, mistral-small en dev."""
    model = (
        "magistral-small-latest"
        if settings.ENVIRONMENT == "production"
        else "mistral-small-latest"
    )
    return ChatMistralAI(
        model=model,
        temperature=0.3,
        api_key=settings.MISTRAL_API_KEY,
    )


# ------------------------------------------------------------
# Outils
# ------------------------------------------------------------

def make_serper_tool():
    GoogleSerperAPIWrapper = _get_serper()
    """Recherche web Serper — 5 résultats max pour contrôler les tokens."""
    return GoogleSerperAPIWrapper(
        serper_api_key=settings.SERPER_API_KEY,
        k=5,
    )


def scrape_url(url: str, max_chars: int = None) -> str:
    WebBaseLoader = _get_web_loader()
    """
    Browse une URL et retourne le texte brut tronqué.
    Retourne une chaîne vide si la page est inaccessible.
    """
    if max_chars is None:
        max_chars = settings.COMPANY_BROWSE_MAX_CHARS
    try:
        loader = WebBaseLoader(url)
        docs = loader.load()
        text = " ".join(d.page_content for d in docs)
        return text[:max_chars]
    except Exception:
        return ""
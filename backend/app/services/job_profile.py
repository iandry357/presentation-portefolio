import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm_client import generate_with_fallback
from app.services.france_travail_client import predict_rome_codes

logger = logging.getLogger(__name__)


# ============================================================================
# Cache TTL helpers
# ============================================================================

def _cache_ttl_minutes() -> int:
    """Retourne le TTL en minutes selon l'environnement. 0 = pas de cache."""
    return 0 if settings.ENVIRONMENT == "development" else 15


def _is_cache_valid(cached_at: Optional[datetime]) -> bool:
    if not cached_at:
        return False
    ttl = _cache_ttl_minutes()
    if ttl == 0:
        return False
    age_minutes = (datetime.utcnow() - cached_at).seconds // 60
    return age_minutes < ttl


# ============================================================================
# Profile text (source de vérité pour le scoring BM25 + embeddings)
# ============================================================================

_profile_text: Optional[str] = None
_profile_text_cached_at: Optional[datetime] = None


async def build_profile_text(db: AsyncSession) -> str:
    """
    Construit le texte profil depuis la table experiences.
    Utilisé comme référence pour le scoring BM25 et les embeddings.
    Mis en cache selon TTL (0 en dev, 15min en prod).
    """
    global _profile_text, _profile_text_cached_at

    if _profile_text and _is_cache_valid(_profile_text_cached_at):
        logger.info("Profil texte servi depuis le cache")
        return _profile_text

    result = await db.execute(text("""
        SELECT role, context, technologies
        FROM experiences
        ORDER BY start_date DESC
    """))
    rows = result.fetchall()

    parts = []
    for row in rows:
        if row.role:
            parts.append(row.role)
        if row.context:
            parts.append(row.context)
        if row.technologies:
            parts.append(" ".join(row.technologies))

    _profile_text = " ".join(parts)
    _profile_text_cached_at = datetime.utcnow()

    logger.info(f"Profil texte construit : {len(_profile_text)} caractères")
    return _profile_text

async def build_profile_text_chat(db: AsyncSession) -> str:
    """
    Construit le texte profil structuré avec dates pour le chatbot RAG (cas GENERAL).
    Distinct de build_profile_text utilisé pour le scoring jobs.
    """
    result = await db.execute(text("""
        SELECT role, start_date, end_date, context, technologies
        FROM experiences
        ORDER BY start_date ASC
    """))
    rows = result.fetchall()

    parts = []
    for row in rows:
        start = str(row.start_date) if row.start_date else "?"
        end = str(row.end_date) if row.end_date else "aujourd'hui"
        parts.append(
            f"[EXPERIENCE] {row.role}\n"
            f"Période : {start} à {end}\n"
            f"{row.context or ''} {' '.join(row.technologies) if row.technologies else ''}"
        )

    return "\n\n".join(parts)

# ============================================================================
# Intitulés métier par expérience (pour ROMEO)
# ============================================================================

_rome_codes: Optional[dict[str, str]] = None
_rome_codes_cached_at: Optional[datetime] = None


def _build_fallback_intitule(role: str, technologies: list[str]) -> str:
    """Fallback si LLM indisponible : concaténation role + technologies."""
    tech_str = " ".join(technologies) if technologies else ""
    return f"{role} {tech_str}".strip()


async def _get_intitule_from_llm(role: str, context: str, technologies: list[str]) -> str:
    """
    Demande à Mistral (→ Groq fallback) un intitulé métier court pour une expérience.
    Lève une exception si les deux LLM échouent.
    """
    tech_str = ", ".join(technologies) if technologies else "non précisées"

    system_prompt = (
        "Tu es un expert en métiers de la Data et de l'Intelligence Artificielle, "
        "spécialisé dans le référentiel ROME France Travail. "
        "Tu produis uniquement un intitulé métier court (2 à 6 mots maximum), "
        "précis et ancré dans les domaines suivants : ingénierie de données, "
        "machine learning, MLOps, IA générative, orchestration de pipelines, "
        "analyse de données, data science. "
        "Tu n'utilises jamais d'intitulé généraliste comme 'Développeur logiciel' ou 'Ingénieur informatique'. "
        "Tu réponds uniquement par l'intitulé, sans phrase ni ponctuation superflue."
    )
    user_prompt = (
        f"Voici une expérience professionnelle dans le domaine Data / IA :\n"
        f"- Rôle : {role}\n"
        f"- Contexte : {context}\n"
        f"- Technologies : {tech_str}\n\n"
        f"Choisis UN SEUL intitulé métier parmi cette liste stricte, celui qui correspond le mieux à l'expérience :\n"
        f"Data Scientist, Data Engineer, Ingénieur Intelligence Artificielle, "
        f"Machine Learning Engineer, Deep Learning Engineer, NLP Engineer, "
        f"MLOps Engineer, LLM Engineer.\n"
        f"Réponds uniquement par l'intitulé choisi, sans modification, sans combinaison, sans ponctuation."
    )
    result = await generate_with_fallback(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=30,
        temperature=0.2,
        models=["mistral", "groq"],
    )
    return result["response"].strip()


async def build_rome_codes(db: AsyncSession) -> dict[str, str]:
    """
    Pour chaque expérience en base :
      1. Mistral → Groq génère un intitulé métier court
      2. Fallback code si les deux LLM échouent
      3. ROMEO prédit les codes ROME depuis cet intitulé

    Retourne un dict {code_rome: intitulé_source} dédoublonné.
    Premier intitulé ayant généré un code ROME est conservé en cas de doublon.
    Mis en cache selon TTL (0 en dev, 15min en prod).
    """
    global _rome_codes, _rome_codes_cached_at

    if _rome_codes and _is_cache_valid(_rome_codes_cached_at):
        logger.info(f"Codes ROME servis depuis le cache : {list(_rome_codes.keys())}")
        return _rome_codes

    result = await db.execute(text("""
        SELECT role, context, technologies
        FROM experiences
        ORDER BY start_date DESC
    """))
    rows = result.fetchall()

    if not rows:
        logger.warning("Aucune expérience en base, codes ROME vides")
        return {}

    rome_map: dict[str, str] = {}

    for row in rows:
        role = row.role or ""
        context = row.context or ""
        technologies = row.technologies or []

        # 1. Tentative LLM (Mistral → Groq)
        try:
            intitule = await _get_intitule_from_llm(role, context, technologies)
            logger.info(f"Intitulé LLM pour '{role}' : {intitule}")
        except Exception as e:
            intitule = _build_fallback_intitule(role, technologies)
            logger.warning(
                f"LLM échoué pour '{role}', fallback code : '{intitule}' — {e}"
            )

        # 2. Appel ROMEO avec l'intitulé obtenu
        try:
            predictions = await predict_rome_codes(intitule)
            for p in predictions:
                code = p["codeRome"]
                if code not in rome_map:
                    rome_map[code] = {
                        "intitule": intitule,
                        "libelle": p.get("libelleRome", ""),
                    }
                # if code not in rome_map:
                #     rome_map[code] = intitule
            logger.info(f"ROMEO pour '{intitule}' : {[p['codeRome'] for p in predictions]}")
        except Exception as e:
            logger.error(f"ROMEO échoué pour '{intitule}' : {e}")

    _rome_codes = rome_map
    _rome_codes_cached_at = datetime.utcnow()

    logger.info(f"Codes ROME finaux ({len(_rome_codes)}) : {list(_rome_codes.keys())}")
    return _rome_codes
import httpx
import logging
from typing import List
from rank_bm25 import BM25Okapi
from app.core.config import settings
from app.core import france_travail_config as ft
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# Profil texte (base de comparaison pour toutes les offres)
# Texte libre décrivant tes compétences, expériences et objectifs
# ============================================================================

# PROFILE_TEXT = """
# Data Engineer avec expérience en Python, pipelines de données, cloud,
# architecture de données, SQL, orchestration de workflows, ETL/ELT,
# PostgreSQL, API REST, Docker, CI/CD, et déploiement cloud.
# """

# Cache du profil (chargé une seule fois au lancement du pipeline)
_profile_text: Optional[str] = None


async def build_profile_text(db: AsyncSession) -> str:
    """
    Construit le texte profil depuis la base de données.
    Chargé une seule fois et mis en cache pour toute la durée du pipeline.
    """
    global _profile_text
    if _profile_text:
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
    logger.info(f"Profil construit depuis la BDD : {len(_profile_text)} caractères")
    return _profile_text

# ============================================================================
# Helpers
# ============================================================================

def _offer_to_text(offer: dict) -> str:
    """Construit un texte représentatif d'une offre pour le scoring."""
    parts = [
        offer.get("intitule", ""),
        offer.get("description", ""),
        offer.get("romeLibelle", ""),
        offer.get("secteurActiviteLibelle", ""),
        " ".join(c.get("libelle", "") for c in offer.get("competences", [])),
    ]
    return " ".join(p for p in parts if p).lower()


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


# ============================================================================
# BM25 - Score par mots-clés
# ============================================================================

def _bm25_scores(offers: list[dict], profile: str) -> list[float]:
    """Calcule les scores BM25 de chaque offre vs le profil."""
    corpus = [_tokenize(_offer_to_text(o)) for o in offers]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(_tokenize(profile))

    # Normalisation entre 0 et 1
    max_score = max(scores) if max(scores) > 0 else 1
    return [float(s / max_score) for s in scores]


# ============================================================================
# VoyageAI - Embeddings
# ============================================================================

async def _voyage_embed(texts: list[str]) -> list[list[float]]:
    """Génère les embeddings VoyageAI pour une liste de textes."""
    url = "https://api.voyageai.com/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {settings.VOYAGE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "input": texts,
        "model": settings.EMBEDDING_MODEL,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    return [item["embedding"] for item in data["data"]]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x ** 2 for x in a) ** 0.5
    norm_b = sum(x ** 2 for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ============================================================================
# VoyageAI - Reranker
# ============================================================================

async def _voyage_rerank(query: str, documents: list[str], top_k: int) -> list[dict]:
    """
    Reranke les documents vs la query avec VoyageAI rerank-2.

    Retourne une liste triée de {"index": int, "relevance_score": float}
    """
    url = "https://api.voyageai.com/v1/rerank"
    headers = {
        "Authorization": f"Bearer {settings.VOYAGE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "query":     query,
        "documents": documents,
        "model":     "rerank-2",
        "top_k":     top_k,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    return data.get("data", [])


# ============================================================================
# Pipeline de scoring principal
# ============================================================================

# async def score_and_filter_offers(offers: list[dict]) -> list[dict]:
async def score_and_filter_offers(offers: list[dict], db: AsyncSession) -> list[dict]:
    """
    Score les offres brutes France Travail via BM25 + embeddings + reranker.

    Retourne les offres filtrées et triées, enrichies d'un champ `_score`.
    Seules les offres au-dessus du seuil SCORING_THRESHOLD sont retenues.
    """
    if not offers:
        return []

    logger.info(f"Scoring de {len(offers)} offre(s)...")

    profile = await build_profile_text(db)

    # 1. Textes des offres
    offer_texts = [_offer_to_text(o) for o in offers]

    # 2. BM25 scores
    bm25_scores = _bm25_scores(offers, profile)

    # 3. Embeddings scores (cosine similarity)
    all_texts = [profile] + offer_texts
    all_embeddings = await _voyage_embed(all_texts)
    profile_emb = all_embeddings[0]
    offer_embs = all_embeddings[1:]
    emb_scores = [_cosine_similarity(profile_emb, e) for e in offer_embs]

    # 4. Score combiné (50% BM25 + 50% embedding)
    combined = [(bm25_scores[i] + emb_scores[i]) / 2 for i in range(len(offers))]

    # 5. Filtre par seuil avant reranking
    candidates = [
        (offers[i], combined[i])
        for i in range(len(offers))
        if combined[i] >= ft.SCORING_THRESHOLD
    ]

    if not candidates:
        logger.info("Aucune offre au-dessus du seuil de scoring")
        return []

    logger.info(f"{len(candidates)} offre(s) au-dessus du seuil, reranking...")

    # 6. Reranker VoyageAI sur les candidats retenus
    candidate_offers = [c[0] for c in candidates]
    candidate_texts  = [_offer_to_text(o) for o in candidate_offers]

    reranked = await _voyage_rerank(profile, candidate_texts, top_k=ft.SCORING_TOP_K)

    # 7. Construction du résultat final trié
    results = []
    for item in reranked:
        idx = item["index"]
        offer = candidate_offers[idx]
        offer["_score"] = item["relevance_score"]
        results.append(offer)

    logger.info(f"Scoring terminé : {len(results)} offre(s) retenue(s)")
    return results
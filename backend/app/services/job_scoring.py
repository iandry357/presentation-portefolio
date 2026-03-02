import httpx
import logging
from typing import List
from rank_bm25 import BM25Okapi
from app.core.config import settings
from app.core import france_travail_config as ft
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timedelta
from app.services.job_profile import build_profile_text

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

    Pipeline :
    1. BM25 + embeddings → score combiné
    2. Tri décroissant → top 50
    3. Sous SCORING_THRESHOLD → label "basique"
    4. Au dessus → reranker → top n/2 "priorité", reste "medium"

    Retourne les 50 offres avec leur label et score.
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

    # 5. Tri décroissant + top 50
    scored = sorted(
        [(offers[i], combined[i]) for i in range(len(offers))],
        key=lambda x: x[1],
        reverse=True,
    )[:ft.SCORING_TOP_K]

    logger.info(f"Top 50 retenu pour labellisation")

    # 6. Séparation basique / candidats au reranking
    below_threshold = [(o, s) for o, s in scored if s < ft.SCORING_THRESHOLD]
    above_threshold = [(o, s) for o, s in scored if s >= ft.SCORING_THRESHOLD]

    # 7. Label basique
    for offer, score in below_threshold:
        offer["_score"] = score
        offer["_label"] = "basique"

    if not above_threshold:
        logger.info("Aucune offre au dessus du seuil, pas de reranking")
        return [o for o, _ in scored]

    logger.info(f"{len(above_threshold)} offre(s) au dessus du seuil, reranking...")

    # 8. Reranker VoyageAI sur les candidats au dessus du seuil
    candidate_offers = [o for o, _ in above_threshold]
    candidate_texts = [_offer_to_text(o) for o in candidate_offers]
    top_k = max(1, len(candidate_offers) // 2)

    reranked = await _voyage_rerank(profile, candidate_texts, top_k=top_k)

    # Index des offres retenues en "priorité"
    priorite_indices = {item["index"] for item in reranked}

    # 9. Label priorité / medium
    for i, offer in enumerate(candidate_offers):
        offer["_score"] = above_threshold[i][1]
        offer["_label"] = "priorité" if i in priorite_indices else "medium"

    logger.info(
        f"Labellisation terminée : "
        f"{len(below_threshold)} basique, "
        f"{len(priorite_indices)} priorité, "
        f"{len(above_threshold) - len(priorite_indices)} medium"
    )

    return [o for o, _ in scored]
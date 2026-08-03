"""
Logique RAG Banque de France — ChromaDB + sentence-transformers + LiteLLM.
Collection : banque_de_france (dim 768, paraphrase-multilingual-mpnet-base-v2)
partagée entre veille (google_news) et décisions ACPR (acpr_decision) —
ce RAG est volontairement restreint à la veille uniquement (filtre metadata
source=google_news) ; les décisions ACPR restent consultables via la page
de classification, pas via ce RAG.
Embedding via Embedding Service OVH port 8004 (partagé avec SG Assurances).
"""
import logging
import os
from typing import Dict, List

import chromadb
import httpx
from chromadb.config import Settings

from app.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "banque_de_france"

# Filtre de perimetre : ce RAG ne repond que sur la veille actualites,
# pas sur les decisions ACPR (consultables via la page classification).
SOURCE_FILTER = "google_news"

OVH_ML_HOST    = os.getenv("OVH_ML_HOST", "51.68.130.23")
EMBEDDING_PORT = os.getenv("EMBEDDING_SERVICE_PORT", "8004")
EMBEDDING_URL  = f"http://{OVH_ML_HOST}:{EMBEDDING_PORT}/embed"


# ─────────────────────────────────────────
# Clients
# ─────────────────────────────────────────
def _get_chroma_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(
        host=settings.CHROMA_HOST,
        port=settings.CHROMA_PORT,
        settings=Settings(
            chroma_client_auth_provider="chromadb.auth.basic_authn.BasicAuthClientProvider",
            chroma_client_auth_credentials=f"{settings.CHROMA_USER}:{settings.CHROMA_PASSWORD}",
            anonymized_telemetry=False,
        ),
    )


async def _get_embedding(text: str) -> List[float]:
    """Appelle l'Embedding Service OVH (partage avec SG Assurances) pour generer l'embedding."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(EMBEDDING_URL, json={"texts": [text]})
        resp.raise_for_status()
        return resp.json()["embeddings"][0]


# ─────────────────────────────────────────
# Retrieval
# ─────────────────────────────────────────
async def retrieve(question: str, n_results: int) -> List[Dict]:
    """Recherche semantique dans ChromaDB banque_de_france, restreinte a la veille
    (metadata source=google_news) — les decisions ACPR sont exclues de ce RAG."""
    query_embedding = await _get_embedding(question)

    chroma_client = _get_chroma_client()
    try:
        collection = chroma_client.get_collection(COLLECTION_NAME)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where={"source": SOURCE_FILTER},
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        logger.error(f"[bdf-rag] ChromaDB error : {e}")
        return []

    docs = []
    if not results["ids"][0]:
        return docs

    for i, doc_id in enumerate(results["ids"][0]):
        meta     = results["metadatas"][0][i]
        distance = results["distances"][0][i]
        score    = round(1 - distance, 4)
        docs.append({
            "id":      doc_id,
            "source":  meta.get("source", SOURCE_FILTER),
            "title":   meta.get("title", ""),
            "content": results["documents"][0][i],
            "url":     meta.get("url", ""),
            "score":   score,
        })

    docs.sort(key=lambda x: x["score"], reverse=True)
    return docs


# ─────────────────────────────────────────
# Context builder
# ─────────────────────────────────────────
def build_context(docs: List[Dict]) -> str:
    parts = []
    for i, doc in enumerate(docs, 1):
        parts.append(
            f"[{i}] {doc['title']}\n"
            f"{doc['content'][:800]}\n"
        )
    return "\n---\n".join(parts)


# ─────────────────────────────────────────
# Generation
# ─────────────────────────────────────────
async def generate(question: str, context: str) -> Dict:
    from app.core.llm_client import generate_with_fallback

    system_prompt = """Tu es un assistant expert en régulation bancaire française, spécialisé sur l'actualité de la Banque de France et de l'ACPR.
Tu réponds en français de manière précise et structurée, en t'appuyant uniquement sur le contexte fourni.
Si le contexte ne contient pas l'information demandée, dis-le clairement.
Cite toujours les sources utilisées dans ta réponse en indiquant leur numéro [1], [2], etc."""

    user_prompt = f"""Contexte disponible :
{context}

Question : {question}

Réponds en t'appuyant sur le contexte ci-dessus."""

    return await generate_with_fallback(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=1500,
        temperature=0.2,
    )


# ─────────────────────────────────────────
# Pipeline complet
# ─────────────────────────────────────────
async def rag_pipeline(question: str, n_results: int) -> Dict:
    docs = await retrieve(question, n_results)
    if not docs:
        return {
            "answer":      "Aucun document pertinent trouvé pour répondre à cette question.",
            "sources":     [],
            "model_used":  "none",
            "tokens_used": 0,
        }

    context    = build_context(docs)
    llm_result = await generate(question, context)

    return {
        "answer":  llm_result["response"],
        "sources": [
            {
                "id":     d["id"],
                "source": d["source"],
                "title":  d["title"],
                "url":    d["url"],
                "score":  d["score"],
            }
            for d in docs
        ],
        "model_used":  llm_result["provider_used"],
        "tokens_used": llm_result["tokens_used"],
    }
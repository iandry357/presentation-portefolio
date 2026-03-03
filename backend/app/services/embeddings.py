import httpx
from typing import List, Dict
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


async def generate_embedding_mistral(query: str, model: str = "mistral-embed"):
    url = "https://api.mistral.ai/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "input": [query]
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            emb = data["data"][0]["embedding"]
            logger.info(f"✅ Embedding generated: {len(emb)} dimensions")
            return emb
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ Erreur HTTP: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"❌ Erreur lors de la génération de l'embedding: {e}")
        raise


async def vectorize_query(query: str, modelEmbeddings: str) -> List[float]:
    """
    Génère embedding pour une query via Voyage ou Mistral.
    """
    if modelEmbeddings == "voyage":
        url = "https://api.voyageai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {settings.VOYAGE_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "input": [query],
            "model": settings.EMBEDDING_MODEL
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                emb = data["data"][0]["embedding"]
                logger.info(f"✅ Embedding generated: {len(emb)} dimensions")
                return emb
        except Exception as e:
            logger.error(f"❌ Voyage API error: {e}")
            raise

    if modelEmbeddings == "mistral":
        return await generate_embedding_mistral(query)


# ============================================================================
# VoyageAI Reranking — fonctions partagées (RAG + Job Scoring)
# ============================================================================

async def voyage_rerank(query: str, documents: List[str], top_k: int) -> List[Dict]:
    """
    Appel brut API VoyageAI rerank-2.
    Partagé entre le pipeline RAG et le scoring d'offres.

    Args:
        query:     Texte de référence (question utilisateur ou profil)
        documents: Liste de textes à reranker
        top_k:     Nombre de résultats à retourner

    Returns:
        Liste de dicts [{"index": int, "relevance_score": float}]
        triée par score décroissant
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

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        results = data.get("data", [])
        logger.info(f"✅ Rerank: {len(documents)} docs → top {len(results)} retenus")
        return results
    except Exception as e:
        logger.error(f"❌ VoyageAI rerank error: {e}")
        raise


async def rerank_chunks(query: str, chunks: List[Dict], top_k: int = 5) -> List[Dict]:
    """
    Wrapper RAG : reranke des chunks CV et retourne les top_k
    avec le score de pertinence mis à jour.

    Args:
        query:  Question utilisateur
        chunks: Liste de dicts {type, id, title, description, score}
        top_k:  Nombre de chunks à retourner après reranking

    Returns:
        Liste de chunks rerankés, score remplacé par relevance_score VoyageAI
    """
    if not chunks:
        return []

    documents = [c["description"] for c in chunks]

    try:
        reranked = await voyage_rerank(query, documents, top_k=top_k)

        result = []
        for item in reranked:
            chunk = chunks[item["index"]].copy()
            chunk["score"] = round(item["relevance_score"], 4)
            result.append(chunk)

        logger.info(f"✅ rerank_chunks: {len(chunks)} → {len(result)} chunks envoyés au LLM")
        return result

    except Exception as e:
        logger.warning(f"⚠️ Rerank failed, fallback top_{top_k} vectoriel: {e}")
        # Fallback : on retourne les top_k du score vectoriel initial
        return sorted(chunks, key=lambda c: c["score"], reverse=True)[:top_k]
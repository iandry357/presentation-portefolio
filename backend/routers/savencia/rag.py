"""
Logique RAG Savencia — ChromaDB + VoyageAI + LiteLLM.
Interroge la collection savencia_veille et génère une réponse LLM.
"""
import json
import logging
from typing import List, Optional, Dict

import chromadb
import voyageai
from chromadb.config import Settings
from google.cloud import bigquery
from google.oauth2 import service_account

from app.core.config import settings

logger = logging.getLogger(__name__)

BQ_DATASET = "savencia_veille"
BQ_TABLE = "articles_bruts"
COLLECTION_NAME = settings.CHROMA_COLLECTION_SAVENCIA


def _get_bq_client() -> bigquery.Client:
    if not settings.GCP_SERVICE_ACCOUNT_JSON_SAVENCIA:
        raise RuntimeError("GCP_SERVICE_ACCOUNT_JSON_SAVENCIA non configuré")
    sa_info = json.loads(settings.GCP_SERVICE_ACCOUNT_JSON_SAVENCIA)
    credentials = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(project=settings.BQ_PROJECT_ID, credentials=credentials)


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


def _get_voyage_client() -> voyageai.Client:
    return voyageai.Client(api_key=settings.VOYAGE_API_KEY)


def _is_valid_url(url: str) -> bool:
    from urllib.parse import urlparse
    if not url:
        return False
    parsed = urlparse(url)
    return bool(parsed.path and parsed.path != "/")


def _lookup_url_from_bq(title: str) -> str:
    """Lookup URL réelle depuis BigQuery par titre."""
    try:
        client = _get_bq_client()
        escaped = title.replace("'", "\\'")
        query = f"""
            SELECT metadata FROM `{settings.BQ_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}`
            WHERE title = '{escaped}' LIMIT 1
        """
        rows = list(client.query(query).result())
        if not rows:
            return ""
        meta = rows[0].metadata
        if isinstance(meta, dict):
            return meta.get("url", "")
        return json.loads(meta).get("url", "") if meta else ""
    except Exception as e:
        logger.warning(f"⚠️ BQ URL lookup failed for '{title[:50]}': {e}")
        return ""


def retrieve(question: str, n_results: int) -> List[Dict]:
    """
    Retrieval ChromaDB sur la collection savencia_veille.
    Retourne les documents les plus proches de la question.
    """
    voyage_client = _get_voyage_client()
    chroma_client = _get_chroma_client()

    # Embedding de la question
    result = voyage_client.embed(
        [question],
        model=settings.VOYAGE_EMBEDDING_MODEL,
        input_type="query",
        output_dimension=settings.VOYAGE_EMBEDDING_DIMENSIONS,
    )
    query_embedding = result.embeddings[0]

    # Retrieval
    try:
        collection = chroma_client.get_collection(COLLECTION_NAME)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        logger.error(f"❌ ChromaDB retrieval error [{COLLECTION_NAME}]: {e}")
        return []

    all_results = []
    for i, doc_id in enumerate(results["ids"][0]):
        meta = results["metadatas"][0][i]
        distance = results["distances"][0][i]
        score = round(1 - distance, 4)

        url = meta.get("url", "")
        if not _is_valid_url(url):
            url = _lookup_url_from_bq(meta.get("title", ""))

        all_results.append({
            "id": doc_id,
            "source": meta.get("source", "google_news"),
            "title": meta.get("title", ""),
            "content": results["documents"][0][i],
            "url": url,
            "feed_name": meta.get("feed_name", ""),
            "score": score,
        })

    all_results.sort(key=lambda x: x["score"], reverse=True)
    return all_results


def build_context(docs: List[Dict]) -> str:
    """Construit le contexte à injecter dans le prompt LLM."""
    parts = []
    for i, doc in enumerate(docs, 1):
        feed_label = {
            "savencia_news": "Actualité Savencia",
            "agroalimentaire_ia": "Actualité Agroalimentaire IA",
        }.get(doc.get("feed_name", ""), "Actualité")

        parts.append(
            f"[{i}] {feed_label} — {doc['title']}\n"
            f"{doc['content'][:800]}\n"
        )
    return "\n---\n".join(parts)


async def generate(question: str, context: str) -> Dict:
    """Génère une réponse LLM avec le contexte récupéré."""
    from app.core.llm_client import generate_with_fallback

    system_prompt = """Tu es un assistant expert en industrie agroalimentaire et en stratégie d'entreprise, spécialisé sur Savencia et le secteur fromager.
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


async def rag_pipeline(question: str, n_results: int) -> Dict:
    """Pipeline RAG complet — Retrieval → Context → LLM."""
    docs = retrieve(question, n_results)
    if not docs:
        return {
            "answer": "Aucun document pertinent trouvé pour répondre à cette question.",
            "sources": [],
            "model_used": "none",
            "tokens_used": 0,
        }

    context = build_context(docs)
    llm_result = await generate(question, context)

    return {
        "answer": llm_result["response"],
        "sources": [
            {
                "id": d["id"],
                "source": d["source"],
                "title": d["title"],
                "url": d["url"],
                "score": d["score"],
            }
            for d in docs
        ],
        "model_used": llm_result["provider_used"],
        "tokens_used": llm_result["tokens_used"],
    }
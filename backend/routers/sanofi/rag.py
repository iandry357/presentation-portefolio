"""
Logique RAG Sanofi — ChromaDB + VoyageAI + LiteLLM.
Interroge les 3 collections ChromaDB et génère une réponse LLM.
"""
import logging
from typing import List, Optional, Dict

import voyageai
import chromadb
from chromadb.config import Settings

from app.core.config import settings

import json
from google.cloud import bigquery
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

SOURCE_BQ_MAP = {
    "google_news": ("sanofi_news", "raw_news"),
    "press_releases": ("sanofi_press_releases", "raw_press_releases"),
    "clinicaltrials": ("sanofi_clinical_trials", "raw_studies"),
    "pubmed": ("sanofi_pubmed", "raw_articles"),
}

# Mapping collection ChromaDB par source
COLLECTION_MAP = {
    "clinicaltrials": settings.CHROMA_COLLECTION_SANOFI_CLINICAL_TRIALS,
    "pubmed": settings.CHROMA_COLLECTION_SANOFI_PUBMED,
    "google_news": settings.CHROMA_COLLECTION_SANOFI_NEWS,
    "press_releases": settings.CHROMA_COLLECTION_SANOFI_PRESS_RELEASES,
}

VALID_SOURCES = list(COLLECTION_MAP.keys())

def _get_bq_client() -> bigquery.Client:
    sa_info = json.loads(settings.GCP_SERVICE_ACCOUNT_JSON_SANOFI)
    credentials = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(project=settings.BQ_PROJECT_ID, credentials=credentials)


def _is_valid_url(url: str) -> bool:
    from urllib.parse import urlparse
    if not url:
        return False
    parsed = urlparse(url)
    return bool(parsed.path and parsed.path != "/")


def _lookup_url_from_bq(title: str, source: str) -> str:
    if source not in SOURCE_BQ_MAP:
        return ""
    dataset, table = SOURCE_BQ_MAP[source]
    try:
        client = _get_bq_client()
        escaped = title.replace("'", "\\'")
        query = f"""
            SELECT metadata FROM `{settings.BQ_PROJECT_ID}.{dataset}.{table}`
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


def retrieve(
    question: str,
    sources: Optional[List[str]],
    n_results: int,
) -> List[Dict]:
    """
    Retrieval multi-collection ChromaDB.
    Retourne les documents les plus proches de la question.
    """
    target_sources = sources if sources else VALID_SOURCES
    target_sources = [s for s in target_sources if s in VALID_SOURCES]

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

    # Retrieval sur chaque collection
    all_results = []
    for source in target_sources:
        collection_name = COLLECTION_MAP[source]
        try:
            collection = chroma_client.get_collection(collection_name)
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )

            for i, doc_id in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i]
                logger.info(f"DEBUG meta keys: {list(meta.keys())} — url: {meta.get('url', 'MISSING')}")
                distance = results["distances"][0][i]
                score = round(1 - distance, 4)  # cosine similarity

                # all_results.append({
                #     "id": doc_id,
                #     "source": source,
                #     "title": meta.get("title", ""),
                #     "content": results["documents"][0][i],
                #     "url": meta.get("url", ""),
                #     "score": score,
                # })

                url = meta.get("url", "")
                if not _is_valid_url(url):
                    url = _lookup_url_from_bq(meta.get("title", ""), source)

                all_results.append({
                    "id": doc_id,
                    "source": source,
                    "title": meta.get("title", ""),
                    "content": results["documents"][0][i],
                    "url": url,
                    "score": score,
                })
        except Exception as e:
            logger.warning(f"⚠️ ChromaDB retrieval error [{collection_name}]: {e}")
            continue

    # Trier par score décroissant et garder les n_results meilleurs
    all_results.sort(key=lambda x: x["score"], reverse=True)
    return all_results[:n_results]


def build_context(docs: List[Dict]) -> str:
    """Construit le contexte à injecter dans le prompt LLM."""
    parts = []
    for i, doc in enumerate(docs, 1):
        source_label = {
            "clinicaltrials": "Essai clinique",
            "pubmed": "Publication scientifique",
            "google_news": "Actualité",
            "press_releases": "Press Release",
        }.get(doc["source"], doc["source"])

        parts.append(
            f"[{i}] {source_label} — {doc['title']}\n"
            f"{doc['content'][:800]}\n"
        )
    return "\n---\n".join(parts)


async def generate(question: str, context: str) -> Dict:
    """Génère une réponse LLM avec le contexte récupéré."""
    # from app.services.llm_client import generate_with_fallback
    from app.core.llm_client import generate_with_fallback

    system_prompt = """Tu es un assistant expert en intelligence pharmaceutique et data science spécialisé sur Sanofi.
Tu réponds en français de manière précise et structurée, en t'appuyant uniquement sur le contexte fourni.
Si le contexte ne contient pas l'information demandée, dis-le clairement.
Cite toujours les sources utilisées dans ta réponse en indiquant leur numéro [1], [2], etc."""

    user_prompt = f"""Contexte disponible :
{context}

Question : {question}

Réponds en t'appuyant sur le contexte ci-dessus."""

    result = await generate_with_fallback(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=1500,
        temperature=0.2,
    )

    return result


async def rag_pipeline(
    question: str,
    sources: Optional[List[str]],
    n_results: int,
) -> Dict:
    """
    Pipeline RAG complet.
    Retrieval → Context building → LLM generation.
    """
    # Retrieval
    docs = retrieve(question, sources, n_results)
    if not docs:
        return {
            "answer": "Aucun document pertinent trouvé pour répondre à cette question.",
            "sources": [],
            "model_used": "none",
            "tokens_used": 0,
        }

    # Context
    context = build_context(docs)

    # Generation
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
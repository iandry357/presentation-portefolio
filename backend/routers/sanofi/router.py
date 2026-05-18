"""
Routes FastAPI /sanofi/*.
BigQuery pour les vues analytiques, ChromaDB pour RAG et recherche.
"""
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from google.cloud import bigquery
from google.oauth2 import service_account

from app.core.config import settings
from routers.sanofi.schemas import (
    SanofiStats,
    ClinicalTrialItem, ClinicalTrialsResponse,
    PubMedItem, PubMedResponse,
    NewsItem, NewsResponse,
    RagRequest, RagResponse, RagSource,
    SearchRequest, SearchResponse, SearchResult,
)
from routers.sanofi import rag as rag_service

from google.oauth2 import service_account
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sanofi", tags=["Sanofi Intelligence"])


# ─────────────────────────────────────────
# BigQuery client
# ─────────────────────────────────────────

# def _get_bq_client() -> bigquery.Client:
#     credentials = service_account.Credentials.from_service_account_file(
#         settings.GCP_SA_KEY_PATH_SANOFI,
#         scopes=["https://www.googleapis.com/auth/cloud-platform"],
#     )
#     return bigquery.Client(
#         project=settings.BQ_PROJECT_ID,
#         credentials=credentials,
#     )

def _get_bq_client() -> bigquery.Client:
    if not settings.GCP_SERVICE_ACCOUNT_JSON_SANOFI:
        raise RuntimeError("GCP_SERVICE_ACCOUNT_JSON_SANOFI non configuré")
    sa_info = json.loads(settings.GCP_SERVICE_ACCOUNT_JSON_SANOFI)
    credentials = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(
        project=settings.BQ_PROJECT_ID,
        credentials=credentials,
    )


# ─────────────────────────────────────────
# Stats globales
# ─────────────────────────────────────────

@router.get("/stats", response_model=SanofiStats)
def get_stats():
    """Compteurs globaux — nombre de documents par source."""
    client = _get_bq_client()
    try:
        query = f"""
            SELECT
                (SELECT COUNT(*) FROM `{settings.BQ_PROJECT_ID}.{settings.BQ_DATASET_SANOFI_CLINICAL_TRIALS}.raw_studies`) AS total_clinical_trials,
                (SELECT COUNT(*) FROM `{settings.BQ_PROJECT_ID}.{settings.BQ_DATASET_SANOFI_PUBMED}.raw_articles`) AS total_pubmed,
                (SELECT COUNT(*) FROM `{settings.BQ_PROJECT_ID}.{settings.BQ_DATASET_SANOFI_NEWS}.raw_news`) AS total_news,
                (SELECT MAX(ingested_at) FROM `{settings.BQ_PROJECT_ID}.{settings.BQ_DATASET_SANOFI_NEWS}.raw_news`) AS last_updated
        """
        row = list(client.query(query).result())[0]
        return SanofiStats(
            total_clinical_trials=row.total_clinical_trials,
            total_pubmed=row.total_pubmed,
            total_news=row.total_news,
            last_updated=str(row.last_updated) if row.last_updated else None,
        )
    except Exception as e:
        logger.error(f"❌ /sanofi/stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# Clinical Trials
# ─────────────────────────────────────────

@router.get("/clinical-trials", response_model=ClinicalTrialsResponse)
def get_clinical_trials(
    limit: int = Query(100, ge=1, le=500),
    status: Optional[str] = Query(None),
    phase: Optional[str] = Query(None),
):
    """Liste des essais cliniques Sanofi depuis BigQuery."""
    client = _get_bq_client()
    try:
        where_clauses = []
        if status:
            where_clauses.append(f"JSON_VALUE(metadata, '$.status') = '{status}'")
        if phase:
            where_clauses.append(f"JSON_VALUE(metadata, '$.phase') LIKE '%{phase}%'")

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
            SELECT id, title, date, metadata
            FROM `{settings.BQ_PROJECT_ID}.{settings.BQ_DATASET_SANOFI_CLINICAL_TRIALS}.raw_studies`
            {where_sql}
            ORDER BY date DESC
            LIMIT {limit}
        """
        rows = list(client.query(query).result())
        items = []
        for row in rows:
            meta = json.loads(row.metadata or "{}")
            items.append(ClinicalTrialItem(
                id=row.id,
                title=row.title,
                date=str(row.date) if row.date else None,
                phase=meta.get("phase"),
                status=meta.get("status"),
                conditions=meta.get("conditions", []),
                study_type=meta.get("study_type"),
                sponsor=meta.get("sponsor"),
                url=meta.get("url"),
            ))
        return ClinicalTrialsResponse(total=len(items), items=items)
    except Exception as e:
        logger.error(f"❌ /sanofi/clinical-trials error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# PubMed
# ─────────────────────────────────────────

@router.get("/pubmed", response_model=PubMedResponse)
def get_pubmed(
    limit: int = Query(100, ge=1, le=500),
):
    """Liste des publications R&D Sanofi depuis BigQuery."""
    client = _get_bq_client()
    try:
        query = f"""
            SELECT id, title, date, metadata
            FROM `{settings.BQ_PROJECT_ID}.{settings.BQ_DATASET_SANOFI_PUBMED}.raw_articles`
            ORDER BY date DESC
            LIMIT {limit}
        """
        rows = list(client.query(query).result())
        items = []
        for row in rows:
            meta = json.loads(row.metadata or "{}")
            items.append(PubMedItem(
                id=row.id,
                title=row.title,
                date=str(row.date) if row.date else None,
                journal=meta.get("journal"),
                authors=meta.get("authors", []),
                keywords=meta.get("keywords", []),
                url=meta.get("url"),
            ))
        return PubMedResponse(total=len(items), items=items)
    except Exception as e:
        logger.error(f"❌ /sanofi/pubmed error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# News
# ─────────────────────────────────────────

@router.get("/news", response_model=NewsResponse)
def get_news(
    limit: int = Query(50, ge=1, le=200),
):
    """Liste des actualités Sanofi depuis BigQuery."""
    client = _get_bq_client()
    try:
        query = f"""
            SELECT id, title, date, metadata
            FROM `{settings.BQ_PROJECT_ID}.{settings.BQ_DATASET_SANOFI_NEWS}.raw_news`
            ORDER BY date DESC
            LIMIT {limit}
        """
        rows = list(client.query(query).result())
        items = []
        for row in rows:
            meta = json.loads(row.metadata or "{}")
            items.append(NewsItem(
                id=row.id,
                title=row.title,
                date=str(row.date) if row.date else None,
                source_name=meta.get("source_name"),
                url=meta.get("url"),
            ))
        return NewsResponse(total=len(items), items=items)
    except Exception as e:
        logger.error(f"❌ /sanofi/news error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# RAG
# ─────────────────────────────────────────

@router.post("/rag", response_model=RagResponse)
async def rag(body: RagRequest):
    """RAG multi-source — ChromaDB + LLM."""
    try:
        result = await rag_service.rag_pipeline(
            question=body.question,
            sources=body.sources,
            n_results=body.n_results,
        )
        return RagResponse(
            answer=result["answer"],
            sources=[RagSource(**s) for s in result["sources"]],
            model_used=result["model_used"],
            tokens_used=result["tokens_used"],
        )
    except Exception as e:
        logger.error(f"❌ /sanofi/rag error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# Recherche sémantique
# ─────────────────────────────────────────

@router.get("/search", response_model=SearchResponse)
async def search(
    query: str = Query(..., min_length=3),
    sources: Optional[List[str]] = Query(None),
    n_results: int = Query(10, ge=1, le=50),
):
    """Recherche sémantique multi-collection ChromaDB."""
    try:
        docs = rag_service.retrieve(
            question=query,
            sources=sources,
            n_results=n_results,
        )
        results = [
            SearchResult(
                id=d["id"],
                source=d["source"],
                title=d["title"],
                date=d.get("date"),
                url=d.get("url"),
                score=d["score"],
                excerpt=d["content"][:200] + "..." if len(d["content"]) > 200 else d["content"],
            )
            for d in docs
        ]
        return SearchResponse(total=len(results), results=results)
    except Exception as e:
        logger.error(f"❌ /sanofi/search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
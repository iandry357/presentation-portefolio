"""
Routes FastAPI /sqli/*.
BigQuery pour les vues analytiques, ChromaDB pour RAG, JSON local pour le topic modeling.
"""
import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from google.cloud import bigquery
from google.oauth2 import service_account

from app.core.config import settings
from routers.sqli.schemas import (
    SqliStats,
    NewsItem, NewsResponse,
    RagRequest, RagResponse, RagSource,
    TopicModelingResponse, Topic, TopicDoc,
)
from routers.sqli import rag as rag_service

from app.services.orchestrator_client import wake, heartbeat

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sqli", tags=["SQLI"])

BQ_PROJECT_ID = "gen-lang-client-0989575872"
BQ_DATASET    = "sqli_veille"
BQ_TABLE      = "articles_bruts"

TOPIC_MODELING_PATH = Path(os.getenv("SQLI_TOPIC_MODELING_PATH", str(Path(__file__).parent / "data" / "topic_modeling.json")))


# ─────────────────────────────────────────
# BigQuery client (compte de service SG)
# ─────────────────────────────────────────
def _get_bq_client() -> bigquery.Client:
    if not settings.GCP_SERVICE_ACCOUNT_JSON_SG:
        raise RuntimeError("GCP_SERVICE_ACCOUNT_JSON_SG non configuré")
    sa_info = json.loads(settings.GCP_SERVICE_ACCOUNT_JSON_SG)
    credentials = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(project=BQ_PROJECT_ID, credentials=credentials)


# ─────────────────────────────────────────
# Stats
# ─────────────────────────────────────────
@router.get("/stats", response_model=SqliStats)
def get_stats():
    """Compteurs globaux — articles de veille SQLI."""
    client = _get_bq_client()
    try:
        query = f"""
            SELECT
                COUNT(*) AS total_news,
                MAX(ingested_at) AS last_updated
            FROM `{BQ_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}`
            WHERE COALESCE(JSON_VALUE(metadata, '$.chunk_index'), '0') = '0'
        """
        row = list(client.query(query).result())[0]
        return SqliStats(
            total_news=row.total_news,
            last_updated=str(row.last_updated) if row.last_updated else None,
        )
    except Exception as e:
        logger.error(f"❌ /sqli/stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# News
# ─────────────────────────────────────────
@router.get("/news", response_model=NewsResponse)
def get_news(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    """Articles de veille SQLI depuis BigQuery."""
    client = _get_bq_client()
    try:
        count_query = f"""
            SELECT COUNT(*) AS total
            FROM `{BQ_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}`
            WHERE COALESCE(JSON_VALUE(metadata, '$.chunk_index'), '0') = '0'
        """
        total_count = list(client.query(count_query).result())[0].total

        query = f"""
            SELECT id, source, date, title, metadata
            FROM `{BQ_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}`
            WHERE COALESCE(JSON_VALUE(metadata, '$.chunk_index'), '0') = '0'
            ORDER BY date DESC
            LIMIT {limit}
            OFFSET {offset}
        """
        rows = list(client.query(query).result())
        items = []
        for row in rows:
            meta = row.metadata if isinstance(row.metadata, dict) else json.loads(row.metadata or "{}")
            items.append(NewsItem(
                id=row.id,
                title=row.title,
                date=str(row.date) if row.date else None,
                source=row.source,
                url=meta.get("url"),
            ))
        return NewsResponse(total=total_count, items=items)
    except Exception as e:
        logger.error(f"❌ /sqli/news error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# RAG
# ─────────────────────────────────────────
@router.post("/rag", response_model=RagResponse)
async def rag(body: RagRequest):
    """RAG — ChromaDB sqli_veille + LLM."""
    await wake("embedding-service")
    await heartbeat("embedding-service")
    try:
        result = await rag_service.rag_pipeline(
            question=body.question,
            n_results=body.n_results or 5,
        )
        return RagResponse(
            answer=result["answer"],
            sources=[RagSource(**s) for s in result["sources"]],
            model_used=result["model_used"],
            tokens_used=result["tokens_used"],
        )
    except Exception as e:
        logger.error(f"❌ /sqli/rag error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# ML — Topic Modeling
# ─────────────────────────────────────────
@router.get("/ml/topic-modeling", response_model=TopicModelingResponse)
async def get_topic_modeling():
    """Topic modeling LDA — résultat calculé en local (JSON monté en volume)."""
    if not TOPIC_MODELING_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Topic modeling non encore calculé — lancez le script manuellement",
        )
    try:
        with open(TOPIC_MODELING_PATH, "r", encoding="utf-8") as f:
            result = json.load(f)
        return TopicModelingResponse(
            n_topics=result["n_topics"],
            total_docs=result["total_docs"],
            topics=[Topic(**t) for t in result["topics"]],
            docs=[TopicDoc(**d) for d in result["docs"]],
        )
    except Exception as e:
        logger.error(f"❌ /sqli/ml/topic-modeling error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

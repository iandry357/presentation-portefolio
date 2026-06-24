"""
Routes FastAPI /savencia/*.
BigQuery pour les vues analytiques, ChromaDB pour RAG.
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from google.cloud import bigquery
from google.oauth2 import service_account

from app.core.config import settings
from routers.savencia.schemas import (
    SavenciaStats,
    NewsItem, NewsResponse,
    RagRequest, RagResponse, RagSource,
    VitInferenceResponse,
)
from routers.savencia import rag as rag_service
from routers.savencia import ml as ml_service

from app.services.orchestrator_client import wake, heartbeat

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/savencia", tags=["Savencia Dashboard"])

# ─────────────────────────────────────────
# BigQuery client
# ─────────────────────────────────────────

def _get_bq_client() -> bigquery.Client:
    if not settings.GCP_SERVICE_ACCOUNT_JSON_SAVENCIA:
        raise RuntimeError("GCP_SERVICE_ACCOUNT_JSON_SAVENCIA non configuré")
    sa_info = json.loads(settings.GCP_SERVICE_ACCOUNT_JSON_SAVENCIA)
    credentials = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(project=settings.BQ_PROJECT_ID, credentials=credentials)


# ─────────────────────────────────────────
# Stats
# ─────────────────────────────────────────

@router.get("/stats", response_model=SavenciaStats)
def get_stats():
    """Compteurs globaux — nombre d'articles par flux."""
    client = _get_bq_client()
    try:
        query = f"""
            SELECT
                COUNT(*) AS total_news,
                COUNTIF(JSON_VALUE(metadata, '$.feed_name') = 'savencia_news') AS total_savencia_news,
                COUNTIF(JSON_VALUE(metadata, '$.feed_name') = 'agroalimentaire_ia') AS total_agroalimentaire_ia,
                MAX(ingested_at) AS last_updated
            FROM `{settings.BQ_PROJECT_ID}.savencia_veille.articles_bruts`
        """
        row = list(client.query(query).result())[0]
        return SavenciaStats(
            total_news=row.total_news,
            total_savencia_news=row.total_savencia_news,
            total_agroalimentaire_ia=row.total_agroalimentaire_ia,
            last_updated=str(row.last_updated) if row.last_updated else None,
        )
    except Exception as e:
        logger.error(f"❌ /savencia/stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# News
# ─────────────────────────────────────────

@router.get("/news", response_model=NewsResponse)
def get_news(
    limit: int = Query(50, ge=1, le=200),
    feed_name: Optional[str] = Query(None),
):
    """Liste des actualités Savencia depuis BigQuery."""
    client = _get_bq_client()
    try:
        where_sql = ""
        if feed_name:
            where_sql = f"WHERE JSON_VALUE(metadata, '$.feed_name') = '{feed_name}'"

        query = f"""
            SELECT id, title, date, metadata
            FROM `{settings.BQ_PROJECT_ID}.savencia_veille.articles_bruts`
            {where_sql}
            ORDER BY date DESC
            LIMIT {limit}
        """
        rows = list(client.query(query).result())
        items = []
        for row in rows:
            meta = row.metadata if isinstance(row.metadata, dict) else json.loads(row.metadata or "{}")
            items.append(NewsItem(
                id=row.id,
                title=row.title,
                date=str(row.date) if row.date else None,
                source_name=meta.get("source_name"),
                feed_name=meta.get("feed_name"),
                url=meta.get("url"),
            ))
        return NewsResponse(total=len(items), items=items)
    except Exception as e:
        logger.error(f"❌ /savencia/news error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# RAG
# ─────────────────────────────────────────

@router.post("/rag", response_model=RagResponse)
async def rag(body: RagRequest):
    """RAG — ChromaDB savencia_veille + LLM."""
    try:
        result = await rag_service.rag_pipeline(
            question=body.question,
            n_results=body.n_results,
        )
        return RagResponse(
            answer=result["answer"],
            sources=[RagSource(**s) for s in result["sources"]],
            model_used=result["model_used"],
            tokens_used=result["tokens_used"],
        )
    except Exception as e:
        logger.error(f"❌ /savencia/rag error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# ML
# ─────────────────────────────────────────

@router.get("/ml/topic-modeling")
async def get_topic_modeling():
    await wake("savencia-ml")
    await heartbeat("savencia-ml")
    return await ml_service.get_topic_modeling()

@router.post("/ml/vit-inference", response_model=VitInferenceResponse)
async def vit_inference(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Le fichier doit être une image")
    await wake("savencia-ml")
    await heartbeat("savencia-ml")
    try:
        image_bytes = await file.read()
        result = await ml_service.vit_inference(image_bytes, file.content_type)
        return VitInferenceResponse(**result)
    except Exception as e:
        logger.error(f"❌ /savencia/ml/vit-inference error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
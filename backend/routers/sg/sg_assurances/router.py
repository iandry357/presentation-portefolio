"""
Routes FastAPI /sg/*.
BigQuery pour les vues analytiques, ChromaDB pour RAG, ML Service OVH pour ML.
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from google.cloud import bigquery
from google.oauth2 import service_account

from app.core.config import settings
from routers.sg.sg_assurances.schemas import (
    SgStats,
    NewsItem, NewsResponse,
    RagRequest, RagResponse, RagSource,
    NerRequest, NerResponse, NerEntity,
    QwenRequest, QwenResponse,
    YoloDetection, YoloResponse,
    TopicModelingResponse, Topic, TopicDoc,
)
from routers.sg.sg_assurances import rag as rag_service
from routers.sg.sg_assurances import ml as ml_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sg", tags=["SG Assurances"])

BQ_PROJECT_ID = "gen-lang-client-0989575872"
BQ_DATASET    = "sg_assurance_veille"
BQ_TABLE      = "articles_bruts"


# ─────────────────────────────────────────
# BigQuery client
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
@router.get("/stats", response_model=SgStats)
def get_stats():
    """Compteurs globaux — articles de veille SG Assurances."""
    client = _get_bq_client()
    try:
        query = f"""
            SELECT
                COUNT(*) AS total_news,
                MAX(ingested_at) AS last_updated
            FROM `{BQ_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}`
        """
        row = list(client.query(query).result())[0]
        return SgStats(
            total_news=row.total_news,
            last_updated=str(row.last_updated) if row.last_updated else None,
        )
    except Exception as e:
        logger.error(f"❌ /sg/stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# News
# ─────────────────────────────────────────
@router.get("/news", response_model=NewsResponse)
def get_news(limit: int = Query(50, ge=1, le=200)):
    """Articles de veille SG Assurances depuis BigQuery."""
    client = _get_bq_client()
    try:
        query = f"""
            SELECT id, source, date, title, metadata
            FROM `{BQ_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}`
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
                source=row.source,
                url=meta.get("url"),
            ))
        return NewsResponse(total=len(items), items=items)
    except Exception as e:
        logger.error(f"❌ /sg/news error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# RAG
# ─────────────────────────────────────────
@router.post("/rag", response_model=RagResponse)
async def rag(body: RagRequest):
    """RAG — ChromaDB sg_assurances_news + LLM."""
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
        logger.error(f"❌ /sg/rag error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# ML — Topic Modeling
# ─────────────────────────────────────────
@router.get("/ml/topic-modeling", response_model=TopicModelingResponse)
async def get_topic_modeling():
    """Topic modeling LDA depuis ML Service OVH."""
    try:
        result = await ml_service.get_topic_modeling()
        return TopicModelingResponse(
            n_topics=result["n_topics"],
            total_docs=result["total_docs"],
            topics=[Topic(**t) for t in result["topics"]],
            docs=[TopicDoc(**d) for d in result["docs"]],
        )
    except Exception as e:
        logger.error(f"❌ /sg/ml/topic-modeling error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# ML — YOLO
# ─────────────────────────────────────────
@router.post("/ml/yolo", response_model=YoloResponse)
async def predict_yolo(file: UploadFile = File(...)):
    """Détection zones document via YOLO — ML Service OVH."""
    try:
        result = await ml_service.predict_yolo(file)
        return YoloResponse(
            detections=[
                YoloDetection(
                    class_name=d["class"],
                    score=d["score"],
                    x1=d["x1"],
                    y1=d["y1"],
                    x2=d["x2"],
                    y2=d["y2"],
                )
                for d in result.get("detections", [])
            ]
        )
    except Exception as e:
        logger.error(f"❌ /sg/ml/yolo error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# ML — NER
# ─────────────────────────────────────────
@router.post("/ml/ner", response_model=NerResponse)
async def predict_ner(body: NerRequest):
    """Extraction entités nommées via NER — ML Service OVH."""
    try:
        result = await ml_service.predict_ner(body.text)
        return NerResponse(
            entities=[
                NerEntity(
                    text=e["text"],
                    label=e["label"],
                    score=e["score"],
                    start=e["start"],
                    end=e["end"],
                )
                for e in result.get("entities", [])
            ]
        )
    except Exception as e:
        logger.error(f"❌ /sg/ml/ner error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# ML — Qwen
# ─────────────────────────────────────────
@router.post("/ml/qwen", response_model=QwenResponse)
async def predict_qwen(body: QwenRequest):
    """Génération Qwen fine-tuné via Vertex Endpoint → ML Service OVH."""
    try:
        result = await ml_service.predict_qwen(
            prompt=body.prompt,
            max_new_tokens=body.max_new_tokens or 200,
        )
        return QwenResponse(
            generated_text=result["generated_text"],
            model_type=result["model_type"],
        )
    except Exception as e:
        logger.error(f"❌ /sg/ml/qwen error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
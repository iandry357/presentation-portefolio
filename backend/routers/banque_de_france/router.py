"""
Routes FastAPI /banque-de-france/*.
RAG sur la veille (ChromaDB banque_de_france, filtre source=google_news).
Topic modeling et autres endpoints ML a ajouter dans une prochaine etape.
"""
import logging

from fastapi import APIRouter, HTTPException

import json

from google.cloud import bigquery
from google.oauth2 import service_account

from app.core.config import settings
from routers.banque_de_france.schemas import (
    BdfStats, NewsItem, NewsResponse,
    RagRequest, RagResponse, RagSource,
    TopicModelingResponse, Topic, TopicDoc,
    EbaScoresResponse, EbaMethodology, EbaRecord, EbaRatios,
    ClassificationRequest, ClassificationResponse, ClassificationPrediction,
    ClassificationExamplesResponse, ClassificationExample,
)
from routers.banque_de_france import rag as rag_service
from routers.banque_de_france import ml as ml_service

from app.services.orchestrator_client import wake, heartbeat

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/banque-de-france", tags=["Banque de France"])

BQ_PROJECT_ID = "gen-lang-client-0989575872"
BQ_DATASET    = "banque_de_france_veille"
BQ_TABLE      = "articles_bruts"


def _get_bq_client() -> bigquery.Client:
    if not settings.GCP_SERVICE_ACCOUNT_JSON_BANQUE:
        raise RuntimeError("GCP_SERVICE_ACCOUNT_JSON_BANQUE non configuré")
    sa_info = json.loads(settings.GCP_SERVICE_ACCOUNT_JSON_BANQUE)
    credentials = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(project=BQ_PROJECT_ID, credentials=credentials)


# ─────────────────────────────────────────
# Stats
# ─────────────────────────────────────────
@router.get("/stats", response_model=BdfStats)
def get_stats():
    """Compteurs globaux — veille uniquement (source=google_news)."""
    client = _get_bq_client()
    try:
        # query = f"""
        #     SELECT COUNT(*) AS total_news, MAX(ingested_at) AS last_updated
        #     FROM `{BQ_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}`
        #     WHERE source = 'google_news'
        # """
        query = f"""
            SELECT COUNT(*) AS total_news, MAX(ingested_at) AS last_updated
            FROM (
                SELECT ingested_at
                FROM `{BQ_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}`
                WHERE source = 'google_news'
                QUALIFY ROW_NUMBER() OVER (
                    PARTITION BY LOWER(TRIM(REGEXP_REPLACE(title, r'\\s+', ' ')))
                    ORDER BY ingested_at DESC
                ) = 1
            )
        """
        row = list(client.query(query).result())[0]
        return BdfStats(
            total_news=row.total_news,
            last_updated=str(row.last_updated) if row.last_updated else None,
        )
    except Exception as e:
        logger.error(f"❌ /banque-de-france/stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# News
# ─────────────────────────────────────────
@router.get("/news", response_model=NewsResponse)
def get_news(limit: int = 20, offset: int = 0):
    """Articles de veille — source=google_news uniquement (memes decisions ACPR
    consultables via la page classification, pas melangees ici)."""
    client = _get_bq_client()
    try:
        count_query = f"""
            SELECT COUNT(*) AS total
            FROM (
                SELECT id
                FROM `{BQ_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}`
                WHERE source = 'google_news'
                QUALIFY ROW_NUMBER() OVER (
                    PARTITION BY LOWER(TRIM(REGEXP_REPLACE(title, r'\\s+', ' ')))
                    ORDER BY ingested_at DESC
                ) = 1
            )
        """
        total_count = list(client.query(count_query).result())[0].total

        query = f"""
            SELECT id, source, date, title, metadata
            FROM `{BQ_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}`
            WHERE source = 'google_news'
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY LOWER(TRIM(REGEXP_REPLACE(title, r'\\s+', ' ')))
                ORDER BY ingested_at DESC
            ) = 1
            ORDER BY date DESC
            LIMIT {limit}
            OFFSET {offset}
        """
        rows = list(client.query(query).result())
        items = []
        for row in rows:
            meta = row.metadata if isinstance(row.metadata, dict) else json.loads(row.metadata or "{}")
            items.append(NewsItem(
                id=row.id, title=row.title,
                date=str(row.date) if row.date else None,
                source=row.source, url=meta.get("url"),
            ))
        return NewsResponse(total=total_count, items=items)
    except Exception as e:
        logger.error(f"❌ /banque-de-france/news error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────
# RAG
# ─────────────────────────────────────────
@router.post("/rag", response_model=RagResponse)
async def rag(body: RagRequest):
    """RAG — ChromaDB banque_de_france (veille uniquement) + LLM."""
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
        logger.error(f"❌ /banque-de-france/rag error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ─────────────────────────────────────────
# ML — Topic Modeling
# ─────────────────────────────────────────
@router.get("/ml/topic-modeling", response_model=TopicModelingResponse)
async def get_topic_modeling():
    """Topic modeling LDA depuis ML Service OVH (veille uniquement)."""
    await wake("banque-ml")
    await heartbeat("banque-ml")
    try:
        result = await ml_service.get_topic_modeling()
        return TopicModelingResponse(
            n_topics=result["n_topics"],
            total_docs=result["total_docs"],
            topics=[Topic(**t) for t in result["topics"]],
            docs=[TopicDoc(**d) for d in result["docs"]],
        )
    except Exception as e:
        logger.error(f"❌ /banque-de-france/ml/topic-modeling error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# ML — EBA (scoring composite)
# ─────────────────────────────────────────
@router.get("/ml/eba-scores", response_model=EbaScoresResponse)
async def get_eba_scores():
    """Score composite EBA pre-calcule (CET1/levier/NPL vs moyenne UE)."""
    await wake("banque-ml")
    await heartbeat("banque-ml")
    try:
        result = await ml_service.get_eba_scores()
        return EbaScoresResponse(**result)
    except Exception as e:
        logger.error(f"❌ /banque-de-france/ml/eba-scores error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# ML — Classification (griefs ACPR)
# ─────────────────────────────────────────
@router.post("/ml/classification", response_model=ClassificationResponse)
async def predict_classification(body: ClassificationRequest):
    """Classification multi-label des griefs sur un texte de decision."""
    await wake("banque-ml")
    await heartbeat("banque-ml")
    try:
        result = await ml_service.predict_classification(body.text)
        return ClassificationResponse(**result)
    except Exception as e:
        logger.error(f"❌ /banque-de-france/ml/classification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ml/classification/examples", response_model=ClassificationExamplesResponse)
async def get_classification_examples():
    """Exemples de decisions ACPR pour la demo (avec verite terrain)."""
    await wake("banque-ml")
    await heartbeat("banque-ml")
    try:
        result = await ml_service.get_classification_examples()
        return ClassificationExamplesResponse(**result)
    except Exception as e:
        logger.error(f"❌ /banque-de-france/ml/classification/examples error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
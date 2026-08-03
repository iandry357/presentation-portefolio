"""
Routes FastAPI /banque-de-france/*.
RAG sur la veille (ChromaDB banque_de_france, filtre source=google_news).
Topic modeling et autres endpoints ML a ajouter dans une prochaine etape.
"""
import logging

from fastapi import APIRouter, HTTPException

from routers.banque_de_france.schemas import (
    RagRequest, RagResponse, RagSource,
    TopicModelingResponse, Topic, TopicDoc,
    EbaScoresResponse, EbaMethodology, EbaRecord, EbaRatios,
    ClassificationRequest, ClassificationResponse, ClassificationPrediction,
)
from routers.banque_de_france import rag as rag_service
from routers.banque_de_france import ml as ml_service

from app.services.orchestrator_client import wake, heartbeat

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/banque-de-france", tags=["Banque de France"])


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
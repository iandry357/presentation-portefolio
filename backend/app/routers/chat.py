# curl -X POST http://localhost:8000/api/chat/ \
#   -H "Content-Type: application/json" \
#   -d '{"message": "Ton expérience en ML ?"}'

from fastapi import APIRouter, HTTPException
from app.schemas.chat import ChatRequest, ChatResponse, SourceReference
from app.services.rag import rag_pipeline
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint chat principal avec RAG + logging complet.
    """
    try:
        # Appel pipeline RAG avec session_id
        result = await rag_pipeline(
            question=request.message,
            session_id=request.session_id,
            top_k=settings.RETRIEVAL_TOP_K,
            score_threshold=settings.RETRIEVAL_SCORE_THRESHOLD
        )
        
        # Construire sources (top 3)
        sources = [
            SourceReference(
                type=chunk['type'],
                title=chunk['title'],
                score=chunk['score'],
                id=chunk['id']
            )
            for chunk in result['context_chunks'][:3]
        ]
        
        return ChatResponse(
            query_id=result['query_id'],
            response=result['response'],
            sources=sources,
            tokens_used=result['tokens_used'],
            cost=result['cost'],
            provider_used=result['provider_used']
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur chat: {str(e)}")
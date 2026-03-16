from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.schemas.feedback import FeedbackCreate, FeedbackCreateResponse
from app.models.feedback import PageFeedback, FeedbackAnswer
from app.models.cv import ChatSession
import logging

router = APIRouter(prefix="/feedback", tags=["feedback"])
logger = logging.getLogger(__name__)


@router.post("", response_model=FeedbackCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    feedback_data: FeedbackCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Créer un nouveau feedback avec ses réponses
    
    - Valide que la session existe
    - Crée l'entrée page_feedbacks
    - Crée les entrées feedback_answers associées
    - Transaction atomique
    """
    try:
        # 1. Vérifier que la session existe
        result = await db.execute(
            select(ChatSession).where(ChatSession.session_id == feedback_data.session_id)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Session {feedback_data.session_id} not found"
            )

        # 2. Créer le feedback principal
        feedback = PageFeedback(
            session_id=feedback_data.session_id,
            page_route=feedback_data.page_route,
            page_type=feedback_data.page_type,
            rating=feedback_data.rating,
            job_offer_id=feedback_data.job_offer_id,
            company_profile_id=feedback_data.company_profile_id
        )
        
        db.add(feedback)
        await db.flush()  # Pour obtenir l'ID du feedback

        # 3. Créer les réponses aux questions
        for answer_data in feedback_data.answers:
            answer = FeedbackAnswer(
                feedback_id=feedback.id,
                question_key=answer_data.question_key,
                comment=answer_data.comment
            )
            db.add(answer)

        # 4. Commit transaction
        await db.commit()
        await db.refresh(feedback)

        logger.info(
            f"Feedback created - ID: {feedback.id}, Page: {feedback.page_type}, "
            f"Rating: {feedback.rating}, Answers: {len(feedback_data.answers)}"
        )

        return FeedbackCreateResponse(
            id=feedback.id,
            message="Feedback enregistré avec succès"
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating feedback: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'enregistrement du feedback"
        )
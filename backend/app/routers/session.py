from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from app.core.database import get_db
from pydantic import BaseModel
import logging
from uuid import UUID

router = APIRouter(prefix="/session", tags=["session"])
logger = logging.getLogger(__name__)


class SessionInit(BaseModel):
    """Initialisation de session"""
    session_id: UUID


class SessionResponse(BaseModel):
    """Réponse initialisation session"""
    session_id: str
    created: bool
    message: str


@router.post("/init", response_model=SessionResponse)
async def initialize_session(
    session_data: SessionInit,
    db: AsyncSession = Depends(get_db)
):
    """
    Initialiser une session globale
    
    - Vérifie si la session existe déjà en base
    - Si non, la crée avec des valeurs par défaut
    - Retourne le statut de la session
    
    Appelé automatiquement au chargement de chaque page
    pour garantir l'existence de la session en base.
    """
    try:
        session_id_str = str(session_data.session_id)
        
        # Vérifier si la session existe
        result = await db.execute(
            select(1).select_from(text("chat_sessions")).where(
                text("session_id = :session_id")
            ).params(session_id=session_id_str)
        )
        session_exists = result.scalar_one_or_none()
        
        if session_exists:
            logger.debug(f"Session {session_id_str} already exists")
            return SessionResponse(
                session_id=session_id_str,
                created=False,
                message="Session already initialized"
            )
        
        # Créer la session
        await db.execute(
            text(
                "INSERT INTO chat_sessions (session_id, created_at, question_count, total_tokens, total_cost) "
                "VALUES (:session_id, NOW(), 0, 0, 0.0)"
            ).params(session_id=session_id_str)
        )
        await db.commit()
        
        logger.info(f"Session {session_id_str} created successfully")
        
        return SessionResponse(
            session_id=session_id_str,
            created=True,
            message="Session initialized successfully"
        )
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error initializing session: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'initialisation de la session"
        )
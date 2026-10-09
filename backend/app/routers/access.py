from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import uuid
from typing import Optional

from app.core import access_control as ac
from app.core.database import get_db
from app.schemas.access import AccessCodeSubmit, AccessStatusResponse

router = APIRouter(prefix="/access", tags=["access"])
logger = logging.getLogger(__name__)


def _reply(visitor_id: uuid.UUID, status_code: int, content: dict, headers: dict | None = None) -> JSONResponse:
    """
    Réponse JSON portant toujours le cookie visiteur.
    Un cookie posé sur la Response injectée est perdu quand la route lève une
    HTTPException : on construit donc la réponse nous-mêmes, y compris en erreur,
    sinon le compteur anti brute-force ne verrait jamais le même visiteur.
    """
    reply = JSONResponse(status_code=status_code, content=content, headers=headers)
    ac.set_visitor_cookie(reply, visitor_id)
    return reply


def _blocked_reply(visitor_id: uuid.UUID, retry_after: int) -> JSONResponse:
    return _reply(
        visitor_id,
        status.HTTP_429_TOO_MANY_REQUESTS,
        {"detail": "Trop de tentatives, réessayez plus tard"},
        headers={"Retry-After": str(retry_after)},
    )


@router.post(
    "/unlock",
    response_model=AccessStatusResponse,
    responses={401: {"description": "Code incorrect"}, 429: {"description": "Trop de tentatives"}},
)
async def unlock(
    payload: AccessCodeSubmit,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Déverrouiller l'accès privé avec le code

    - Bloqué (trop d'échecs) : 429, le code n'est même pas lu
    - Code correct : compteur remis à zéro, jeton créé, cookie httpOnly posé
    - Code faux : compteur +1 (401, ou 429 si le seuil vient d'être atteint)
    """
    try:
        # Le cookie visiteur est posé plus bas sur la réponse finale
        visitor_id = ac.get_or_create_visitor_id(request, Response())

        blocked = await ac.get_block_seconds(db, visitor_id)
        if blocked > 0:
            return _blocked_reply(visitor_id, blocked)

        if ac.verify_code(payload.code):
            await ac.reset_failures(db, visitor_id)
            token = await ac.create_access_token(db)
            body = AccessStatusResponse(
                unlocked=True,
                expires_in_seconds=round(ac.ACCESS_TOKEN_TTL_MINUTES * 60),
            )
            reply = _reply(visitor_id, status.HTTP_200_OK, body.model_dump())
            ac.set_access_cookie(reply, token)
            return reply

        blocked = await ac.register_failure(db, visitor_id)
        if blocked > 0:
            logger.warning(f"Access blocked for visitor {str(visitor_id)[:8]} ({blocked}s)")
            return _blocked_reply(visitor_id, blocked)

        return _reply(visitor_id, status.HTTP_401_UNAUTHORIZED, {"detail": "Code incorrect"})

    except Exception as e:
        await db.rollback()
        logger.error(f"Error unlocking access: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du déverrouillage"
        )


@router.get("/status", response_model=AccessStatusResponse)
async def get_status(remaining: Optional[int] = Depends(ac.get_access_remaining)):
    """
    Suis-je déverrouillé ? Lecture seule : ne prolonge pas la fenêtre de 15 min.
    """
    return AccessStatusResponse(unlocked=remaining is not None, expires_in_seconds=remaining)


@router.post("/lock", response_model=AccessStatusResponse)
async def lock(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Verrouiller manuellement : supprime le jeton en base et efface le cookie
    """
    try:
        token = request.cookies.get(ac.ACCESS_COOKIE_NAME)
        if token:
            await ac.revoke_access_token(db, token)
    except Exception as e:
        await db.rollback()
        logger.error(f"Error locking access: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du verrouillage"
        )

    ac.clear_access_cookie(response)
    return AccessStatusResponse(unlocked=False)

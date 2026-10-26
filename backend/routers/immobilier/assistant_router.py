"""
Route POST /immobilier/assistant/chat (assistant bailleur de la page Immobilier).
Publique avec limite de débit par visiteur (cookie) et plafond global : la route appelle une API payante.
Les compteurs sont en mémoire, donc par instance du backend (2 au maximum).
"""
import logging
import time
from collections import deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.core.access_control import get_access_state, get_or_create_visitor_id
from app.services.immobilier_assistant import repondre
from routers.immobilier.assistant_schemas import AssistantReponse, AssistantRequete

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/immobilier/assistant", tags=["Immobilier assistant"])

# Paramètres
FENETRE_SEC = 3600
LIMITE_VERROUILLE = 10       # questions par visiteur et par fenêtre, accès verrouillé
LIMITE_DEVERROUILLE = 60     # accès déverrouillé
LIMITE_GLOBALE = 300         # toutes personnes confondues, par instance

_appels: dict[str, deque] = {}


def _fenetre(cle: str, maintenant: float) -> deque:
    appels = _appels.setdefault(cle, deque())
    while appels and maintenant - appels[0] > FENETRE_SEC:
        appels.popleft()
    return appels


def _verifier_debit(visiteur: str, limite: int) -> None:
    maintenant = time.monotonic()
    fenetres = [_fenetre(visiteur, maintenant), _fenetre("global", maintenant)]
    if len(fenetres[0]) >= limite or len(fenetres[1]) >= LIMITE_GLOBALE:
        raise HTTPException(status_code=429, detail="Limite de questions atteinte, réessayez plus tard")
    for appels in fenetres:
        appels.append(maintenant)


@router.post("/chat", response_model=AssistantReponse)
async def chat(
    requete: AssistantRequete, request: Request, response: Response, deverrouille: bool = Depends(get_access_state),
):
    visiteur = str(get_or_create_visitor_id(request, response))
    _verifier_debit(visiteur, LIMITE_DEVERROUILLE if deverrouille else LIMITE_VERROUILLE)
    try:
        return await repondre(requete.question, [m.model_dump() for m in requete.historique])
    except Exception as e:
        logger.error(f"[immobilier_assistant] Erreur : {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Assistant momentanément indisponible")

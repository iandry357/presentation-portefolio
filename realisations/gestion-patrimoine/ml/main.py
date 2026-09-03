"""
main.py — Service FastAPI ml-service (port 8008) du MVP gestion-patrimoine.

Expose un unique endpoint /chat (boucle ReAct via assistant_agent.repondre)
et /health pour le polling de l'orchestrateur OVH et du backend après wake.

Stateless : aucun état conservé côté service. Le backend fournit
systématiquement soit le profil (premier tour), soit l'historique complet
(tours suivants) — le premier tour est déduit côté assistant_agent par
l'absence d'historique.
"""

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agents.assistant_agent import AssistantAgentError, repondre

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="gestion-patrimoine-ml")


# --------------------------------------------------------------------------
# Schémas requête / réponse
# --------------------------------------------------------------------------

class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    thematique: str
    profil: Optional[dict] = None          # fourni uniquement au premier tour
    historique: Optional[list[Message]] = None  # fourni à partir du 2e tour


class ArticleCiteResponse(BaseModel):
    numero_article: str
    url_source: str


class ChatResponse(BaseModel):
    texte: str
    articles_cites: list[ArticleCiteResponse]
    tokens_entree: int
    tokens_sortie: int
    latence_ms: int


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    historique_dicts = (
        [m.model_dump() for m in request.historique] if request.historique else []
    )

    if not historique_dicts and request.profil is None:
        raise HTTPException(
            status_code=400,
            detail="Le profil client est requis au premier tour (historique vide).",
        )

    try:
        resultat = repondre(
            thematique=request.thematique,
            profil=request.profil,
            historique=historique_dicts,
        )
    except AssistantAgentError as exc:
        logger.error("Échec assistant_agent : %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return resultat
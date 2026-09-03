"""
Routes FastAPI /gestion-patrimoine/*.

- POST /profil : génère un profil client via profil_agent (appel direct
  Mistral/Gemini depuis le backend, pas de service OVH dédié — latence
  minimale, profil_agent n'a aucune dépendance à l'infra OVH), crée la
  session en base, enregistre le message role='profil_agent'.
- POST /chat : reconstruit l'historique depuis PostgreSQL, réveille
  gestion-patrimoine-ml (et embedding-service, nécessaire à son tool
  search_referentiel) via l'orchestrateur OVH, appelle /chat sur
  ml-service, enregistre le message role='user' (si tour >= 2) puis
  role='assistant'.

Premier tour = aucun message user/assistant en base pour cette session
(le profil suffit à déclencher la première synthèse, aucun message
utilisateur n'est requis à ce stade).
"""

import json
import logging
import time
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.orchestrator_client import OVH_ML_HOST, SERVICE_PORTS, heartbeat, wake
from routers.gestion_patrimoine.profil_agent import ProfilAgentError, generer_profil
from routers.gestion_patrimoine.schemas import (
    ChatRequest,
    ChatResponseSchema,
    GenererProfilRequest,
    GenererProfilResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gestion-patrimoine", tags=["Gestion Patrimoine"])

ML_SERVICE_KEY = "gestion-patrimoine-ml"
ML_SERVICE_TIMEOUT_SEC = 400.0  # couvre le pire cas : 3 itérations x 120s côté ml-service + marge


def _ml_service_url() -> str:
    port = SERVICE_PORTS[ML_SERVICE_KEY]
    return f"http://{OVH_ML_HOST}:{port}/chat"


# --------------------------------------------------------------------------
# POST /gestion-patrimoine/profil
# --------------------------------------------------------------------------

@router.post("/profil", response_model=GenererProfilResponse)
async def generer_profil_route(
    body: GenererProfilRequest,
    db: AsyncSession = Depends(get_db),
):
    """Génère un profil client synthétique, crée la session, enregistre le coût."""
    debut = time.perf_counter()
    try:
        resultat = generer_profil(thematique=body.thematique)
    except ProfilAgentError as e:
        logger.error(f"❌ /gestion-patrimoine/profil error: {e}")
        raise HTTPException(status_code=502, detail=str(e))

    latence_ms = int((time.perf_counter() - debut) * 1000)
    profil = resultat["profil"]
    usage = resultat["usage"]
    session_id = uuid4()

    try:
        await db.execute(
            text(
                "INSERT INTO gestion_patrimoine_sessions (session_id, thematique, profil, created_at) "
                "VALUES (:session_id, :thematique, CAST(:profil AS JSONB), NOW())"
            ).params(
                session_id=str(session_id),
                thematique=profil["thematique"],
                profil=json.dumps(profil),
            )
        )
        await db.execute(
            text(
                "INSERT INTO gestion_patrimoine_messages "
                "(session_id, role, contenu, tokens_entree, tokens_sortie, cout_estime, latence_ms, articles_cites, created_at) "
                "VALUES (:session_id, 'profil_agent', :contenu, :tokens_entree, :tokens_sortie, :cout_estime, :latence_ms, CAST('[]' AS JSONB), NOW())"
            ).params(
                session_id=str(session_id),
                contenu=json.dumps(profil),
                tokens_entree=usage["tokens_entree"],
                tokens_sortie=usage["tokens_sortie"],
                cout_estime=usage["cout_estime"],
                latence_ms=latence_ms,
            )
        )
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"❌ /gestion-patrimoine/profil DB error: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de l'enregistrement du profil")

    return GenererProfilResponse(session_id=session_id, profil=profil)


# --------------------------------------------------------------------------
# POST /gestion-patrimoine/chat
# --------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponseSchema)
async def chat_route(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Envoie un message à assistant_agent (via ml-service) et enregistre l'échange."""
    session_id_str = str(body.session_id)

    result = await db.execute(
        text("SELECT thematique, profil FROM gestion_patrimoine_sessions WHERE session_id = :session_id").params(
            session_id=session_id_str
        )
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Session introuvable")
    thematique, profil = row.thematique, row.profil

    result = await db.execute(
        text(
            "SELECT role, contenu FROM gestion_patrimoine_messages "
            "WHERE session_id = :session_id AND role IN ('user', 'assistant') "
            "ORDER BY created_at ASC"
        ).params(session_id=session_id_str)
    )
    historique = [{"role": r.role, "content": r.contenu} for r in result.fetchall()]
    premier_tour = len(historique) == 0

    if not premier_tour and not body.message:
        raise HTTPException(status_code=400, detail="Le champ message est requis à partir du 2e tour.")

    await wake("embedding-service")
    await heartbeat("embedding-service")
    await wake(ML_SERVICE_KEY)
    await heartbeat(ML_SERVICE_KEY)

    payload = {"thematique": thematique}
    if premier_tour:
        payload["profil"] = profil
    else:
        historique.append({"role": "user", "content": body.message})
        payload["historique"] = historique

        try:
            async with httpx.AsyncClient(timeout=ML_SERVICE_TIMEOUT_SEC) as client:
                response = await client.post(_ml_service_url(), json=payload)
                if response.status_code >= 400:
                    logger.error(f"❌ /gestion-patrimoine/chat ml-service returned {response.status_code}: {response.text}")
                    raise HTTPException(status_code=502, detail=f"ml-service error: {response.text}")
                data = response.json()
        except httpx.HTTPError as e:
            logger.error(f"❌ /gestion-patrimoine/chat ml-service unreachable: {e}")
            raise HTTPException(status_code=502, detail="Échec de communication avec ml-service")

    try:
        if not premier_tour:
            await db.execute(
                text(
                    "INSERT INTO gestion_patrimoine_messages "
                    "(session_id, role, contenu, tokens_entree, tokens_sortie, cout_estime, latence_ms, articles_cites, created_at) "
                    "VALUES (:session_id, 'user', :contenu, 0, 0, 0, 0, CAST('[]' AS JSONB), NOW())"
                ).params(session_id=session_id_str, contenu=body.message)
            )

        await db.execute(
            text(
                "INSERT INTO gestion_patrimoine_messages "
                "(session_id, role, contenu, tokens_entree, tokens_sortie, cout_estime, latence_ms, articles_cites, created_at) "
                "VALUES (:session_id, 'assistant', :contenu, :tokens_entree, :tokens_sortie, 0, :latence_ms, CAST(:articles_cites AS JSONB), NOW())"
            ).params(
                session_id=session_id_str,
                contenu=data["texte"],
                tokens_entree=data["tokens_entree"],
                tokens_sortie=data["tokens_sortie"],
                latence_ms=data["latence_ms"],
                articles_cites=json.dumps(data["articles_cites"]),
            )
        )
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"❌ /gestion-patrimoine/chat DB error: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de l'enregistrement de l'échange")

    return ChatResponseSchema(texte=data["texte"], articles_cites=data["articles_cites"], latence_ms=data["latence_ms"])
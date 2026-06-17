"""
Embedding Service — sentence-transformers
Modèle : paraphrase-multilingual-mpnet-base-v2 (dim 768)
Port   : 8004

Endpoints :
    GET  /health  → health check
    POST /embed   → génère embeddings pour une liste de textes
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "paraphrase-multilingual-mpnet-base-v2"
EMBEDDING_DIM   = 768

# ─────────────────────────────────────────
# State global
# ─────────────────────────────────────────
_model: SentenceTransformer = None

# ─────────────────────────────────────────
# Lifespan — chargement au démarrage
# ─────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model
    logger.info(f"[embedding] Chargement modèle : {EMBEDDING_MODEL}")
    _model = SentenceTransformer(EMBEDDING_MODEL)
    logger.info(f"[embedding] Modèle prêt — dim={EMBEDDING_DIM}")
    yield
    logger.info("[embedding] Arrêt")

app = FastAPI(title="Embedding Service", version="1.0.0", lifespan=lifespan)

# ─────────────────────────────────────────
# Schémas
# ─────────────────────────────────────────
class EmbedRequest(BaseModel):
    texts: list[str]

class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    model: str
    dim: int

# ─────────────────────────────────────────
# Routes
# ─────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "model":  EMBEDDING_MODEL,
        "dim":    EMBEDDING_DIM,
    }

@app.post("/embed", response_model=EmbedResponse)
def embed(request: EmbedRequest):
    if _model is None:
        raise HTTPException(status_code=503, detail="Modèle non chargé")
    if not request.texts:
        raise HTTPException(status_code=400, detail="Liste de textes vide")

    embeddings = _model.encode(
        request.texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    ).tolist()

    return EmbedResponse(
        embeddings=embeddings,
        model=EMBEDDING_MODEL,
        dim=EMBEDDING_DIM,
    )
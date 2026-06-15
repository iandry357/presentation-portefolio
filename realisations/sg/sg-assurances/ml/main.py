"""
ML Service SG Assurances — FastAPI port 8003
Orchestre YOLO, NER (local OVH) et Qwen (Vertex AI Endpoint)

Routes :
    GET  /health
    POST /predict/yolo
    POST /predict/ner
    POST /predict/qwen/base
    POST /predict/qwen/finetuned
    POST /predict/qwen/dual
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

import ner_inference
import yolo_inference
import qwen_base_client
import qwen_finetuned_client
import qwen_dual_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# Config chemins
# ─────────────────────────────────────────
YOLO_MODEL_PATH = Path(os.getenv("YOLO_MODEL_PATH", "/app/models/yolo_sg_assurances.pt"))
NER_MODEL_PATH  = Path(os.getenv("NER_MODEL_PATH",  "/app/models/ner_sg_assurances"))

# ─────────────────────────────────────────
# Lifespan — chargement modèles au démarrage
# ─────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[ml-service] Démarrage ML Service SG Assurances")

    logger.info("[ml-service] Chargement YOLO...")
    yolo_inference.init(YOLO_MODEL_PATH)

    logger.info("[ml-service] Chargement NER...")
    ner_inference.init(NER_MODEL_PATH)

    logger.info("[ml-service] ML Service prêt — port 8003")
    yield
    logger.info("[ml-service] Arrêt")

app = FastAPI(title="ML Service SG Assurances", version="1.0.0", lifespan=lifespan)

# ─────────────────────────────────────────
# Schémas
# ─────────────────────────────────────────
class NERRequest(BaseModel):
    text: str

class QwenRequest(BaseModel):
    prompt: str
    max_new_tokens: int = 200

# ─────────────────────────────────────────
# Routes
# ─────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status":  "ok",
        "service": "sg-assurances-ml",
        "models": {
            "yolo": "loaded",
            "ner":  "loaded",
            "qwen": "vertex-endpoint",
        },
    }


@app.post("/predict/yolo")
async def predict_yolo(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        result = yolo_inference.predict(image_bytes)
        return result
    except Exception as e:
        logger.error(f"[ml-service] Erreur YOLO : {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/ner")
def predict_ner(request: NERRequest):
    try:
        result = ner_inference.predict(request.text)
        return result
    except Exception as e:
        logger.error(f"[ml-service] Erreur NER : {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/qwen/base")
def predict_qwen_base(request: QwenRequest):
    try:
        result = qwen_base_client.predict(
            prompt=request.prompt,
            max_new_tokens=request.max_new_tokens,
        )
        return result
    except Exception as e:
        logger.warning(f"[ml-service] Qwen base non disponible : {e}")
        return {"generated_text": "Vertex Endpoint non disponible", "model_type": "base"}


@app.post("/predict/qwen/finetuned")
def predict_qwen_finetuned(request: QwenRequest):
    try:
        result = qwen_finetuned_client.predict(
            prompt=request.prompt,
            max_new_tokens=request.max_new_tokens,
        )
        return result
    except Exception as e:
        logger.warning(f"[ml-service] Qwen finetuned non disponible : {e}")
        return {"generated_text": "Vertex Endpoint non disponible", "model_type": "finetuned"}


@app.post("/predict/qwen/dual")
def predict_qwen_dual(request: QwenRequest):
    try:
        result = qwen_dual_client.predict(
            prompt=request.prompt,
            max_new_tokens=request.max_new_tokens,
        )
        return result
    except Exception as e:
        logger.warning(f"[ml-service] Qwen dual non disponible : {e}")
        return {
            "base":      {"generated_text": "Vertex Endpoint non disponible", "model_type": "base"},
            "finetuned": {"generated_text": "Vertex Endpoint non disponible", "model_type": "finetuned"},
        }
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
import json

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

import ner_inference
import yolo_inference
import qwen_base_client
import qwen_finetuned_client
import qwen_dual_client

import subprocess
from google.oauth2 import service_account

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# Config chemins
# ─────────────────────────────────────────
YOLO_MODEL_PATH = Path(os.getenv("YOLO_MODEL_PATH", "/app/models/yolo_sg_assurances.pt"))
NER_MODEL_PATH  = Path(os.getenv("NER_MODEL_PATH",  "/app/models/ner_sg_assurances"))

GCS_YOLO_URI = os.getenv("GCS_YOLO_URI", "gs://sg-assurances-models/sg-assurances/yolo/yolo_sg_assurances.pt")
GCS_NER_URI  = os.getenv("GCS_NER_URI",  "gs://sg-assurances-models/sg-assurances/ner/ner_sg_assurances")

GCS_ENDPOINT_INFO = os.getenv("GCS_ENDPOINT_INFO", "gs://sg-assurances-models/sg-assurances/qwen-endpoint/qwen_endpoint_id.json")
ENDPOINT_INFO_PATH = Path(os.getenv("ENDPOINT_INFO_PATH", "/app/models/qwen_endpoint_id.json"))

def _download_if_missing(gcs_uri: str, local_path: Path) -> None:
    """Télécharge depuis GCS si le fichier/répertoire est absent."""
    if local_path.exists() and (local_path.is_file() or any(local_path.iterdir())):
        logger.info(f"[ml-service] Déjà en cache : {local_path}")
        return

    is_file = gcs_uri.endswith(".pt") or gcs_uri.endswith(".json")

    if is_file:
        local_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        local_path.mkdir(parents=True, exist_ok=True)

    sa_key = os.getenv("SA_KEY_PATH", "/app/gcp_sa_sg.json")

    auth_cmd = ["gcloud", "auth", "activate-service-account", f"--key-file={sa_key}"]
    subprocess.run(auth_cmd, capture_output=True, text=True)

    logger.info(f"[ml-service] Téléchargement {gcs_uri} → {local_path}")

    if is_file:
        cmd = ["gsutil", "cp", gcs_uri, str(local_path)]
    else:
        cmd = ["gsutil", "-m", "rsync", "-r", gcs_uri, str(local_path)]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"[ml-service] Erreur gsutil : {result.stderr}")
    logger.info(f"[ml-service] Téléchargement terminé → {local_path}")

# ─────────────────────────────────────────
# Lifespan — chargement modèles au démarrage
# ─────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[ml-service] Démarrage ML Service SG Assurances")

    logger.info("[ml-service] Vérification modèles GCS...")
    _download_if_missing(GCS_YOLO_URI, YOLO_MODEL_PATH)
    _download_if_missing(GCS_NER_URI,  Path(str(NER_MODEL_PATH)))

    logger.info("[ml-service] Chargement YOLO...")
    yolo_inference.init(YOLO_MODEL_PATH)

    logger.info("[ml-service] Chargement NER...")
    ner_inference.init(NER_MODEL_PATH)

    logger.info("[ml-service] Téléchargement endpoint info...")
    _download_if_missing(GCS_ENDPOINT_INFO, ENDPOINT_INFO_PATH)

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
    
@app.get("/predict/topic-modeling")
def predict_topic_modeling():
    results_path = Path("/app/results/topic_modeling.json")
    if not results_path.exists():
        raise HTTPException(status_code=404, detail="Topic modeling non encore calculé — lancez le script manuellement")
    try:
        with open(results_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[ml-service] Erreur lecture topic modeling : {e}")
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
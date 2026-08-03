"""
ML Service Banque de France — FastAPI port 8007
Sert les resultats pre-calcules (topic modeling pour l'instant).
Les routes EBA/NER/Webstat seront ajoutees ici quand ces modules seront prets.

Routes :
    GET /health
    GET /predict/topic-modeling
"""

import json
import logging
import os
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import eba_service
import classification_inference

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RESULTS_DIR = Path("/app/results")

CLASSIFICATION_MODEL_DIR = Path(os.getenv("CLASSIFICATION_MODEL_DIR", "/app/models/classification"))
GCS_CLASSIFICATION_URI = os.getenv(
    "GCS_CLASSIFICATION_URI",
    "gs://banque-de-france-models/banque-de-france/classification",
)


def _download_if_missing(gcs_uri: str, local_path: Path) -> None:
    """Telecharge depuis GCS si le repertoire est absent — meme logique que
    le ML Service SG Assurances (yolo/ner)."""
    if local_path.exists() and any(local_path.iterdir()):
        logger.info(f"[banque-ml] Deja en cache : {local_path}")
        return

    local_path.mkdir(parents=True, exist_ok=True)

    sa_key = os.getenv("SA_KEY_PATH", "/app/gcp_sa_banque.json")
    auth_cmd = ["gcloud", "auth", "activate-service-account", f"--key-file={sa_key}"]
    subprocess.run(auth_cmd, capture_output=True, text=True)

    logger.info(f"[banque-ml] Telechargement {gcs_uri} -> {local_path}")
    cmd = ["gsutil", "-m", "rsync", "-r", gcs_uri, str(local_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"[banque-ml] Erreur gsutil : {result.stderr}")
    logger.info(f"[banque-ml] Telechargement termine -> {local_path}")


class ClassificationRequest(BaseModel):
    text: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[banque-ml] Demarrage ML Service Banque de France")

    logger.info("[banque-ml] Verification modele classification GCS...")
    _download_if_missing(GCS_CLASSIFICATION_URI, CLASSIFICATION_MODEL_DIR)

    logger.info("[banque-ml] Chargement classification...")
    classification_inference.init(CLASSIFICATION_MODEL_DIR)

    logger.info("[banque-ml] ML Service pret — port 8007")
    yield
    logger.info("[banque-ml] Arret")


app = FastAPI(title="ML Service Banque de France", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status":  "ok",
        "service": "banque-de-france-ml",
    }


@app.get("/predict/topic-modeling")
def predict_topic_modeling():
    results_path = RESULTS_DIR / "topic_modeling.json"
    if not results_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Topic modeling non encore calcule — lancez topic_modeling.py manuellement",
        )
    try:
        with open(results_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[banque-ml] Erreur lecture topic modeling : {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/predict/eba")
def predict_eba():
    try:
        return eba_service.get_eba_scores()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"[banque-ml] Erreur lecture EBA : {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/classification")
def predict_classification(request: ClassificationRequest):
    try:
        return classification_inference.predict(request.text)
    except Exception as e:
        logger.error(f"[banque-ml] Erreur classification : {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/predict/classification/examples")
def get_classification_examples():
    try:
        return {"examples": classification_inference.get_demo_examples()}
    except Exception as e:
        logger.error(f"[banque-ml] Erreur lecture exemples demo : {e}")
        raise HTTPException(status_code=500, detail=str(e))
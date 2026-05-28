import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

RESULTS_DIR = Path(__file__).parent / "results"
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "*")

cache: dict = {}


def load_json(name: str) -> dict:
    path = RESULTS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"{name}.json not found in results/")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Chargement topic modeling au démarrage
    try:
        cache["topic_modeling"] = load_json("topic_modeling")
        print("✅ topic_modeling.json chargé en cache")
    except FileNotFoundError as e:
        print(f"⚠️  Warning: {e}")

    # Chargement lazy du modèle ViT — import différé pour éviter cold start
    try:
        from vit_inference import load_model
        cache["vit_model"] = load_model()
        print("✅ Modèle ViT chargé en cache")
    except Exception as e:
        print(f"⚠️  ViT model non disponible: {e}")

    yield
    cache.clear()


app = FastAPI(title="Savencia ML Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "cached": list(cache.keys()),
    }


@app.get("/ml/topic-modeling")
def get_topic_modeling():
    if "topic_modeling" not in cache:
        raise HTTPException(status_code=503, detail="topic_modeling.json non disponible — lancer topic_modeling.py")
    return cache["topic_modeling"]


@app.post("/ml/vit-inference")
async def vit_inference(file: UploadFile = File(...)):
    if "vit_model" not in cache:
        raise HTTPException(status_code=503, detail="Modèle ViT non disponible")

    # Validation type fichier
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Le fichier doit être une image")

    try:
        from vit_inference import predict
        image_bytes = await file.read()
        result = predict(cache["vit_model"], image_bytes)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur inférence ViT: {str(e)}")
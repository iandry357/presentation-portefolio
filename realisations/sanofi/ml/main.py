import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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
    try:
        cache["clustering"] = load_json("clustering")
        cache["forecasting"] = load_json("forecasting")
        print("✅ ML results loaded into cache")
    except FileNotFoundError as e:
        print(f"⚠️  Warning: {e}")
    yield
    cache.clear()


app = FastAPI(title="Sanofi ML Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "cached": list(cache.keys())}


@app.get("/ml/clustering")
def get_clustering():
    if "clustering" not in cache:
        raise HTTPException(status_code=503, detail="clustering.json not available")
    return cache["clustering"]


@app.get("/ml/forecasting")
def get_forecasting():
    if "forecasting" not in cache:
        raise HTTPException(status_code=503, detail="forecasting.json not available")
    return cache["forecasting"]
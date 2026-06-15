"""
Serving FastAPI — Qwen2.5-1.5B base et fine-tuné
Custom container pour Vertex AI Endpoint

Variables d'environnement :
    MODEL_TYPE         : "base" | "finetuned"
    GCS_BASE_MODEL_URI : gs://... chemin poids base model
    GCS_FINETUNED_URI  : gs://... chemin adapters LoRA
    LOCAL_BASE_CACHE   : répertoire local cache base model
    LOCAL_FINETUNED_CACHE : répertoire local cache adapters

Endpoints :
    GET  /health   → health check Vertex AI
    POST /predict  → inférence Qwen
"""

import logging
import os
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# Config depuis variables d'environnement
# ─────────────────────────────────────────
MODEL_TYPE            = os.getenv("MODEL_TYPE", "base")
GCS_BASE_MODEL_URI    = os.getenv("GCS_BASE_MODEL_URI", "gs://sg-assurances-models/sg-assurances/qwen-base")
GCS_FINETUNED_URI     = os.getenv("GCS_FINETUNED_URI",  "gs://sg-assurances-models/sg-assurances/qlora/qlora_sg_assurances")
LOCAL_BASE_CACHE      = os.getenv("LOCAL_BASE_CACHE",    "/app/models/qwen-base")
LOCAL_FINETUNED_CACHE = os.getenv("LOCAL_FINETUNED_CACHE", "/app/models/qlora")

DEFAULT_MAX_TOKENS = 100
MAX_TOKENS_CAP     = 512

# ─────────────────────────────────────────
# State global
# ─────────────────────────────────────────
model     = None
tokenizer = None
device    = None

# ─────────────────────────────────────────
# Helpers GCS
# ─────────────────────────────────────────
def _download_gcs(gcs_uri: str, local_dir: str) -> None:
    Path(local_dir).mkdir(parents=True, exist_ok=True)
    # cmd = ["gsutil", "-m", "cp", "-r", f"{gcs_uri}/*", local_dir]
    cmd = ["gsutil", "-m", "rsync", "-r", gcs_uri, local_dir]
    logger.info(f"[serving] Téléchargement {gcs_uri} → {local_dir}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"[serving] Erreur gsutil : {result.stderr}")
    logger.info(f"[serving] Téléchargement terminé → {local_dir}")

# ─────────────────────────────────────────
# Chargement modèle
# ─────────────────────────────────────────
def _load_model() -> None:
    global model, tokenizer, device

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"[serving] Device : {device}")

    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

    # Téléchargement base model si absent
    base_path = Path(LOCAL_BASE_CACHE)
    if not base_path.exists() or not any(base_path.iterdir()):
        _download_gcs(GCS_BASE_MODEL_URI, LOCAL_BASE_CACHE)

    # Chargement tokenizer
    tokenizer = AutoTokenizer.from_pretrained(LOCAL_BASE_CACHE, trust_remote_code=True)
    logger.info(f"[serving] Tokenizer chargé")

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
    )

    if MODEL_TYPE == "finetuned":
        from peft import PeftModel

        # Téléchargement adapters si absent
        ft_path = Path(LOCAL_FINETUNED_CACHE)
        if not ft_path.exists() or not any(ft_path.iterdir()):
            _download_gcs(GCS_FINETUNED_URI, LOCAL_FINETUNED_CACHE)

        logger.info(f"[serving] Chargement base model + adapters LoRA...")
        base = AutoModelForCausalLM.from_pretrained(
            LOCAL_BASE_CACHE,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
        )
        model = PeftModel.from_pretrained(base, LOCAL_FINETUNED_CACHE)

    else:
        logger.info(f"[serving] Chargement base model...")
        model = AutoModelForCausalLM.from_pretrained(
            LOCAL_BASE_CACHE,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
        )

    model.eval()
    logger.info(f"[serving] Modèle prêt — model_type={MODEL_TYPE}")

# ─────────────────────────────────────────
# Lifespan — chargement au démarrage
# ─────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"[serving] Démarrage — MODEL_TYPE={MODEL_TYPE}")
    _load_model()
    yield
    logger.info(f"[serving] Arrêt")

app = FastAPI(title="Qwen Serving", lifespan=lifespan)

# ─────────────────────────────────────────
# Schémas
# ─────────────────────────────────────────
class Instance(BaseModel):
    prompt: str
    max_new_tokens: int = DEFAULT_MAX_TOKENS

class PredictRequest(BaseModel):
    instances: list[Instance]

class Prediction(BaseModel):
    generated_text: str
    model_type: str

class PredictResponse(BaseModel):
    predictions: list[Prediction]

# ─────────────────────────────────────────
# Routes
# ─────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "model_type": MODEL_TYPE}

@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Modèle non chargé")

    predictions = []
    for instance in request.instances:
        prompt         = instance.prompt
        max_new_tokens = min(instance.max_new_tokens, MAX_TOKENS_CAP)

        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = tokenizer(text, return_tensors="pt").to(device)

        with torch.no_grad():
            generated = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=0.7,
                top_p=0.8,
                top_k=20,
                pad_token_id=tokenizer.eos_token_id,
            )

        input_len  = inputs["input_ids"].shape[1]
        new_tokens = generated[0][input_len:]
        response   = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

        predictions.append(Prediction(
            generated_text=response,
            model_type=MODEL_TYPE,
        ))

    return PredictResponse(predictions=predictions)
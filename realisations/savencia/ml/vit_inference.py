"""
Inférence ViT — Détection maturité fromagère CR-IDB.
Charge le modèle depuis GCP Cloud Storage, préprocesse l'image,
infère la classe et génère la heatmap Grad-CAM.
"""
import base64
import io
import json
import logging
import os
from pathlib import Path

import numpy as np
import torch
import torchvision.transforms as T
from google.cloud import storage
from google.oauth2 import service_account
from PIL import Image
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.image import show_cam_on_image
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
from transformers import ViTForImageClassification

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# Config
# ─────────────────────────────────────────
GCS_BUCKET = "savencia-models"
GCS_MODEL_PATH = "vit/model_latest.pt"
GCS_REGISTRY_PATH = "vit/model_registry.json"
LOCAL_MODEL_PATH = Path(__file__).parent / "models" / "model_latest.pt"
GCP_SA_PATH = os.getenv("GCP_SA_SAVENCIA_PATH", "/app/gcp_sa_savencia.json")

# 6 classes CR-IDB : 3 types x 2 états
CLASS_NAMES = [
    "Extra-Hard_Not-Target",
    "Extra-Hard_Target",
    "Hard_Not-Target",
    "Hard_Target",
    "Semi-Hard_Not-Target",
    "Semi-Hard_Target",
]

IMAGE_SIZE = 224

TRANSFORM = T.Compose([
    T.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    T.ToTensor(),
    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


# ─────────────────────────────────────────
# GCS
# ─────────────────────────────────────────
def _get_gcs_client() -> storage.Client:
    creds = service_account.Credentials.from_service_account_file(GCP_SA_PATH)
    return storage.Client(credentials=creds)


def _download_model() -> Path:
    """Télécharge le modèle depuis GCS si absent en local."""
    LOCAL_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOCAL_MODEL_PATH.exists():
        logger.info(f"✅ Modèle trouvé en local : {LOCAL_MODEL_PATH}")
        return LOCAL_MODEL_PATH

    logger.info(f"⬇️  Téléchargement modèle depuis GCS : {GCS_BUCKET}/{GCS_MODEL_PATH}")
    client = _get_gcs_client()
    bucket = client.bucket(GCS_BUCKET)
    blob = bucket.blob(GCS_MODEL_PATH)
    blob.download_to_filename(str(LOCAL_MODEL_PATH))
    logger.info("✅ Modèle téléchargé")
    return LOCAL_MODEL_PATH


# ─────────────────────────────────────────
# Chargement modèle
# ─────────────────────────────────────────
def load_model() -> dict:
    """
    Charge le modèle ViT fine-tuné depuis GCS.
    Retourne un dict avec modèle + métadonnées registry.
    """
    model_path = _download_model()

    model = ViTForImageClassification.from_pretrained(
        "google/vit-base-patch16-224",
        num_labels=len(CLASS_NAMES),
        ignore_mismatched_sizes=True,
    )
    state_dict = torch.load(model_path, map_location="cpu")
    model.load_state_dict(state_dict)
    model.eval()

    # Lecture registry
    registry = {}
    try:
        client = _get_gcs_client()
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(GCS_REGISTRY_PATH)
        registry = json.loads(blob.download_as_text())
    except Exception as e:
        logger.warning(f"⚠️  Registry non disponible : {e}")

    logger.info("✅ Modèle ViT prêt pour l'inférence")
    return {"model": model, "registry": registry}


# ─────────────────────────────────────────
# Inférence + Grad-CAM
# ─────────────────────────────────────────
def _generate_gradcam(model: ViTForImageClassification, tensor: torch.Tensor, class_idx: int) -> str:
    """Génère la heatmap Grad-CAM et retourne l'image en base64."""
    # Couche cible pour ViT — dernière couche d'attention
    target_layer = model.vit.encoder.layer[-1].layernorm_before

    cam = GradCAM(model=model, target_layers=[target_layer])
    targets = [ClassifierOutputTarget(class_idx)]
    grayscale_cam = cam(input_tensor=tensor.unsqueeze(0), targets=targets)[0]

    # Image originale normalisée pour overlay
    img_np = tensor.permute(1, 2, 0).numpy()
    img_np = (img_np - img_np.min()) / (img_np.max() - img_np.min())
    img_np = np.float32(img_np)

    visualization = show_cam_on_image(img_np, grayscale_cam, use_rgb=True)
    pil_img = Image.fromarray(visualization)

    buffer = io.BytesIO()
    pil_img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def predict(model_cache: dict, image_bytes: bytes) -> dict:
    """
    Prédit la classe d'une image fromagère et génère la heatmap Grad-CAM.

    Args:
        model_cache: dict retourné par load_model()
        image_bytes: bytes de l'image uploadée

    Returns:
        dict avec cheese_type, ripeness, confidence, heatmap_base64
    """
    model = model_cache["model"]
    registry = model_cache.get("registry", {})

    # Préprocessing
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = TRANSFORM(image)

    # Inférence
    with torch.no_grad():
        outputs = model(pixel_values=tensor.unsqueeze(0))
        logits = outputs.logits
        probs = torch.softmax(logits, dim=-1)[0]
        class_idx = int(torch.argmax(probs))
        confidence = float(probs[class_idx])

    class_name = CLASS_NAMES[class_idx]
    cheese_type, ripeness = class_name.split("_", 1)

    # Grad-CAM
    heatmap_base64 = _generate_gradcam(model, tensor, class_idx)

    return {
        "cheese_type": cheese_type,
        "ripeness": ripeness.replace("-", " "),
        "confidence": round(confidence, 3),
        "class_name": class_name,
        "all_probabilities": {
            CLASS_NAMES[i]: round(float(probs[i]), 3)
            for i in range(len(CLASS_NAMES))
        },
        "heatmap_base64": heatmap_base64,
        "model_version": registry.get("version", "unknown"),
    }
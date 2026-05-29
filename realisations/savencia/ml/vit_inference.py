"""
vit_inference.py
────────────────
Inférence ViT — Détection maturité fromagère CR-IDB.
Charge le modèle depuis GCS au démarrage, préprocesse l'image,
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
import torch.nn as nn
import torchvision.transforms as T
from google.cloud import storage
from google.oauth2 import service_account
from PIL import Image
# from pytorch_grad_cam import GradCAM
from pytorch_grad_cam import GradCAMPlusPlus
from pytorch_grad_cam.utils.reshape_transforms import vit_reshape_transform
from pytorch_grad_cam.utils.image import show_cam_on_image
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
from transformers import ViTForImageClassification

logger = logging.getLogger(__name__)


# ── Config ─────────────────────────────────────────────────────────────────────

GCS_BUCKET        = "savencia-models"
GCS_MODEL_PATH    = "vit/model_latest.pt"
GCS_REGISTRY_PATH = "vit/model_registry.json"
LOCAL_MODEL_PATH  = Path(__file__).parent / "models" / "model_latest.pt"
GCP_SA_PATH       = os.getenv("GCP_SA_SAVENCIA_PATH", "/app/gcp_sa_savencia.json")

# Aligné avec dataset.py — CHEESE_TYPES x CHEESE_STATES
CLASS_NAMES = [
    "Extra-Hard_Target",
    "Extra-Hard_NotTarget",
    "Hard_Target",
    "Hard_NotTarget",
    "Semi-Hard_Target",
    "Semi-Hard_NotTarget",
]

IMAGE_SIZE = 224

TRANSFORM = T.Compose([
    T.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    T.ToTensor(),
    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


# ── Wrapper Grad-CAM pour ViT HuggingFace ──────────────────────────────────────

class ViTGradCAMWrapper(nn.Module):
    """Expose le dernier bloc d'encodeur au Grad-CAM."""

    def __init__(self, model: ViTForImageClassification) -> None:
        super().__init__()
        self.model = model

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.model(pixel_values=x).logits

    # def get_target_layer(self):
        # return self.model.vit.encoder.layer[-1].layernorm_before
        # return self.model.vit.encoder.layer[-1].layernorm_after
        # return self.model.vit.encoder.layer[-1]
    
    # def get_target_layer(self):
        # return self.model.vit.layers[-1].layernorm_before
    
    def get_target_layer(self):
        return self.model.vit.encoder.layer[-1].layernorm_before


# ── GCS ────────────────────────────────────────────────────────────────────────

def _get_gcs_client() -> storage.Client:
    creds = service_account.Credentials.from_service_account_file(GCP_SA_PATH)
    return storage.Client(credentials=creds)


def _download_model() -> Path:
    """Télécharge le modèle depuis GCS si absent en local."""
    LOCAL_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOCAL_MODEL_PATH.exists():
        logger.info(f"Modèle trouvé en local : {LOCAL_MODEL_PATH}")
        return LOCAL_MODEL_PATH

    logger.info(f"Téléchargement modèle depuis GCS : {GCS_BUCKET}/{GCS_MODEL_PATH}")
    client = _get_gcs_client()
    bucket = client.bucket(GCS_BUCKET)
    blob   = bucket.blob(GCS_MODEL_PATH)
    blob.download_to_filename(str(LOCAL_MODEL_PATH))
    logger.info("Modèle téléchargé depuis GCS")
    return LOCAL_MODEL_PATH


# ── Chargement modèle ──────────────────────────────────────────────────────────

def load_model() -> dict:
    """
    Charge le modèle ViT fine-tuné depuis GCS.
    Retourne un dict avec modèle wrappé + métadonnées registry.
    """
    model_path = _download_model()

    # Checkpoint format : {model_state, epoch, val_acc, config}
    checkpoint = torch.load(model_path, map_location="cpu")

    base_model = ViTForImageClassification.from_pretrained(
        "google/vit-base-patch16-224",
        num_labels=len(CLASS_NAMES),
        ignore_mismatched_sizes=True,
    )
    base_model.load_state_dict(checkpoint["model_state"])
    base_model.eval()

    model = ViTGradCAMWrapper(base_model)

    # Lecture registry GCS
    registry = {}
    try:
        client  = _get_gcs_client()
        bucket  = client.bucket(GCS_BUCKET)
        blob    = bucket.blob(GCS_REGISTRY_PATH)
        registry = json.loads(blob.download_as_text())
    except Exception as e:
        logger.warning(f"Registry GCS non disponible : {e}")

    logger.info(f"Modèle ViT prêt — époque {checkpoint.get('epoch')} | val_acc={checkpoint.get('val_acc', '?'):.3f}")
    return {"model": model, "registry": registry}


# ── Grad-CAM ───────────────────────────────────────────────────────────────────

def _generate_gradcam(
    model:     ViTGradCAMWrapper,
    tensor:    torch.Tensor,
    class_idx: int,
) -> str:
    """Génère la heatmap Grad-CAM et retourne l'image en base64 PNG."""
    target_layer = model.get_target_layer()

    # with GradCAM(model=model, target_layers=[target_layer]) as cam:
    with GradCAMPlusPlus(model=model, target_layers=[target_layer], reshape_transform=vit_reshape_transform) as cam:
        targets      = [ClassifierOutputTarget(class_idx)]
        grayscale    = cam(input_tensor=tensor.unsqueeze(0), targets=targets)[0]

    # Dénormalisation pour overlay visuel
    img_np = tensor.permute(1, 2, 0).numpy()
    img_np = (img_np - img_np.min()) / (img_np.max() - img_np.min())
    img_np = np.float32(img_np)

    visualization = show_cam_on_image(img_np, grayscale, use_rgb=True)

    buffer = io.BytesIO()
    Image.fromarray(visualization).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


# ── Inférence ──────────────────────────────────────────────────────────────────

def predict(model_cache: dict, image_bytes: bytes) -> dict:
    """
    Prédit la classe d'une image fromagère et génère la heatmap Grad-CAM.

    Args:
        model_cache : dict retourné par load_model()
        image_bytes : bytes de l'image uploadée

    Returns:
        dict avec cheese_type, ripeness, confidence, probabilities, heatmap_base64
    """
    model    = model_cache["model"]
    registry = model_cache.get("registry", {})

    # Préprocessing
    image  = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = TRANSFORM(image)

    # Inférence
    with torch.no_grad():
        probs     = torch.softmax(model(tensor.unsqueeze(0)), dim=-1)[0]
        class_idx = int(probs.argmax())
        confidence = float(probs[class_idx])

    class_name  = CLASS_NAMES[class_idx]
    cheese_type, ripeness = class_name.split("_", 1)

    # Grad-CAM
    heatmap_base64 = _generate_gradcam(model, tensor, class_idx)

    return {
        "cheese_type":       cheese_type,
        "ripeness":          ripeness,
        "confidence":        round(confidence, 3),
        "class_name":        class_name,
        "all_probabilities": {CLASS_NAMES[i]: round(float(probs[i]), 3) for i in range(len(CLASS_NAMES))},
        "heatmap_base64":    heatmap_base64,
        "model_version":     registry.get("version", "unknown"),
    }
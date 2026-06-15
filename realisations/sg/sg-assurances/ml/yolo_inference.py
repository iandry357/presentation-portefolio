"""
YOLO Inference — Détection de zones sur documents SG Assurances
Chargement du modèle au démarrage, inférence CPU sur OVH.

Classes détectées :
    contract_block, identity_block, amount_block, signature_block
"""

import io
import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

CLASSES = [
    "contract_block",
    "identity_block",
    "amount_block",
    "signature_block",
]

CONF_THRESHOLD = 0.07
IOU_THRESHOLD  = 0.45

# State global — chargé au démarrage via init()
_model = None


def init(model_path: Path) -> None:
    """Charge le modèle YOLO depuis le chemin fourni."""
    global _model
    from ultralytics import YOLO

    if not model_path.exists():
        raise FileNotFoundError(f"[yolo] Modèle introuvable : {model_path}")

    _model = YOLO(str(model_path))
    logger.info(f"[yolo] Modèle chargé : {model_path}")


def predict(image_bytes: bytes) -> dict:
    """
    Détecte les zones sur une image de document.

    Args:
        image_bytes : image en bytes (JPEG, PNG)

    Returns:
        {"detections": [{"class": str, "score": float, "x1": float, ...}]}
    """
    if _model is None:
        raise RuntimeError("[yolo] Modèle non initialisé — appelle init() d'abord")

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    results = _model.predict(
        source=image,
        conf=CONF_THRESHOLD,
        iou=IOU_THRESHOLD,
        verbose=False,
        device="cpu",
    )

    detections = []
    for result in results:
        if result.boxes is None:
            continue
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            score   = float(box.conf[0])
            cls_idx = int(box.cls[0])
            cls_name = (
                CLASSES[cls_idx] if cls_idx < len(CLASSES) else f"class_{cls_idx}"
            )
            detections.append({
                "class": cls_name,
                "score": round(score, 4),
                "x1":    round(x1, 2),
                "y1":    round(y1, 2),
                "x2":    round(x2, 2),
                "y2":    round(y2, 2),
            })

    return {"detections": detections}
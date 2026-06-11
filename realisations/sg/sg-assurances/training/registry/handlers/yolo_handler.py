 
"""
YOLO Handler — TorchServe handler pour Vertex AI Model Registry
Permet le packaging en model.mar via torch-model-archiver.

Note : le serving réel est assuré par OVH (FastAPI port 8003).
Ce handler est requis uniquement pour satisfaire le format Vertex AI.

Input  : image base64 encodée en JSON {"instances": [{"image": "<base64>"}]}
Output : détections JSON {"predictions": [{"boxes": [...], "scores": [...], "classes": [...]}]}
"""

import base64
import io
import json
import logging
import os
from pathlib import Path

import torch
from ts.torch_handler.base_handler import BaseHandler

logger = logging.getLogger(__name__)


class YOLOHandler(BaseHandler):
    """
    Handler TorchServe pour modèle YOLO SG Assurances.
    Gère le chargement du modèle et l'inférence sur images de documents.
    """

    # Classes YOLO SG Assurances
    CLASSES = [
        "contract_block",
        "identity_block",
        "amount_block",
        "signature_block",
    ]

    def __init__(self):
        super().__init__()
        self.model = None
        self.initialized = False
        self.device = None

    def initialize(self, context) -> None:
        """
        Chargement du modèle YOLO depuis les artefacts TorchServe.
        Appelé une seule fois au démarrage du serveur.
        """
        self.manifest = context.manifest
        properties = context.system_properties
        model_dir = properties.get("model_dir")

        # Device — GPU si disponible
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        logger.info(f"[YOLOHandler] Device : {self.device}")

        # Chargement poids YOLO
        model_file = os.path.join(model_dir, "yolo_sg_assurances.pt")
        if not os.path.exists(model_file):
            raise FileNotFoundError(f"Modèle introuvable : {model_file}")

        try:
            from ultralytics import YOLO
            self.model = YOLO(model_file)
            logger.info(f"[YOLOHandler] Modèle chargé : {model_file}")
        except Exception as e:
            raise RuntimeError(f"Erreur chargement modèle : {e}")

        self.initialized = True
        logger.info("[YOLOHandler] Handler initialisé")

    def preprocess(self, data: list) -> list:
        """
        Décode les images base64 en objets PIL.
        Entrée : [{"body": {"instances": [{"image": "<base64>"}]}}]
        """
        from PIL import Image

        images = []
        for item in data:
            body = item.get("body", item)
            if isinstance(body, (bytes, bytearray)):
                body = json.loads(body)

            instances = body.get("instances", [])
            for instance in instances:
                img_b64 = instance.get("image", "")
                img_bytes = base64.b64decode(img_b64)
                img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                images.append(img)

        return images

    def inference(self, images: list) -> list:
        """
        Inférence YOLO sur liste d'images PIL.
        Retourne les résultats Ultralytics bruts.
        """
        if not images:
            return []

        results = self.model.predict(
            source=images,
            conf=0.25,
            iou=0.45,
            verbose=False,
            device=self.device,
        )
        return results

    def postprocess(self, results: list) -> list:
        """
        Transforme les résultats Ultralytics en JSON sérialisable.
        Format : {"predictions": [{"boxes": [...], "scores": [...], "classes": [...]}]}
        """
        predictions = []

        for result in results:
            boxes_data = []
            if result.boxes is not None:
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    score = float(box.conf[0])
                    cls_idx = int(box.cls[0])
                    cls_name = (
                        self.CLASSES[cls_idx]
                        if cls_idx < len(self.CLASSES)
                        else f"class_{cls_idx}"
                    )
                    boxes_data.append({
                        "x1":        round(x1, 2),
                        "y1":        round(y1, 2),
                        "x2":        round(x2, 2),
                        "y2":        round(y2, 2),
                        "score":     round(score, 4),
                        "class_idx": cls_idx,
                        "class":     cls_name,
                    })

            predictions.append({"detections": boxes_data})

        return [{"predictions": predictions}]
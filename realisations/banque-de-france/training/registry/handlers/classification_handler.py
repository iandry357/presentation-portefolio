"""
handlers/classification_handler.py — MVP Banque de France

Handler spécifique au modèle de classification multi-label des griefs ACPR,
appelé par registry/register_model.py --model classification.

Expose le contrat attendu par register_model.py :
    get_artifact_dir() -> Path
    get_display_name() -> str
    get_description() -> str
    get_labels() -> dict
    get_serving_container_uri() -> str
"""

import json
import re
from pathlib import Path

TRAINING_DIR = Path(__file__).resolve().parent.parent.parent  # training/
FINAL_MODEL_DIR = TRAINING_DIR / "models" / "classification" / "final"
EVALUATION_SUMMARY = TRAINING_DIR / "models" / "classification" / "evaluation_summary.json"
CATEGORIES_FILE = FINAL_MODEL_DIR / "categories.json"

DISPLAY_NAME = "banque-de-france-classification-griefs"

# Conteneur pré-construit générique — requis par l'API, jamais déployé
# (registre MLOps uniquement, service réel prévu sur OVH).
# SERVING_CONTAINER_IMAGE_URI = "europe-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.1-0:latest"
SERVING_CONTAINER_IMAGE_URI = "europe-docker.pkg.dev/vertex-ai/prediction/huggingface-cpu.2-3:latest"


def _safe_label_key(text: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", text.lower()).strip("-")[:63]


def _load_categories() -> list:
    with open(CATEGORIES_FILE, encoding="utf-8") as f:
        return json.load(f)


def _load_evaluation_summary() -> dict:
    """Métriques K-Fold, utilisées uniquement à titre informatif dans les
    labels — aucun seuil bloquant l'enregistrement."""
    if not EVALUATION_SUMMARY.exists():
        return {}
    with open(EVALUATION_SUMMARY, encoding="utf-8") as f:
        return json.load(f)


def get_artifact_dir() -> Path:
    return FINAL_MODEL_DIR


def get_display_name() -> str:
    return DISPLAY_NAME


def get_description() -> str:
    categories = _load_categories()
    categories_str = ", ".join(categories)
    return (
        "Classification multi-label des griefs de sanction ACPR "
        "(corps sentence-camembert-base fine-tuné + têtes k-NN one-vs-rest "
        f"par catégorie). Catégories : {categories_str}. "
        "Registre MLOps uniquement — aucun endpoint Vertex AI déployé, "
        "service d'inférence prévu sur OVH."
    )


def get_labels() -> dict:
    categories = _load_categories()
    evaluation_summary = _load_evaluation_summary()

    labels = {
        "sector": "banque-de-france",
        "model-type": "camembert-embeddings-knn",
        "n-categories": str(len(categories)),
        "usage": "registry-only-no-endpoint",
    }
    for category in categories:
        f1_mean = evaluation_summary.get(category, {}).get("f1_mean")
        if f1_mean is not None:
            key = f"f1-{_safe_label_key(category)}"
            labels[key] = str(round(f1_mean, 3)).replace(".", "-")

    return labels


def get_serving_container_uri() -> str:
    return SERVING_CONTAINER_IMAGE_URI
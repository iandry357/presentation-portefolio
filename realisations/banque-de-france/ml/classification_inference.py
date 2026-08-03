"""
classification_inference.py — Banque de France ML Service
Inference du modele de classification multi-label des griefs ACPR
(corps sentence-camembert-base fine-tune + tetes k-NN one-vs-rest par categorie).
Artefacts telecharges depuis GCS au demarrage (cf. main.py lifespan).
"""

import json
import logging
import re
from pathlib import Path

import joblib
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_body: SentenceTransformer = None
_heads: dict = {}
_categories: list = []


def _safe_category_filename(category: str) -> str:
    """Duplique volontairement la meme convention de nommage que
    train_final.py / classification_handler.py — necessaire pour retrouver
    les fichiers head_*.joblib. Point de vigilance deja documente :
    toute modification de cette logique doit etre repercutee partout."""
    return re.sub(r"[^a-z0-9]+", "_", category.lower()).strip("_")


def init(model_dir: Path) -> None:
    """Charge le corps d'embeddings, les categories et les tetes k-NN — a
    appeler une seule fois au demarrage du service (lifespan)."""
    global _body, _heads, _categories

    logger.info(f"[classification] Chargement corps d'embeddings : {model_dir / 'embedding_body'}")
    _body = SentenceTransformer(str(model_dir / "embedding_body"))

    with open(model_dir / "categories.json", encoding="utf-8") as f:
        _categories = json.load(f)

    _heads = {}
    for category in _categories:
        safe_name = _safe_category_filename(category)
        head_path = model_dir / f"head_{safe_name}.joblib"
        if not head_path.exists():
            logger.warning(f"[classification] Tete manquante pour '{category}' : {head_path}")
            continue
        _heads[category] = joblib.load(head_path)

    logger.info(f"[classification] Pret — {len(_categories)} categories, {len(_heads)} tetes chargees")


def predict(text: str) -> dict:
    """Predit les griefs applicables a un texte de decision, categorie par
    categorie, avec le seuil de decision propre a chaque tete (derive du
    desequilibre positif/negatif observe a l'entrainement, pas 0.5 fixe)."""
    if _body is None:
        raise RuntimeError("Modele non charge — init() doit etre appele au demarrage")

    embedding = _body.encode([text])

    predictions = []
    for category in _categories:
        bundle = _heads.get(category)
        if bundle is None:
            continue
        clf = bundle["model"]
        threshold = bundle["threshold"]

        proba = clf.predict_proba(embedding)[0]
        # proba[1] = probabilite de la classe positive (grief present)
        score = float(proba[1]) if len(proba) > 1 else float(proba[0])

        predictions.append({
            "category": category,
            "score": round(score, 4),
            "threshold": round(threshold, 4),
            "predicted": score >= threshold,
        })

    return {"predictions": predictions}
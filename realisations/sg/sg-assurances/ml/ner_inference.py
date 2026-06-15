"""
NER Inference — Extraction d'entités nommées sur documents SG Assurances
Chargement du modèle CamemBERT au démarrage, inférence CPU sur OVH.

Entités détectées :
    PER (personne), ORG (organisation), LOC (lieu),
    AMOUNT (montant), DATE (date), CONTRACT (contrat)
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# State global — chargé au démarrage via init()
_pipeline = None


def init(model_path: Path) -> None:
    """Charge le pipeline NER CamemBERT depuis le chemin fourni."""
    global _pipeline
    from transformers import pipeline

    if not model_path.exists():
        raise FileNotFoundError(f"[ner] Modèle introuvable : {model_path}")

    _pipeline = pipeline(
        task="ner",
        model=str(model_path),
        tokenizer=str(model_path),
        aggregation_strategy="simple",
        device=-1,  # CPU
    )
    logger.info(f"[ner] Modèle chargé : {model_path}")


def predict(text: str) -> dict:
    """
    Extrait les entités nommées d'un texte de document SG Assurances.

    Args:
        text : texte brut extrait du document

    Returns:
        {"entities": [{"text": str, "label": str, "score": float, "start": int, "end": int}]}
    """
    if _pipeline is None:
        raise RuntimeError("[ner] Modèle non initialisé — appelle init() d'abord")

    if not text or not text.strip():
        return {"entities": []}

    raw = _pipeline(text)

    entities = []
    for ent in raw:
        entities.append({
            "text":  ent.get("word", ""),
            "label": ent.get("entity_group", ent.get("entity", "")),
            "score": round(float(ent.get("score", 0)), 4),
            "start": ent.get("start", 0),
            "end":   ent.get("end", 0),
        })

    return {"entities": entities}
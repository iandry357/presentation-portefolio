"""
eba_service.py — Banque de France ML Service
Sert le score composite EBA pre-calcule (JSON transporte via scp depuis
training/eba/data/processed/eba_scores.json — cf. compute_score.py).
Aucun calcul ici, aucun modele charge : simple lecture de fichier,
meme logique que topic_modeling pour /predict/topic-modeling.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

RESULTS_PATH = Path(__file__).resolve().parent / "results" / "eba_scores.json"


def get_eba_scores() -> dict:
    if not RESULTS_PATH.exists():
        raise FileNotFoundError(
            f"{RESULTS_PATH} introuvable — transferer eba_scores.json via scp "
            "depuis training/eba/data/processed/"
        )
    with open(RESULTS_PATH, encoding="utf-8") as f:
        return json.load(f)
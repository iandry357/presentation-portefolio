"""
train_final.py — MVP Banque de France / classification multi-label

Réentraîne un modèle final sur l'intégralité du pool (toutes les décisions
éligibles, sans split K-Fold), destiné au déploiement — le K-Fold
(train_classification.py + evaluate.py) a servi à ESTIMER la performance
attendue, ce script produit l'artefact réellement déployé, en s'appuyant sur
la totalité des données disponibles plutôt que ~80% d'entre elles.

Reprend strictement la même logique que train_classification.py (pairing
Jaccard, fine-tuning du corps, têtes k-NN par catégorie), appliquée cette
fois à data/train/full_pool.csv plutôt qu'à un fold.

Entrée :
  - training/classification/data/train/full_pool.csv

Sortie :
  - training/models/classification/final/
      embedding_body/
      head_<categorie>.joblib
      categories.json

Usage :
  python train_final.py
"""

import json
import logging
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sentence_transformers import InputExample, SentenceTransformer, losses
from sklearn.neighbors import KNeighborsClassifier
from torch.utils.data import DataLoader

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("train_final")

# --------------------------------------------------------------------------
# Configuration (identique à train_classification.py)
# --------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DATA_TRAIN_DIR = BASE_DIR / "data" / "train"
FINAL_MODEL_DIR = BASE_DIR.parents[0] / "models" / "classification" / "final"

EMBEDDING_MODEL_NAME = "dangvantuan/sentence-camembert-base"

NUM_EPOCHS = 3
BATCH_SIZE = 16
WARMUP_STEPS = 10


# --------------------------------------------------------------------------
# Chargement du pool complet
# --------------------------------------------------------------------------

def load_full_pool():
    """Charge full_pool.csv et déduit les catégories des colonnes présentes
    (toutes sauf decision_number/text/Autre — Autre n'a pas de tête dédiée,
    même logique que pour les folds)."""
    pool_df = pd.read_csv(DATA_TRAIN_DIR / "full_pool.csv")
    categories = [c for c in pool_df.columns if c not in ("decision_number", "text", "Autre")]
    logger.info("Pool complet : %d décisions, %d catégories : %s",
                len(pool_df), len(categories), categories)
    return pool_df, categories


# --------------------------------------------------------------------------
# Génération des paires multi-label (Jaccard) — identique à train_classification.py
# --------------------------------------------------------------------------

def generate_multilabel_pairs(texts: list, label_matrix: np.ndarray) -> list:
    n = len(texts)
    examples = []

    for i in range(n):
        set_i = set(np.where(label_matrix[i])[0])
        for j in range(i + 1, n):
            set_j = set(np.where(label_matrix[j])[0])
            union = set_i | set_j
            jaccard = len(set_i & set_j) / len(union) if union else 0.0
            examples.append(InputExample(texts=[texts[i], texts[j]], label=float(jaccard)))

    similarities = [e.label for e in examples]
    logger.info(
        "Paires générées : %d (similarité Jaccard moyenne=%.3f, min=%.3f, max=%.3f)",
        len(examples), np.mean(similarities), np.min(similarities), np.max(similarities),
    )
    return examples


# --------------------------------------------------------------------------
# Fine-tuning du corps d'embeddings — identique à train_classification.py
# --------------------------------------------------------------------------

def finetune_embedding_body(train_examples: list) -> SentenceTransformer:
    body = SentenceTransformer(EMBEDDING_MODEL_NAME)

    train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=BATCH_SIZE)
    train_loss = losses.CosineSimilarityLoss(body)

    body.fit(
        train_objectives=[(train_dataloader, train_loss)],
        epochs=NUM_EPOCHS,
        warmup_steps=WARMUP_STEPS,
        show_progress_bar=True,
    )

    return body


def encode_texts(body: SentenceTransformer, texts: list) -> np.ndarray:
    return body.encode(texts, show_progress_bar=True)


# --------------------------------------------------------------------------
# Entraînement des têtes k-NN — identique à train_classification.py
# --------------------------------------------------------------------------

def train_category_heads(X: np.ndarray, pool_df: pd.DataFrame, categories: list) -> dict:
    """Entraîne un k-NN indépendant par catégorie, k adapté au nombre
    d'exemples positifs, seuil de décision dérivé du déséquilibre."""
    heads = {}
    for category in categories:
        y = pool_df[category].to_numpy()

        n_pos = int(y.sum())
        n_neg = len(y) - n_pos
        k = max(1, min(5, n_pos))
        threshold = n_pos / (n_pos + n_neg)

        clf = KNeighborsClassifier(n_neighbors=k, weights="distance")
        clf.fit(X, y)

        heads[category] = {"model": clf, "threshold": threshold}

        logger.info(
            "Tête entraînée : '%s' (k=%d, threshold=%.4f, n_pos=%d, n_neg=%d)",
            category, k, threshold, n_pos, n_neg,
        )

    return heads


# --------------------------------------------------------------------------
# Sauvegarde
# --------------------------------------------------------------------------

def safe_category_filename(category: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", category.lower()).strip("_")


def save_final_artifacts(body: SentenceTransformer, heads: dict, categories: list):
    FINAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)

    body.save(str(FINAL_MODEL_DIR / "embedding_body"))

    for category, bundle in heads.items():
        safe_name = safe_category_filename(category)
        joblib.dump(bundle, FINAL_MODEL_DIR / f"head_{safe_name}.joblib")

    with open(FINAL_MODEL_DIR / "categories.json", "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)

    logger.info("Modèle final sauvegardé : %s", FINAL_MODEL_DIR)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    pool_df, categories = load_full_pool()

    label_matrix = pool_df[categories].to_numpy()
    texts = pool_df["text"].tolist()

    train_examples = generate_multilabel_pairs(texts, label_matrix)
    body = finetune_embedding_body(train_examples)

    X = encode_texts(body, texts)
    heads = train_category_heads(X, pool_df, categories)

    save_final_artifacts(body, heads, categories)

    logger.info("Terminé.")


if __name__ == "__main__":
    main()
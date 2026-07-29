"""
train_classification.py — MVP Banque de France / classification multi-label

Entraîne, pour chaque fold produit par dataset.py, un modèle de classification
multi-label des griefs de sanction ACPR :
  - Étage 1 : fine-tuning contrastif du corps d'embeddings SetFit
    (paraphrase-multilingual-mpnet-base-v2), avec pairing multi-label natif
    (deux décisions sont "similaires" si elles partagent au moins un grief).
  - Étage 2 : une régression logistique indépendante par catégorie retenue
    (one-vs-rest fait main), chacune pondérée via class_weight issu de
    foldXX_weights.json.

Entrées (par fold, dans training/classification/data/train/) :
  - foldXX_train.csv, foldXX_test.csv, foldXX_weights.json

Sorties (par fold, dans training/models/classification/foldXX/) :
  - embedding_body/      (corps SentenceTransformer fine-tuné)
  - head_<categorie>.joblib   (une régression logistique par catégorie)
  - categories.json      (ordre des catégories retenues pour ce fold)

Usage :
  python train_classification.py
"""

import json
import logging
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sentence_transformers import InputExample, losses
# from setfit import SetFitModel
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from torch.utils.data import DataLoader

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("train_classification")

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DATA_TRAIN_DIR = BASE_DIR / "data" / "train"
MODELS_DIR = BASE_DIR.parents[0] / "models" / "classification"

# EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
EMBEDDING_MODEL_NAME = "dangvantuan/sentence-camembert-base"

# Hyperparamètres par défaut SetFit pour le fine-tuning du corps
NUM_EPOCHS = 3
BATCH_SIZE = 16
WARMUP_STEPS = 10


# --------------------------------------------------------------------------
# Étape 1 — Chargement des artefacts du fold
# --------------------------------------------------------------------------

def discover_folds() -> list:
    """Détecte automatiquement les folds disponibles dans data/train/."""
    train_files = sorted(DATA_TRAIN_DIR.glob("fold*_train.csv"))
    fold_ids = [re.match(r"fold(\d+)_train\.csv", f.name).group(1) for f in train_files]
    logger.info("Folds détectés : %s", fold_ids)
    return fold_ids


def load_fold(fold_id: str):
    """Charge train/test/weights pour un fold donné. Les catégories à
    classifier sont dérivées des clés de foldXX_weights.json (source unique
    de vérité, pas de re-hardcodage)."""
    train_df = pd.read_csv(DATA_TRAIN_DIR / f"fold{fold_id}_train.csv")
    test_df = pd.read_csv(DATA_TRAIN_DIR / f"fold{fold_id}_test.csv")

    with open(DATA_TRAIN_DIR / f"fold{fold_id}_weights.json", "r", encoding="utf-8") as f:
        weights = json.load(f)

    categories = list(weights.keys())
    logger.info("Fold %s : %d catégories, %d train / %d test",
                fold_id, len(categories), len(train_df), len(test_df))
    return train_df, test_df, weights, categories


# --------------------------------------------------------------------------
# Étape 2 — Génération des paires multi-label (option 3)
# --------------------------------------------------------------------------

def generate_multilabel_pairs(texts: list, label_matrix: np.ndarray) -> list:
    """Génère toutes les paires (i, j) du train. Label de pairing = indice de
    Jaccard entre les ensembles de griefs des deux décisions (proportion de
    labels partagés), plutôt qu'un simple 0/1 — évite qu'un grief dominant
    (LCB-FT) dilue le signal des catégories rares dans le pairing."""
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
# Étape 3 — Fine-tuning du corps d'embeddings (étage 1)
# --------------------------------------------------------------------------
def finetune_embedding_body(train_examples: list) -> SentenceTransformer:

    """Charge le modèle de base et fine-tune son corps SentenceTransformer
    sur les paires générées, via la perte CosineSimilarityLoss (défaut SetFit).
    Aucune pondération appliquée à cet étage, comme convenu."""
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


# --------------------------------------------------------------------------
# Étape 4 — Extraction des embeddings
# --------------------------------------------------------------------------
def encode_texts(body: SentenceTransformer, texts: list) -> np.ndarray:
    return body.encode(texts, show_progress_bar=True)



def train_category_heads(X_train: np.ndarray, train_df: pd.DataFrame,
                          categories: list, weights: dict) -> dict:
    """Entraîne un k-NN indépendant par catégorie, avec k adapté au nombre
    d'exemples positifs disponibles et un seuil de décision dérivé du
    déséquilibre de classe (remplace class_weight, sans équivalent en k-NN)."""
    heads = {}
    for category in categories:
        y = train_df[category].to_numpy()

        n_pos = weights[category]["n_pos"]
        n_neg = weights[category]["n_neg"]
        k = max(1, min(5, n_pos))
        threshold = n_pos / (n_pos + n_neg)

        clf = KNeighborsClassifier(n_neighbors=k, weights="distance")
        clf.fit(X_train, y)

        heads[category] = {"model": clf, "threshold": threshold}

        logger.info(
            "Tête entraînée : '%s' (k=%d, threshold=%.4f, n_pos=%d)",
            category, k, threshold, n_pos,
        )

    return heads


# --------------------------------------------------------------------------
# Étape 6 — Sauvegarde
# --------------------------------------------------------------------------

def save_fold_artifacts(fold_id: str, body: SentenceTransformer, heads: dict, categories: list):
    fold_dir = MODELS_DIR / f"fold{fold_id}"
    fold_dir.mkdir(parents=True, exist_ok=True)


    body.save(str(fold_dir / "embedding_body"))

    for category, bundle in heads.items():
        safe_name = re.sub(r"[^a-z0-9]+", "_", category.lower()).strip("_")
        joblib.dump(bundle, fold_dir / f"head_{safe_name}.joblib")

    with open(fold_dir / "categories.json", "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)

    logger.info("Fold %s : artefacts sauvegardés dans %s", fold_id, fold_dir)


# --------------------------------------------------------------------------
# Étape 7 — Boucle sur tous les folds
# --------------------------------------------------------------------------

def main():
    fold_ids = discover_folds()

    for fold_id in fold_ids:
        logger.info("=== Fold %s ===", fold_id)
        train_df, test_df, weights, categories = load_fold(fold_id)

        label_matrix = train_df[categories].to_numpy()
        train_texts = train_df["text"].tolist()

        
        train_examples = generate_multilabel_pairs(train_texts, label_matrix)
        body = finetune_embedding_body(train_examples)

        X_train = encode_texts(body, train_texts)
        heads = train_category_heads(X_train, train_df, categories, weights)

        save_fold_artifacts(fold_id, body, heads, categories)

    logger.info("Terminé.")


if __name__ == "__main__":
    main()
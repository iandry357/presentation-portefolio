"""
evaluate.py — MVP Banque de France / classification multi-label

Évalue chaque fold produit par train_classification.py sur son test respectif,
calcule precision/recall/F1 par catégorie, puis agrège (moyenne ± écart-type)
sur l'ensemble des folds.

Entrées :
  - training/classification/data/train/foldXX_test.csv
  - training/models/classification/foldXX/ (embedding_body/, head_*.joblib, categories.json)

Sortie :
  - training/models/classification/evaluation_summary.json

Usage :
  python evaluate.py
"""

import json
import logging
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics import precision_recall_fscore_support

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("evaluate")

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DATA_TRAIN_DIR = BASE_DIR / "data" / "train"
MODELS_DIR = BASE_DIR.parents[0] / "models" / "classification"

SUMMARY_PATH = MODELS_DIR / "evaluation_summary.json"


# --------------------------------------------------------------------------
# Chargement des artefacts d'un fold
# --------------------------------------------------------------------------

def discover_folds() -> list:
    """Détecte les folds disponibles à partir des dossiers de modèles."""
    fold_dirs = sorted(MODELS_DIR.glob("fold*"))
    fold_ids = [d.name.replace("fold", "") for d in fold_dirs if d.is_dir()]
    logger.info("Folds détectés : %s", fold_ids)
    return fold_ids


def safe_category_filename(category: str) -> str:
    """Doit rester identique à la fonction utilisée dans train_classification.py
    pour reconstruire le nom de fichier d'une tête à partir du nom de catégorie."""
    return re.sub(r"[^a-z0-9]+", "_", category.lower()).strip("_")


def load_fold_artifacts(fold_id: str):
    """Charge le test set, le corps d'embeddings, les têtes et les catégories
    d'un fold donné."""
    fold_dir = MODELS_DIR / f"fold{fold_id}"

    test_df = pd.read_csv(DATA_TRAIN_DIR / f"fold{fold_id}_test.csv")

    with open(fold_dir / "categories.json", "r", encoding="utf-8") as f:
        categories = json.load(f)

    body = SentenceTransformer(str(fold_dir / "embedding_body"))

    heads = {}
    for category in categories:
        head_path = fold_dir / f"head_{safe_category_filename(category)}.joblib"
        heads[category] = joblib.load(head_path)

    return test_df, body, heads, categories


# --------------------------------------------------------------------------
# Calcul des métriques par catégorie, pour un fold
# --------------------------------------------------------------------------

def evaluate_fold(test_df: pd.DataFrame, body: SentenceTransformer,
                   heads: dict, categories: list) -> dict:
    """Encode le test set et calcule precision/recall/F1 par catégorie."""
    texts = test_df["text"].tolist()
    X_test = body.encode(texts, show_progress_bar=False)

    
    fold_metrics = {}
    for category in categories:
        y_true = test_df[category].to_numpy()

        bundle = heads[category]
        clf, threshold = bundle["model"], bundle["threshold"]
        proba_positive = clf.predict_proba(X_test)[:, list(clf.classes_).index(1)]
        y_pred = (proba_positive >= threshold).astype(int)

        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, average="binary", zero_division=0
        )
        fold_metrics[category] = {
            "precision": round(float(precision), 4),
            "recall": round(float(recall), 4),
            "f1": round(float(f1), 4),
            "n_test": len(y_true),
            "n_positive_test": int(y_true.sum()),
        }

    return fold_metrics


# --------------------------------------------------------------------------
# Agrégation sur l'ensemble des folds
# --------------------------------------------------------------------------

def aggregate_metrics(per_fold_metrics: dict, categories: list) -> dict:
    """Calcule moyenne et écart-type de chaque métrique, par catégorie,
    sur l'ensemble des folds. Conserve aussi le détail par fold pour
    traçabilité (utile pour documenter la fragilité de certaines catégories)."""
    summary = {}

    for category in categories:
        precisions, recalls, f1s = [], [], []
        per_fold_detail = {}

        for fold_id, fold_metrics in per_fold_metrics.items():
            if category not in fold_metrics:
                continue
            m = fold_metrics[category]
            precisions.append(m["precision"])
            recalls.append(m["recall"])
            f1s.append(m["f1"])
            per_fold_detail[fold_id] = m

        summary[category] = {
            "precision_mean": round(float(np.mean(precisions)), 4),
            "precision_std": round(float(np.std(precisions)), 4),
            "recall_mean": round(float(np.mean(recalls)), 4),
            "recall_std": round(float(np.std(recalls)), 4),
            "f1_mean": round(float(np.mean(f1s)), 4),
            "f1_std": round(float(np.std(f1s)), 4),
            "n_folds": len(precisions),
            "per_fold": per_fold_detail,
        }

    return summary


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    fold_ids = discover_folds()
    per_fold_metrics = {}
    categories = None

    for fold_id in fold_ids:
        logger.info("=== Évaluation fold %s ===", fold_id)
        test_df, body, heads, fold_categories = load_fold_artifacts(fold_id)

        if categories is None:
            categories = fold_categories
        elif set(categories) != set(fold_categories):
            logger.warning(
                "Fold %s : catégories différentes de celles du premier fold "
                "(%s vs %s) — vérifier la cohérence de compute_retained_categories.",
                fold_id, fold_categories, categories,
            )

        fold_metrics = evaluate_fold(test_df, body, heads, fold_categories)
        per_fold_metrics[fold_id] = fold_metrics

        for category, m in fold_metrics.items():
            logger.info(
                "  %-70s | precision=%.3f recall=%.3f f1=%.3f (n_pos=%d/%d)",
                category, m["precision"], m["recall"], m["f1"],
                m["n_positive_test"], m["n_test"],
            )

    summary = aggregate_metrics(per_fold_metrics, categories)

    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info("Résumé écrit : %s", SUMMARY_PATH)
    logger.info("Terminé.")


if __name__ == "__main__":
    main()
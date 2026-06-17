"""
YOLO Evaluate — Évaluation du modèle SG Assurances sur le split test
Entrée  : models/yolo_sg_assurances.pt + data/datasets/yolo/dataset.yaml
Sortie  : models/yolo_metrics.json — métriques pour register_model.py

Seuil MVP : mAP50 global ≥ 0.40 → éligible Vertex AI
"""

import json
import sys
import shutil
from pathlib import Path

from ultralytics import YOLO

# ─────────────────────────────────────────
# Chemins
# ─────────────────────────────────────────
TRAINING_DIR = Path(__file__).parent.parent
DATA_DIR     = TRAINING_DIR / "data"
MODELS_DIR   = TRAINING_DIR / "models"
YAML_PATH    = DATA_DIR / "datasets" / "yolo" / "dataset.yaml"
MODEL_PATH   = MODELS_DIR / "yolo_sg_assurances.pt"
METRICS_PATH = MODELS_DIR / "yolo_metrics.json"
RUNS_DIR     = TRAINING_DIR / "runs" / "yolo" / "sg_assurances_eval"

# ─────────────────────────────────────────
# Paramètres
# ─────────────────────────────────────────
MAP50_THRESHOLD = 0.40   # seuil MVP pour éligibilité Vertex AI
CLASSES = [
    "contract_block",
    "identity_block",
    "amount_block",
    "signature_block",
]


# ─────────────────────────────────────────
# Validation prérequis
# ─────────────────────────────────────────
def _check_prerequisites() -> None:
    if not MODEL_PATH.exists():
        print(f"[yolo/evaluate] Modèle introuvable : {MODEL_PATH}")
        print("[yolo/evaluate] Lance yolo/train.py d'abord")
        sys.exit(1)
    if not YAML_PATH.exists():
        print(f"[yolo/evaluate] dataset.yaml introuvable : {YAML_PATH}")
        print("[yolo/evaluate] Lance yolo/dataset.py d'abord")
        sys.exit(1)


# ─────────────────────────────────────────
# Évaluation
# ─────────────────────────────────────────
def evaluate() -> dict:
    """
    Évalue le modèle sur le split test.
    Retourne le dict de métriques.
    """
    _check_prerequisites()

    print(f"[yolo/evaluate] Chargement modèle : {MODEL_PATH}")
    model = YOLO(str(MODEL_PATH))

    print(f"[yolo/evaluate] Évaluation sur split test...")
    results = model.val(
        data=str(YAML_PATH),
        split="test",
        project=str(RUNS_DIR.parent),
        name=RUNS_DIR.name,
        exist_ok=True,
        verbose=True,
        device=0,
    )

    # ─────────────────────────────────────
    # Extraction métriques globales
    # ─────────────────────────────────────
    map50     = float(results.box.map50)
    map50_95  = float(results.box.map)
    precision = float(results.box.mp)
    recall    = float(results.box.mr)

    # Métriques par classe
    per_class = {}
    if results.box.ap_class_index is not None:
        for i, cls_idx in enumerate(results.box.ap_class_index):
            cls_name = CLASSES[int(cls_idx)] if int(cls_idx) < len(CLASSES) else f"class_{cls_idx}"
            per_class[cls_name] = {
                "mAP50":     float(results.box.ap50[i]) if i < len(results.box.ap50) else 0.0,
                "mAP50_95":  float(results.box.ap[i])   if i < len(results.box.ap)   else 0.0,
            }

    metrics = {
        "model":      str(MODEL_PATH.name),
        "framework":  "ultralytics-yolov8",
        "task":       "object_detection",
        "dataset":    str(YAML_PATH),
        "split":      "test",
        "global": {
            "mAP50":     map50,
            "mAP50_95":  map50_95,
            "precision": precision,
            "recall":    recall,
        },
        "per_class":  per_class,
        "threshold":  MAP50_THRESHOLD,
        "eligible_vertex_ai": map50 >= MAP50_THRESHOLD,
    }

    return metrics


# ─────────────────────────────────────────
# Sauvegarde métriques
# ─────────────────────────────────────────
def save_metrics(metrics: dict) -> None:
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(f"[yolo/evaluate] Métriques sauvegardées → {METRICS_PATH}")


# ─────────────────────────────────────────
# Affichage résumé
# ─────────────────────────────────────────
def print_summary(metrics: dict) -> None:
    g = metrics["global"]
    print("\n" + "="*50)
    print("[yolo/evaluate] RÉSULTATS SUR TEST SET")
    print("="*50)
    print(f"  mAP50       : {g['mAP50']:.4f}")
    print(f"  mAP50-95    : {g['mAP50_95']:.4f}")
    print(f"  Precision   : {g['precision']:.4f}")
    print(f"  Recall      : {g['recall']:.4f}")
    print("\n  Par classe :")
    for cls, m in metrics["per_class"].items():
        print(f"    {cls:<20} mAP50={m['mAP50']:.4f}  mAP50-95={m['mAP50_95']:.4f}")
    print("="*50)
    eligible = metrics["eligible_vertex_ai"]
    status = "✅ ÉLIGIBLE Vertex AI" if eligible else f"❌ En dessous du seuil {metrics['threshold']}"
    print(f"  Statut MVP  : {status}")
    print("="*50 + "\n")


# ─────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────
if __name__ == "__main__":
    metrics = evaluate()
    print_summary(metrics)
    save_metrics(metrics)

    if not metrics["eligible_vertex_ai"]:
        print("[yolo/evaluate] Modèle non éligible — améliorer le dataset avant register_model.py")
        sys.exit(1)

    print("[yolo/evaluate] Done — prêt pour yolo/register_model.py")
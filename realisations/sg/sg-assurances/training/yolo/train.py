"""
YOLO Train — Re-fine-tuning yolov8s-doclaynet sur PDFs synthétiques SG Assurances
Base    : yolov8s-doclaynet (HuggingFace) — 11 classes DocLayNet génériques
Sortie  : models/yolo_sg_assurances.pt — meilleur modèle (best mAP50)

Transfer learning cascade :
  yolov8s-doclaynet → fine-tuning 4 classes métier SG → modèle final 4 classes
"""

import shutil
import sys
from pathlib import Path

from ultralytics import YOLO

# ─────────────────────────────────────────
# Chemins
# ─────────────────────────────────────────
TRAINING_DIR = Path(__file__).parent.parent
DATA_DIR     = TRAINING_DIR / "data"
MODELS_DIR   = TRAINING_DIR / "models"
YAML_PATH    = DATA_DIR / "datasets" / "yolo" / "dataset.yaml"
OUTPUT_MODEL = MODELS_DIR / "yolo_sg_assurances.pt"
RUNS_DIR     = TRAINING_DIR / "runs"

MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────
# Paramètres entraînement
# ─────────────────────────────────────────
# BASE_MODEL  = "hustvl/yolov8s-doclaynet"   # HuggingFace — poids pré-entraînés
BASE_MODEL  = str(MODELS_DIR / "yolov8s-doclaynet.pt")
EPOCHS      = 100
BATCH_SIZE  = 16
IMG_SIZE    = 640
PATIENCE    = 25      # early stopping — arrêt si pas d'amélioration sur 5 epochs
SEED        = 42
PROJECT     = str(RUNS_DIR / "yolo")
RUN_NAME    = "sg_assurances_v1"


# ─────────────────────────────────────────
# Validation prérequis
# ─────────────────────────────────────────
def _check_prerequisites() -> None:
    if not YAML_PATH.exists():
        print(f"[yolo/train] dataset.yaml introuvable : {YAML_PATH}")
        print("[yolo/train] Lance yolo/dataset.py d'abord")
        sys.exit(1)

    import torch
    if not torch.cuda.is_available():
        print("[yolo/train] WARN — CUDA non disponible, entraînement sur CPU (très lent)")
    else:
        print(f"[yolo/train] GPU détecté : {torch.cuda.get_device_name(0)}")


# ─────────────────────────────────────────
# Entraînement
# ─────────────────────────────────────────
def train() -> Path:
    """
    Pipeline d'entraînement complet.
    Retourne le chemin vers le meilleur modèle sauvegardé.
    """
    _check_prerequisites()

    print(f"[yolo/train] Chargement modèle de base : {BASE_MODEL}")
    model = YOLO(BASE_MODEL)

    print(f"[yolo/train] Démarrage entraînement — {EPOCHS} epochs, batch={BATCH_SIZE}")
    print(f"[yolo/train] Dataset : {YAML_PATH}")

    results = model.train(
        data=str(YAML_PATH),
        epochs=EPOCHS,
        batch=BATCH_SIZE,
        imgsz=IMG_SIZE,
        patience=PATIENCE,
        seed=SEED,
        project=PROJECT,
        name=RUN_NAME,
        exist_ok=True,       # écrase le run précédent si même nom
        save=True,           # sauvegarde checkpoints
        save_period=-1,      # ne sauvegarde pas à chaque epoch — uniquement le meilleur
        plots=True,          # courbes loss + métriques
        verbose=True,
        device=0,            # GPU 0
    )

    # Chemin vers le meilleur modèle produit par Ultralytics
    best_model_src = Path(PROJECT) / RUN_NAME / "weights" / "best.pt"

    if not best_model_src.exists():
        print(f"[yolo/train] ERREUR — best.pt introuvable : {best_model_src}")
        sys.exit(1)

    # Copie vers models/yolo_sg_assurances.pt
    shutil.copy2(best_model_src, OUTPUT_MODEL)
    print(f"[yolo/train] Meilleur modèle sauvegardé → {OUTPUT_MODEL}")

    return OUTPUT_MODEL


# ─────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────
if __name__ == "__main__":
    model_path = train()
    print(f"\n[yolo/train] Done — modèle prêt : {model_path}")
    print("Prochaine étape : python yolo/evaluate.py")
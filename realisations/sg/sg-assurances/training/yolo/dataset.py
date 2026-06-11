"""
YOLO Dataset — Préparation dataset Ultralytics depuis annotations synthétiques SG
Entrée  : data/annotations/images/ + data/annotations/labels/
Sortie  : data/datasets/yolo/{train,val,test}/{images,labels}/ + dataset.yaml

Classes :
  0 — contract_block
  1 — identity_block
  2 — amount_block
  3 — signature_block
"""

import shutil
import random
import yaml
from pathlib import Path

# ─────────────────────────────────────────
# Chemins
# ─────────────────────────────────────────
TRAINING_DIR  = Path(__file__).parent.parent
DATA_DIR      = TRAINING_DIR / "data"
ANNOT_DIR     = DATA_DIR / "annotations"
IMAGES_SRC    = ANNOT_DIR / "images"
LABELS_SRC    = ANNOT_DIR / "labels"
DATASET_DIR   = DATA_DIR / "datasets" / "yolo"
YAML_PATH     = DATASET_DIR / "dataset.yaml"

# ─────────────────────────────────────────
# Paramètres
# ─────────────────────────────────────────
SPLIT_TRAIN = 0.70
SPLIT_VAL   = 0.20
SPLIT_TEST  = 0.10
SEED        = 42

CLASSES = [
    "contract_block",
    "identity_block",
    "amount_block",
    "signature_block",
]


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────
def _clean_dataset_dir() -> None:
    """Vide le répertoire dataset avant chaque run."""
    if DATASET_DIR.exists():
        shutil.rmtree(DATASET_DIR)
        print(f"[yolo/dataset] Nettoyage {DATASET_DIR}")
    DATASET_DIR.mkdir(parents=True)


def _collect_valid_pairs() -> list[tuple[Path, Path]]:
    """
    Collecte les paires (image, label) valides :
    - image PNG existe
    - label .txt existe et non vide (pages sans annotation écartées)
    """
    pairs = []
    for img_path in sorted(IMAGES_SRC.glob("*.png")):
        lbl_path = LABELS_SRC / (img_path.stem + ".txt")
        if not lbl_path.exists():
            continue
        if lbl_path.stat().st_size == 0:
            continue
        pairs.append((img_path, lbl_path))

    print(f"[yolo/dataset] {len(pairs)} paires valides (labels non vides)")
    return pairs


def _split_pairs(
    pairs: list[tuple[Path, Path]],
) -> dict[str, list[tuple[Path, Path]]]:
    """Split reproductible train/val/test avec seed fixe."""
    random.seed(SEED)
    shuffled = pairs.copy()
    random.shuffle(shuffled)

    n = len(shuffled)
    n_train = int(n * SPLIT_TRAIN)
    n_val   = int(n * SPLIT_VAL)

    splits = {
        "train": shuffled[:n_train],
        "val":   shuffled[n_train:n_train + n_val],
        "test":  shuffled[n_train + n_val:],
    }

    for name, s in splits.items():
        print(f"[yolo/dataset]   {name}: {len(s)} paires")

    return splits


def _copy_split(name: str, pairs: list[tuple[Path, Path]]) -> None:
    """Copie images et labels dans la structure Ultralytics."""
    img_dir = DATASET_DIR / name / "images"
    lbl_dir = DATASET_DIR / name / "labels"
    img_dir.mkdir(parents=True)
    lbl_dir.mkdir(parents=True)

    for img_src, lbl_src in pairs:
        shutil.copy2(img_src, img_dir / img_src.name)
        shutil.copy2(lbl_src, lbl_dir / lbl_src.name)


def _write_yaml() -> None:
    """Génère le dataset.yaml requis par Ultralytics."""
    config = {
        "path": str(DATASET_DIR.resolve()),
        "train": "train/images",
        "val":   "val/images",
        "test":  "test/images",
        "nc":    len(CLASSES),
        "names": CLASSES,
    }
    with open(YAML_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    print(f"[yolo/dataset] dataset.yaml écrit → {YAML_PATH}")


# ─────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────
def prepare_dataset() -> Path:
    """
    Pipeline complet de préparation du dataset YOLO.
    Retourne le chemin vers dataset.yaml.
    """
    print("[yolo/dataset] Préparation dataset YOLO...")

    _clean_dataset_dir()

    pairs = _collect_valid_pairs()
    if not pairs:
        raise RuntimeError(
            "Aucune paire valide trouvée — lance annotator.py d'abord"
        )

    splits = _split_pairs(pairs)

    for name, split_pairs in splits.items():
        _copy_split(name, split_pairs)
        print(f"[yolo/dataset]   {name} copié → {DATASET_DIR / name}")

    _write_yaml()

    print(f"[yolo/dataset] Done — dataset prêt dans {DATASET_DIR}")
    return YAML_PATH


# ─────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────
if __name__ == "__main__":
    yaml_path = prepare_dataset()
    print(f"\nDataset YAML : {yaml_path}")
    print("Prêt pour yolo/train.py")
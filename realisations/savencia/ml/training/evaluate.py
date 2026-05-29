"""
evaluate.py
───────────
Évalue best_model.pt sur le val set.
Affiche matrice de confusion + métriques dans le terminal.
"""

from pathlib import Path

import torch
import torch.nn as nn
import numpy as np
from torch.utils.data import DataLoader
from transformers import ViTForImageClassification
from sklearn.metrics import classification_report, confusion_matrix

from dataset import CLASS_NAMES, make_splits


# ── Config ─────────────────────────────────────────────────────────────────────

DATASET_ROOT = "../sample_images/CHEESE-HIDB-224"
MODEL_PATH   = "../models/best_model.pt"
BATCH_SIZE   = 16
NUM_WORKERS  = 8


# ── Chargement modèle ──────────────────────────────────────────────────────────

def load_model(model_path: str, num_classes: int, device: torch.device) -> nn.Module:
    checkpoint = torch.load(model_path, map_location=device)
    cfg = checkpoint["config"]

    model = ViTForImageClassification.from_pretrained(
        cfg["pretrained_name"],
        num_labels=num_classes,
        ignore_mismatched_sizes=True,
    )
    model.load_state_dict(checkpoint["model_state"])
    model.to(device)
    model.eval()
    print(f"Modèle chargé — époque {checkpoint['epoch']} | val_acc={checkpoint['val_acc']:.3f}")
    return model


# ── Inférence ──────────────────────────────────────────────────────────────────

def run_inference(model, loader, device):
    all_preds, all_labels = [], []
    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            outputs = model(pixel_values=images).logits
            preds = outputs.argmax(dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(labels.numpy())
    return np.array(all_labels), np.array(all_preds)


# ── Affichage ──────────────────────────────────────────────────────────────────

def print_confusion_matrix(labels, preds):
    cm = confusion_matrix(labels, preds)
    short_names = [n.replace("Extra-Hard", "EH").replace("Semi-Hard", "SH").replace("Hard", "H") for n in CLASS_NAMES]
    col_width = 12
    header = " " * col_width + "".join(f"{n:>{col_width}}" for n in short_names)
    print("\n=== Matrice de confusion ===")
    print(header)
    for i, row in enumerate(cm):
        row_str = f"{short_names[i]:>{col_width}}" + "".join(f"{v:>{col_width}}" for v in row)
        print(row_str)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device : {device}")

    _, val_ds = make_splits(DATASET_ROOT, val_ratio=0.2, seed=42)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=NUM_WORKERS)
    print(f"Val set : {len(val_ds)} images")

    model  = load_model(MODEL_PATH, num_classes=len(CLASS_NAMES), device=device)
    labels, preds = run_inference(model, val_loader, device)

    print("\n=== Rapport de classification ===")
    print(classification_report(labels, preds, target_names=CLASS_NAMES, digits=3))

    print_confusion_matrix(labels, preds)


if __name__ == "__main__":
    main()
import json
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.amp import GradScaler, autocast
from torch.utils.data import DataLoader
from transformers import ViTForImageClassification

from tqdm import tqdm

from dataset import CLASS_NAMES, compute_class_weights, make_splits


# ── Config ─────────────────────────────────────────────────────────────────────

@dataclass
class TrainConfig:
    dataset_root:    str   = "../sample_images/CHEESE-HIDB-224"
    model_dir:       str   = "../models"
    registry_path:   str   = "../models/model_registry.json"
    pretrained_name: str   = "google/vit-base-patch16-224"
    num_classes:     int   = 6
    val_ratio:       float = 0.2
    epochs:          int   = 20
    early_stop:      int   = 7
    batch_size:      int   = 16
    lr:              float = 1e-4
    num_workers:     int   = 8
    seed:            int   = 42


# ── Reproductibilité ───────────────────────────────────────────────────────────

def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True


# ── Modèle ─────────────────────────────────────────────────────────────────────

def build_model(cfg: TrainConfig) -> nn.Module:
    model = ViTForImageClassification.from_pretrained(
        cfg.pretrained_name,
        num_labels=cfg.num_classes,
        ignore_mismatched_sizes=True,
    )
    # Gel du backbone — seule la tête classifier est entraînable
    # for name, param in model.named_parameters():
    #     if "classifier" not in name:
    #         param.requires_grad = False
    for name, param in model.named_parameters():
        if "classifier" not in name and "encoder.layer.10" not in name and "encoder.layer.11" not in name:
            param.requires_grad = False

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total     = sum(p.numel() for p in model.parameters())
    print(f"Paramètres entraînables : {trainable:,} / {total:,}")
    return model


# ── Boucle époque ──────────────────────────────────────────────────────────────

def run_epoch(
    model:     nn.Module,
    loader:    DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer | None,
    scaler:    GradScaler,
    device:    torch.device,
    train:     bool,
) -> tuple[float, float]:
    model.train() if train else model.eval()
    total_loss, correct, total = 0.0, 0, 0

    ctx = torch.enable_grad() if train else torch.no_grad()
    with ctx:
        desc = "Train" if train else "Val"
        for images, labels in tqdm(loader, desc=desc, leave=False):
        # for images, labels in loader:
            images, labels = images.to(device), labels.to(device)

            with autocast('cuda'):
                outputs = model(pixel_values=images).logits
                loss    = criterion(outputs, labels)

            if train:
                optimizer.zero_grad()
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()

            total_loss += loss.item() * labels.size(0)
            correct    += (outputs.argmax(dim=1) == labels).sum().item()
            total      += labels.size(0)

    return total_loss / total, correct / total


# ── Registry ───────────────────────────────────────────────────────────────────

def update_registry(registry_path: str, entry: dict) -> None:
    path = Path(registry_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    registry = json.loads(path.read_text()) if path.exists() else []
    registry.append(entry)
    path.write_text(json.dumps(registry, indent=2))


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    cfg    = TrainConfig()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device : {device}")

    set_seed(cfg.seed)

    # Data
    train_ds, val_ds = make_splits(cfg.dataset_root, cfg.val_ratio, cfg.seed)
    print(f"Train : {len(train_ds)} | Val : {len(val_ds)}")

    train_loader = DataLoader(train_ds, batch_size=cfg.batch_size, shuffle=True,  num_workers=cfg.num_workers, pin_memory=True)
    val_loader   = DataLoader(val_ds,   batch_size=cfg.batch_size, shuffle=False, num_workers=cfg.num_workers, pin_memory=True)

    # Modèle
    model = build_model(cfg).to(device)

    # Loss avec class weights
    weights   = compute_class_weights(train_ds).to(device)
    criterion = nn.CrossEntropyLoss(weight=weights)

    # Optimizer — uniquement sur les paramètres entraînables
    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=cfg.lr,
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=2
    )
    scaler = GradScaler('cuda')

    # Entraînement
    best_val_acc   = 0.0
    best_epoch     = 0
    patience_count = 0
    model_dir      = Path(cfg.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    best_model_path = model_dir / "best_model.pt"

    for epoch in range(1, cfg.epochs + 1):
        t0 = time.time()

        train_loss, train_acc = run_epoch(model, train_loader, criterion, optimizer, scaler, device, train=True)
        val_loss,   val_acc   = run_epoch(model, val_loader,   criterion, None,      scaler, device, train=False)
        scheduler.step(val_loss)

        elapsed = time.time() - t0
        print(
            f"Époque {epoch:02d}/{cfg.epochs} | "
            f"Train loss={train_loss:.4f} acc={train_acc:.3f} | "
            f"Val loss={val_loss:.4f} acc={val_acc:.3f} | "
            f"{elapsed:.1f}s"
        )

        # Sauvegarde meilleur modèle
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_epoch   = epoch
            patience_count = 0
            torch.save({
                "epoch":       epoch,
                "model_state": model.state_dict(),
                "optim_state": optimizer.state_dict(),
                "val_acc":     val_acc,
                "config":      asdict(cfg),
            }, best_model_path)
            print(f"  ✓ Meilleur modèle sauvegardé (val_acc={val_acc:.3f})")
        else:
            patience_count += 1
            print(f"  – Pas d'amélioration ({patience_count}/{cfg.early_stop})")
            if patience_count >= cfg.early_stop:
                print(f"Early stopping à l'époque {epoch}.")
                break

    # Registry
    update_registry(cfg.registry_path, {
        "timestamp":    datetime.now().isoformat(),
        "best_epoch":   best_epoch,
        "best_val_acc": round(best_val_acc, 4),
        "model_path":   str(best_model_path),
        "config":       asdict(cfg),
    })
    print(f"\nEntraînement terminé. Meilleur val_acc={best_val_acc:.3f} à l'époque {best_epoch}.")
    print(f"Modèle : {best_model_path}")


if __name__ == "__main__":
    main()
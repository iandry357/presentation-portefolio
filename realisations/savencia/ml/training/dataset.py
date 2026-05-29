from pathlib import Path
from typing import Tuple, List, Dict

import torch
from torch.utils.data import Dataset, random_split
from torchvision import transforms
from PIL import Image


# ── Labels ────────────────────────────────────────────────────────────────────

CHEESE_TYPES  = ["Extra-Hard", "Hard", "Semi-Hard"]
CHEESE_STATES = ["Target", "NotTarget"]

CLASS_NAMES: List[str] = [
    f"{t}_{s}" for t in CHEESE_TYPES for s in CHEESE_STATES
]  # 6 classes : Extra-Hard_Target, Extra-Hard_NotTarget, ...

CLASS_TO_IDX: Dict[str, int] = {name: i for i, name in enumerate(CLASS_NAMES)}


# ── Transformations ────────────────────────────────────────────────────────────

def get_transforms(train: bool) -> transforms.Compose:
    base = [
        # transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ]
    if train:
        augment = [
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(degrees=15),
        ]
        return transforms.Compose(augment + base)
    return transforms.Compose(base)


# ── Dataset ────────────────────────────────────────────────────────────────────

class CheeseDataset(Dataset):
    """
    Dataset CR-IDB — 6 classes (3 types x 2 états de maturité).

    Structure attendue :
        dataset_root/
            Extra-Hard/Target/*.JPG
            Extra-Hard/NotTarget/*.JPG
            Hard/Target/*.JPG
            ...
    """

    def __init__(self, dataset_root: str | Path, train: bool = True) -> None:
        self.root = Path(dataset_root)
        self.transform = get_transforms(train)
        self.samples: List[Tuple[Path, int]] = self._scan()

    def _scan(self) -> List[Tuple[Path, int]]:
        samples = []
        for cheese_type in CHEESE_TYPES:
            for state in CHEESE_STATES:
                folder = self.root / cheese_type / state
                if not folder.exists():
                    raise FileNotFoundError(f"Dossier introuvable : {folder}")
                images = [f for f in folder.iterdir() if f.suffix.upper() == ".JPG"]
                label = CLASS_TO_IDX[f"{cheese_type}_{state}"]
                for img_path in images:
                    samples.append((img_path, label))
        return samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int]:
        img_path, label = self.samples[idx]
        image = Image.open(img_path).convert("RGB")
        return self.transform(image), label


# ── Split train / val ──────────────────────────────────────────────────────────

def make_splits(
    dataset_root: str | Path,
    val_ratio: float = 0.2,
    seed: int = 42,
) -> Tuple[CheeseDataset, CheeseDataset]:
    """
    Retourne (train_dataset, val_dataset) avec split 80/20.
    Les transformations d'augmentation sont actives uniquement sur le train set.
    """
    train_ds = CheeseDataset(dataset_root, train=True)
    val_ds   = CheeseDataset(dataset_root, train=False)

    n_total = len(train_ds)
    n_val   = int(n_total * val_ratio)
    n_train = n_total - n_val

    generator = torch.Generator().manual_seed(seed)
    train_indices, val_indices = random_split(
        range(n_total), [n_train, n_val], generator=generator
    )

    train_ds.samples = [train_ds.samples[i] for i in train_indices]
    val_ds.samples   = [val_ds.samples[i]   for i in val_indices]

    return train_ds, val_ds


# ── Class weights (pour compenser le déséquilibre 1:2) ───────────────────────

def compute_class_weights(dataset: CheeseDataset) -> torch.Tensor:
    """
    Calcule les poids inverses des fréquences de classe.
    Destiné à être passé à nn.CrossEntropyLoss(weight=...).
    """
    counts = torch.zeros(len(CLASS_NAMES))
    for _, label in dataset.samples:
        counts[label] += 1
    weights = 1.0 / counts
    return weights / weights.sum() * len(CLASS_NAMES)
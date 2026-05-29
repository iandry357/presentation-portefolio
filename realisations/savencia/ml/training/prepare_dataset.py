"""
prepare_dataset.py
──────────────────
Pré-redimensionne les images CHEESE-HIDB de 6016x4016 → 224x224.
À lancer une seule fois avant l'entraînement.

Entrée  : ../sample_images/CHEESE-HIDB-main/
Sortie  : ../sample_images/CHEESE-HIDB-224/
"""

import multiprocessing
from pathlib import Path

from PIL import Image
from tqdm import tqdm


# ── Config ─────────────────────────────────────────────────────────────────────

SRC_ROOT   = Path("../sample_images/CHEESE-HIDB-main")
DST_ROOT   = Path("../sample_images/CHEESE-HIDB-224")
TARGET_SIZE = (224, 224)
NUM_WORKERS = 8


# ── Worker ─────────────────────────────────────────────────────────────────────

def process_image(args: tuple[Path, Path]) -> tuple[bool, str]:
    src_path, dst_path = args
    try:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(src_path) as img:
            img_resized = img.convert("RGB").resize(TARGET_SIZE, Image.LANCZOS)
            img_resized.save(dst_path, "JPEG", quality=95)
        return True, str(src_path)
    except Exception as e:
        return False, f"{src_path} — {e}"


# ── Scan ───────────────────────────────────────────────────────────────────────

def collect_tasks() -> list[tuple[Path, Path]]:
    tasks = []
    for src_path in SRC_ROOT.rglob("*"):
        if src_path.suffix.upper() == ".JPG":
            relative  = src_path.relative_to(SRC_ROOT)
            dst_path  = DST_ROOT / relative
            tasks.append((src_path, dst_path))
    return tasks


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Source : {SRC_ROOT}")
    print(f"Dest   : {DST_ROOT}")
    print(f"Workers: {NUM_WORKERS}\n")

    tasks = collect_tasks()
    print(f"{len(tasks)} images à traiter...\n")

    success, errors = 0, []

    with multiprocessing.Pool(processes=NUM_WORKERS) as pool:
        for ok, msg in tqdm(
            pool.imap_unordered(process_image, tasks),
            total=len(tasks),
            desc="Resize",
        ):
            if ok:
                success += 1
            else:
                errors.append(msg)

    print(f"\n✓ Traité : {success}/{len(tasks)}")
    if errors:
        print(f"✗ Erreurs ({len(errors)}) :")
        for e in errors:
            print(f"  {e}")
    else:
        print("Aucune erreur.")
    print(f"\nDataset prêt dans : {DST_ROOT}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
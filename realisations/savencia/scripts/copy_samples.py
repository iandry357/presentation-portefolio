import shutil
from pathlib import Path
import random

SRC  = Path(r"C:\Users\iandr\Documents\EXP\exp 2.0\projet cv\presentation-portefolio\realisations\savencia\ml\sample_images\CHEESE-HIDB-224")
DST  = Path(r"C:\Users\iandr\Documents\EXP\exp 2.0\projet cv\presentation-portefolio\frontend\public\savencia\samples")

TYPES   = ["Extra-Hard", "Hard", "Semi-Hard"]
CLASSES = ["Target", "NotTarget"]

DST.mkdir(parents=True, exist_ok=True)

for t in TYPES:
    for c in CLASSES:
        folder = SRC / t / c
        images = [f for f in folder.iterdir() if f.suffix.upper() == ".JPG"]
        if images:
            # src_file = sorted(images)[0]
            src_file = random.choice(images)
            dst_name = f"{t}_{c}.jpg"
            shutil.copy(src_file, DST / dst_name)
            print(f"{dst_name} — {src_file.name}")
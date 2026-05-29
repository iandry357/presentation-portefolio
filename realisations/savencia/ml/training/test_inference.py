import sys
sys.path.append("..")

from pathlib import Path
from vit_inference import load_model, predict
import base64
import io
from PIL import Image
import matplotlib.pyplot as plt


# Chargement modèle
cache = load_model()

# Prendre une image au hasard dans le dataset
img_path = list(Path("../sample_images/CHEESE-HIDB-224/Hard/Target").iterdir())[0]
print(f"Image testée : {img_path.name}")

from transformers import ViTForImageClassification
import torch

checkpoint = torch.load("../models/model_latest.pt", map_location="cpu")
model = ViTForImageClassification.from_pretrained(
    "google/vit-base-patch16-224",
    num_labels=6,
    ignore_mismatched_sizes=True,
)
model.load_state_dict(checkpoint["model_state"])

# Affiche la structure
for name, _ in model.named_modules():
    if "layer" in name and "11" in name:
        print(name)

# Inférence
result = predict(cache, img_path.read_bytes())

print(f"Classe prédite : {result['class_name']}")
print(f"Confiance     : {result['confidence']}")
print(f"Heatmap       : {result['heatmap_base64'][:50]}...")

# Image originale
original = Image.open(img_path).resize((224, 224))

# Heatmap
heatmap_bytes = base64.b64decode(result['heatmap_base64'])
heatmap = Image.open(io.BytesIO(heatmap_bytes))

# Affichage côte à côte
fig, axes = plt.subplots(1, 2, figsize=(10, 5))
axes[0].imshow(original)
axes[0].set_title("Image originale")
axes[0].axis("off")

axes[1].imshow(heatmap)
axes[1].set_title(f"Grad-CAM — {result['class_name']} ({result['confidence']:.2%})")
axes[1].axis("off")

plt.tight_layout()
plt.show()
"""
ner/evaluate.py
Évaluation détaillée du modèle NER fine-tuné CamemBERT.
- F1 / precision / recall par entité
- Comparaison baseline CamemBERT zero-shot vs fine-tuné
- Export rapport JSON

Lancer depuis training/ :
    python ner/evaluate.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import numpy as np
from pathlib import Path

# Retrait de ner/ du path pour éviter le shadow de evaluate.py local
import sys as _sys
_ner_path = str(Path(__file__).parent)
if _ner_path in _sys.path:
    _sys.path.remove(_ner_path)
import evaluate as hf_evaluate
if _ner_path not in _sys.path:
    _sys.path.append(_ner_path)

from datasets import load_from_disk
from transformers import (
    CamembertForTokenClassification,
    CamembertTokenizerFast,
    pipeline,
)
import torch

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------
BASE         = Path(__file__).parent.parent
DATASET_DIR  = BASE / "data" / "ner_datasets" / "ner_sg_dataset"
LABEL_MAP    = BASE / "data" / "ner_datasets" / "label_map.json"
FINETUNED    = BASE / "models" / "ner_sg_assurances"
OUTPUT_DIR   = BASE / "models" / "ner_sg_assurances"

# ---------------------------------------------------------------------------
# Chargement label map
# ---------------------------------------------------------------------------
with open(LABEL_MAP, "r") as f:
    meta = json.load(f)

label_list = meta["label_list"]
id2label   = {int(k): v for k, v in meta["id2label"].items()}
label2id   = meta["label2id"]

# ---------------------------------------------------------------------------
# Chargement dataset test
# ---------------------------------------------------------------------------
print("Chargement dataset test...")
dataset = load_from_disk(str(DATASET_DIR))
test_ds = dataset["test"]
print(f"  {len(test_ds)} exemples de test")

device = 0 if torch.cuda.is_available() else -1

# ---------------------------------------------------------------------------
# Helper — inférence batch → labels prédits
# ---------------------------------------------------------------------------
def predict(model, tokenizer, dataset) -> tuple[list, list]:
    """Retourne (true_labels, pred_labels) en format seqeval (listes de listes de strings)."""
    model.eval()
    true_all, pred_all = [], []

    for example in dataset:
        input_ids      = torch.tensor([example["input_ids"]]).to(model.device)
        attention_mask = torch.tensor([example["attention_mask"]]).to(model.device)
        labels_tensor  = example["labels"]

        with torch.no_grad():
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)

        preds = torch.argmax(outputs.logits, dim=-1)[0].cpu().numpy()

        true_row, pred_row = [], []
        for p, l in zip(preds, labels_tensor):
            if l == -100:
                continue
            true_row.append(id2label[int(l)])
            pred_row.append(id2label[int(p)])

        true_all.append(true_row)
        pred_all.append(pred_row)

    return true_all, pred_all


# ---------------------------------------------------------------------------
# Évaluation modèle fine-tuné
# ---------------------------------------------------------------------------
print(f"\nChargement modèle fine-tuné : {FINETUNED}")
ft_tokenizer = CamembertTokenizerFast.from_pretrained(str(FINETUNED))
ft_model     = CamembertForTokenClassification.from_pretrained(str(FINETUNED))
ft_model     = ft_model.to("cuda" if torch.cuda.is_available() else "cpu")

print("Inférence modèle fine-tuné sur test set...")
true_labels, ft_preds = predict(ft_model, ft_tokenizer, test_ds)

seqeval = hf_evaluate.load("seqeval")

ft_results = seqeval.compute(
    predictions=ft_preds,
    references=true_labels,
    zero_division=0,
)

# ---------------------------------------------------------------------------
# Évaluation baseline CamemBERT zero-shot
# ---------------------------------------------------------------------------
print("\nChargement baseline CamemBERT zero-shot...")
base_tokenizer = CamembertTokenizerFast.from_pretrained("camembert-base")
base_model     = CamembertForTokenClassification.from_pretrained(
    "camembert-base",
    num_labels=len(label_list),
    id2label=id2label,
    label2id=label2id,
    ignore_mismatched_sizes=True,
)
base_model = base_model.to("cuda" if torch.cuda.is_available() else "cpu")

print("Inférence baseline sur test set...")
_, base_preds = predict(base_model, base_tokenizer, test_ds)

base_results = seqeval.compute(
    predictions=base_preds,
    references=true_labels,
    zero_division=0,
)

# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------
print("\n" + "="*60)
print("RAPPORT ÉVALUATION NER — SG Assurances")
print("="*60)

print("\n--- Métriques globales ---")
print(f"{'Métrique':<20} {'Baseline':>12} {'Fine-tuné':>12} {'Delta':>10}")
print("-" * 56)
for metric in ["overall_f1", "overall_precision", "overall_recall", "overall_accuracy"]:
    base_val = base_results.get(metric, 0.0)
    ft_val   = ft_results.get(metric, 0.0)
    delta    = ft_val - base_val
    label    = metric.replace("overall_", "")
    print(f"{label:<20} {base_val:>12.4f} {ft_val:>12.4f} {delta:>+10.4f}")

print("\n--- F1 par entité (fine-tuné) ---")
entity_metrics = {}
for key, val in ft_results.items():
    if isinstance(val, dict):          # clés entité = dicts {f1, precision, recall, number}
        entity_metrics[key] = val
        f1  = val.get("f1", 0.0)
        p   = val.get("precision", 0.0)
        r   = val.get("recall", 0.0)
        n   = val.get("number", 0)
        print(f"  {key:<20} F1={f1:.4f}  P={p:.4f}  R={r:.4f}  N={n}")

# Seuil MVP
f1_macro = ft_results["overall_f1"]
threshold = 0.70
status = "✅ SEUIL ATTEINT" if f1_macro >= threshold else "❌ SEUIL NON ATTEINT"
print(f"\nF1 macro = {f1_macro:.4f}  →  {status} (seuil MVP : {threshold})")
print("="*60)

# ---------------------------------------------------------------------------
# Export JSON
# ---------------------------------------------------------------------------
report = {
    "model": str(FINETUNED),
    "test_size": len(test_ds),
    "threshold_mvp": threshold,
    "threshold_reached": f1_macro >= threshold,
    "finetuned": {
        "f1_macro":  ft_results["overall_f1"],
        "precision": ft_results["overall_precision"],
        "recall":    ft_results["overall_recall"],
        "accuracy":  ft_results["overall_accuracy"],
        "per_entity": entity_metrics,
    },
    "baseline": {
        "f1_macro":  base_results["overall_f1"],
        "precision": base_results["overall_precision"],
        "recall":    base_results["overall_recall"],
        "accuracy":  base_results["overall_accuracy"],
    },
}

out_path = OUTPUT_DIR / "eval_results.json"
with open(out_path, "w", encoding="utf-8") as f:
    class NpEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (np.integer,)): return int(obj)
            if isinstance(obj, (np.floating,)): return float(obj)
            if isinstance(obj, (np.bool_,)): return bool(obj)
            return super().default(obj)
    json.dump(report, f, indent=2, ensure_ascii=False, cls=NpEncoder)

print(f"\n[OK] eval_results.json sauvegardé → {out_path}")

# ---------------------------------------------------------------------------
# Illustrations concrètes
# ---------------------------------------------------------------------------
print("\n" + "="*60)
print("ILLUSTRATIONS — Ce que le modèle détecte")
print("="*60)

# Reconstruction des tokens originaux depuis input_ids
def decode_tokens(example):
    return ft_tokenizer.convert_ids_to_tokens(example["input_ids"])

# Bloc 1 — 5 exemples avec entités détectées
print("\n--- Exemples d'extraction (5 phrases) ---")
shown = 0
for i, example in enumerate(test_ds):
    tokens    = decode_tokens(example)
    labels_ex = example["labels"]
    input_ids = torch.tensor([example["input_ids"]]).to(ft_model.device)
    attn_mask = torch.tensor([example["attention_mask"]]).to(ft_model.device)

    with torch.no_grad():
        logits = ft_model(input_ids=input_ids, attention_mask=attn_mask).logits
    preds = torch.argmax(logits, dim=-1)[0].cpu().numpy()

    # Ne montrer que les phrases qui ont au moins une entité réelle
    has_entity = any(id2label.get(int(l), "O") != "O" for l in labels_ex if l != -100)
    if not has_entity:
        continue

    print(f"\n  Phrase #{i}")
    print(f"  {'Token':<20} {'Prédit':<20} {'Réel':<20} {'OK?'}")
    print(f"  {'-'*70}")
    for tok, p, l in zip(tokens, preds, labels_ex):
        if l == -100:
            continue
        pred_lbl = id2label[int(p)]
        true_lbl = id2label[int(l)]
        if pred_lbl == "O" and true_lbl == "O":
            continue   # on n'affiche pas les O/O — trop verbeux
        ok = "✓" if pred_lbl == true_lbl else "✗"
        print(f"  {tok:<20} {pred_lbl:<20} {true_lbl:<20} {ok}")

    shown += 1
    if shown >= 5:
        break

# Bloc 2 — 3 erreurs typiques
print("\n--- Erreurs typiques (3 exemples) ---")
errors_shown = 0
for i, example in enumerate(test_ds):
    tokens    = decode_tokens(example)
    labels_ex = example["labels"]
    input_ids = torch.tensor([example["input_ids"]]).to(ft_model.device)
    attn_mask = torch.tensor([example["attention_mask"]]).to(ft_model.device)

    with torch.no_grad():
        logits = ft_model(input_ids=input_ids, attention_mask=attn_mask).logits
    preds = torch.argmax(logits, dim=-1)[0].cpu().numpy()

    errors = [
        (tok, id2label[int(p)], id2label[int(l)])
        for tok, p, l in zip(tokens, preds, labels_ex)
        if l != -100 and int(p) != int(l) and id2label[int(l)] != "O"
    ]
    if not errors:
        continue

    print(f"\n  Phrase #{i} — {len(errors)} erreur(s)")
    for tok, pred_lbl, true_lbl in errors[:3]:
        print(f"    token='{tok}'  prédit={pred_lbl}  réel={true_lbl}")

    errors_shown += 1
    if errors_shown >= 3:
        break

# Bloc 3 — Distribution entités
print("\n--- Distribution entités (test set) ---")
from collections import Counter
true_counts, pred_counts = Counter(), Counter()

for tl_seq, pl_seq in zip(true_labels, ft_preds):
    for tl in tl_seq:
        if tl != "O":
            true_counts[tl.replace("B-","").replace("I-","")] += 1
    for pl in pl_seq:
        if pl != "O":
            pred_counts[pl.replace("B-","").replace("I-","")] += 1

print(f"  {'Entité':<20} {'Réel':>8} {'Prédit':>8}")
print(f"  {'-'*38}")
all_ents = sorted(set(list(true_counts.keys()) + list(pred_counts.keys())))
for ent in all_ents:
    print(f"  {ent:<20} {true_counts.get(ent,0):>8} {pred_counts.get(ent,0):>8}")
print("="*60)
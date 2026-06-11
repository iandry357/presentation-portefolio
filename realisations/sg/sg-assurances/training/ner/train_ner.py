"""
ner/train_ner.py
Fine-tuning CamemBERT pour NER — 5 entités SG Assurances.
Entrée  : data/ner_datasets/ner_sg_dataset/ + label_map.json
Sortie  : models/ner_sg_assurances/

Lancer depuis training/ :
    python ner/train_ner.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import numpy as np
from pathlib import Path

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
    TrainingArguments,
    Trainer,
    DataCollatorForTokenClassification,
    EarlyStoppingCallback,
)

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------
BASE        = Path(__file__).parent.parent          # training/
DATASET_DIR = BASE / "data" / "ner_datasets" / "ner_sg_dataset"
LABEL_MAP   = BASE / "data" / "ner_datasets" / "label_map.json"
OUTPUT_DIR  = BASE / "models" / "ner_sg_assurances"
RUNS_DIR    = BASE / "runs" / "ner"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MODEL_NAME = "camembert-base"
EPOCHS     = 10
BATCH_SIZE = 16
LR         = 2e-5
WEIGHT_DECAY = 0.01
EARLY_STOPPING_PATIENCE = 3

# ---------------------------------------------------------------------------
# Chargement label map
# ---------------------------------------------------------------------------
with open(LABEL_MAP, "r") as f:
    meta = json.load(f)

label_list = meta["label_list"]
label2id   = meta["label2id"]
id2label   = {int(k): v for k, v in meta["id2label"].items()}
num_labels = len(label_list)

print(f"Labels ({num_labels}) : {label_list}")

# ---------------------------------------------------------------------------
# Chargement dataset
# ---------------------------------------------------------------------------
print(f"\nChargement dataset depuis {DATASET_DIR} ...")
dataset = load_from_disk(str(DATASET_DIR))
print(f"  train      : {len(dataset['train'])} exemples")
print(f"  validation : {len(dataset['validation'])} exemples")
print(f"  test       : {len(dataset['test'])} exemples")

# ---------------------------------------------------------------------------
# Modèle + Tokenizer
# ---------------------------------------------------------------------------
print(f"\nChargement modèle : {MODEL_NAME}")
tokenizer = CamembertTokenizerFast.from_pretrained(MODEL_NAME)
model = CamembertForTokenClassification.from_pretrained(
    MODEL_NAME,
    num_labels=num_labels,
    id2label=id2label,
    label2id=label2id,
)

# ---------------------------------------------------------------------------
# Data collator — padding dynamique au batch
# ---------------------------------------------------------------------------
data_collator = DataCollatorForTokenClassification(
    tokenizer=tokenizer,
    padding=True,
    label_pad_token_id=-100,
)

# ---------------------------------------------------------------------------
# Métriques — seqeval F1 macro
# ---------------------------------------------------------------------------
seqeval = hf_evaluate.load("seqeval")

def compute_metrics(eval_preds):
    logits, labels = eval_preds
    predictions = np.argmax(logits, axis=-1)

    true_labels, true_preds = [], []
    for pred_seq, label_seq in zip(predictions, labels):
        true_label_row, true_pred_row = [], []
        for p, l in zip(pred_seq, label_seq):
            if l == -100:
                continue
            true_label_row.append(id2label[l])
            true_pred_row.append(id2label[p])
        true_labels.append(true_label_row)
        true_preds.append(true_pred_row)

    results = seqeval.compute(
        predictions=true_preds,
        references=true_labels,
        zero_division=0,
    )
    return {
        "f1_macro":  results["overall_f1"],
        "precision": results["overall_precision"],
        "recall":    results["overall_recall"],
        "accuracy":  results["overall_accuracy"],
    }

# ---------------------------------------------------------------------------
# Training arguments
# ---------------------------------------------------------------------------
training_args = TrainingArguments(
    output_dir=str(RUNS_DIR),
    num_train_epochs=EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    per_device_eval_batch_size=BATCH_SIZE,
    learning_rate=LR,
    weight_decay=WEIGHT_DECAY,
    eval_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="f1_macro",
    greater_is_better=True,
    logging_dir=str(RUNS_DIR / "logs"),
    logging_steps=50,
    fp16=True,                          # RTX 5060 — mixed precision
    report_to="none",
    save_total_limit=2,
)

# ---------------------------------------------------------------------------
# Trainer
# ---------------------------------------------------------------------------
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset["train"],
    eval_dataset=dataset["validation"],
    tokenizer=tokenizer,
    data_collator=data_collator,
    compute_metrics=compute_metrics,
    callbacks=[EarlyStoppingCallback(early_stopping_patience=EARLY_STOPPING_PATIENCE)],
)

# ---------------------------------------------------------------------------
# Entraînement
# ---------------------------------------------------------------------------
print("\n=== Début entraînement ===")
train_result = trainer.train()

print(f"\nMeilleur F1 macro validation : {trainer.state.best_metric:.4f}")

# ---------------------------------------------------------------------------
# Export modèle final
# ---------------------------------------------------------------------------
print(f"\nExport modèle → {OUTPUT_DIR}")
trainer.save_model(str(OUTPUT_DIR))
tokenizer.save_pretrained(str(OUTPUT_DIR))

# Sauvegarde métriques + config entraînement
train_metrics = train_result.metrics
train_metrics["best_f1_macro"] = trainer.state.best_metric
with open(OUTPUT_DIR / "training_results.json", "w") as f:
    json.dump(train_metrics, f, indent=2)

print(f"[OK] Modèle sauvegardé → {OUTPUT_DIR}")
print(f"[OK] training_results.json sauvegardé")
print("\n=== Entraînement terminé ===")
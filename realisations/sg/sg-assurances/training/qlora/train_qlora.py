"""
qlora/train_qlora.py
Fine-tuning QLoRA 4-bit de Qwen2.5-1.5B-Instruct sur les paires QA SG Assurances.
Entrée  : data/qlora_datasets/qlora_train.jsonl + qlora_val.jsonl
Sortie  : models/qlora/qlora_sg_assurances/ (adapters LoRA uniquement)

Lancer depuis training/ :
    python qlora/train_qlora.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------
BASE_DIR   = Path(__file__).resolve().parent.parent          # training/
TRAIN_FILE = BASE_DIR / "data" / "qlora_datasets" / "qlora_train.jsonl"
VAL_FILE   = BASE_DIR / "data" / "qlora_datasets" / "qlora_val.jsonl"
OUTPUT_DIR = BASE_DIR / "models" / "qlora" / "qlora_sg_assurances"
LOGS_DIR   = BASE_DIR / "runs" / "qlora"

# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------
MODEL_ID    = "Qwen/Qwen2.5-1.5B-Instruct"

# QLoRA
LORA_R          = 32
LORA_ALPHA      = 64
LORA_DROPOUT    = 0.05
LORA_TARGETS    = ["q_proj", "k_proj", "v_proj", "o_proj",
                   "gate_proj", "up_proj", "down_proj"]

# Training
EPOCHS          = 5
BATCH_SIZE      = 4
GRAD_ACCUM      = 8       # batch effectif = 16
LEARNING_RATE   = 3e-4
MAX_LENGTH      = 512
WARMUP_RATIO    = 0.1


# ---------------------------------------------------------------------------
# Chargement dataset pré-tokenisé
# ---------------------------------------------------------------------------
def load_datasets():
    print("[1/5] Chargement datasets ...")
    ds = load_dataset(
        "json",
        data_files={
            "train": str(TRAIN_FILE),
            "validation": str(VAL_FILE),
        }
    )
    # Cast en tenseurs int (stockés comme listes dans le JSONL)
    ds = ds.with_format("torch")
    print(f"  Train : {len(ds['train'])} exemples")
    print(f"  Val   : {len(ds['validation'])} exemples")
    return ds["train"], ds["validation"]


# ---------------------------------------------------------------------------
# Quantification 4-bit
# ---------------------------------------------------------------------------
def get_bnb_config() -> BitsAndBytesConfig:
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )


# ---------------------------------------------------------------------------
# Chargement modèle + tokenizer
# ---------------------------------------------------------------------------
def load_model_and_tokenizer():
    print(f"[2/5] Chargement modèle {MODEL_ID} (4-bit) ...")
    bnb_config = get_bnb_config()

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=torch.bfloat16,
        trust_remote_code=True,
    )
    model.config.use_cache = False          # désactivé pendant le training
    model.config.pretraining_tp = 1

    print(f"  Mémoire GPU après chargement : "
          f"{torch.cuda.memory_allocated() / 1e9:.2f} Go")
    return model, tokenizer


# ---------------------------------------------------------------------------
# Configuration LoRA
# ---------------------------------------------------------------------------
def apply_lora(model):
    print("[3/5] Application QLoRA ...")
    model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=LORA_TARGETS,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    return model


# ---------------------------------------------------------------------------
# Entraînement
# ---------------------------------------------------------------------------
def train(model, tokenizer, ds_train, ds_val):
    print("[4/5] Entraînement ...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    training_args = SFTConfig(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LEARNING_RATE,
        lr_scheduler_type="cosine",
        warmup_ratio=WARMUP_RATIO,
        bf16=True,
        logging_dir=str(LOGS_DIR),
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=1,             # garder uniquement le meilleur checkpoint
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        report_to="none",               # pas de wandb/tensorboard
        dataset_kwargs={"skip_prepare_dataset": True},
        dataloader_num_workers=0,       # Windows — évite les erreurs multiprocess
        gradient_checkpointing=True,
        optim="paged_adamw_8bit",
        group_by_length=True,
        neftune_noise_alpha=5,
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=ds_train,
        eval_dataset=ds_val,
        processing_class=tokenizer,
    )

    result = trainer.train()
    return trainer, result


# ---------------------------------------------------------------------------
# Sauvegarde adapters LoRA
# ---------------------------------------------------------------------------
def save_adapters(trainer, result):
    print("[5/5] Sauvegarde adapters LoRA ...")
    trainer.model.save_pretrained(str(OUTPUT_DIR))
    trainer.processing_class.save_pretrained(str(OUTPUT_DIR))

    # Métriques
    metrics = {
        "train_loss":    round(result.training_loss, 4),
        "train_runtime": round(result.metrics.get("train_runtime", 0), 1),
        "epochs":        EPOCHS,
        "lora_r":        LORA_R,
        "lora_alpha":    LORA_ALPHA,
        "model_id":      MODEL_ID,
    }
    metrics_path = OUTPUT_DIR / "train_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"  ✅ Adapters sauvegardés → {OUTPUT_DIR}")
    print(f"  ✅ Métriques            → {metrics_path}")
    return metrics


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("QLoRA Training — Qwen2.5-1.5B SG Assurances")
    print("=" * 60)

    ds_train, ds_val     = load_datasets()
    model, tokenizer     = load_model_and_tokenizer()
    model                = apply_lora(model)
    trainer, result      = train(model, tokenizer, ds_train, ds_val)
    metrics              = save_adapters(trainer, result)

    print("\n" + "=" * 60)
    print("RÉCAP TRAINING")
    print(f"  Train loss     : {metrics['train_loss']}")
    print(f"  Durée          : {metrics['train_runtime']}s")
    print(f"  Adapters       : {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
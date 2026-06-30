"""
finetune.py
-----------
Fine-tuning QLoRA de Mistral 7B Instruct sur le dataset drug discovery Sanofi.

Étapes :
    1. Charge dataset_train.jsonl + dataset_eval.jsonl
    2. Charge Mistral 7B Instruct en 4-bit (nf4)
    3. Configure QLoRA (r=32, lora_alpha=64, NEFTune noise_alpha=5)
    4. Entraînement SFTTrainer — 5 epochs
    5. Évalue eval_loss + perplexité à chaque epoch
    6. Sauvegarde meilleur checkpoint → models/lora/

Usage :
    python finetune.py                        # run standard
    python finetune.py --search-hyperparams   # grille hyperparamètres avant run complet

Prérequis :
    - RTX 5060 8GB VRAM
    - torch nightly cu128 installé via constraints.txt
    - data/dataset_train.jsonl + data/dataset_eval.jsonl générés par prepare_dataset.py
"""

import argparse
import json
import math
import re
import time
from pathlib import Path

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from trl import SFTTrainer, SFTConfig

# ---------------------------------------------------------------------------
# PARAMÈTRES CONFIGURABLES
# ---------------------------------------------------------------------------

DATA_DIR        = Path(__file__).parent / "data"
MODELS_DIR      = Path(__file__).parent / "models"
TRAIN_FILE      = DATA_DIR / "dataset_train.jsonl"
EVAL_FILE       = DATA_DIR / "dataset_eval.jsonl"
LORA_OUTPUT_DIR = MODELS_DIR / "lora"
HPARAM_LOG      = MODELS_DIR / "hparam_search.json"

BASE_MODEL      = "mistralai/Mistral-7B-Instruct-v0.3"
# BASE_MODEL = "mistralai/Ministral-3B-instruct-2410"
# BASE_MODEL = "mistralai/Ministral-3B-Instruct-2410"
# BASE_MODEL = "mistralai/Ministral-3-3B-Instruct-2512"
# BASE_MODEL = "google/gemma-2-2b-it"
MAX_SEQ_LENGTH  = 800

# Hyperparamètres par défaut
DEFAULT_LORA_R          = 32
DEFAULT_LORA_ALPHA      = 64
DEFAULT_LEARNING_RATE   = 2e-4
DEFAULT_EPOCHS          = 3
DEFAULT_BATCH_SIZE      = 4
DEFAULT_GRAD_ACCUM      = 4
NEFTUNE_NOISE_ALPHA     = 5

# Grille hyperparamètres
HPARAM_GRID = {
    "r":             [16, 32, 64],
    "lora_alpha":    [32, 64],
    "learning_rate": [1e-4, 2e-4],
}

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _log(msg: str):
    print(f"[FINETUNE] {msg}", flush=True)


def _load_datasets():
    """Charge train + eval depuis jsonl."""
    train_ds = load_dataset("json", data_files=str(TRAIN_FILE), split="train")
    eval_ds  = load_dataset("json", data_files=str(EVAL_FILE),  split="train")
    _log(f"Dataset — train: {len(train_ds)} / eval: {len(eval_ds)}")
    return train_ds, eval_ds


def _load_model_and_tokenizer():
    """Charge Mistral 7B en 4-bit nf4."""
    _log(f"Chargement {BASE_MODEL} en 4-bit nf4...")

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(

    # model = Mistral3ForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    _log("Modèle chargé.")
    return model, tokenizer


def _build_lora_config(r: int, lora_alpha: int) -> LoraConfig:
    return LoraConfig(
        r=r,
        lora_alpha=lora_alpha,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )


def _build_training_args(
    output_dir: Path,
    epochs: int,
    learning_rate: float,
    run_name: str = "mistral7b-drug",
) -> SFTConfig:
    return SFTConfig(
        output_dir=str(output_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=DEFAULT_BATCH_SIZE,
        per_device_eval_batch_size=DEFAULT_BATCH_SIZE,
        gradient_accumulation_steps=DEFAULT_GRAD_ACCUM,
        learning_rate=learning_rate,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        fp16=True,
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        neftune_noise_alpha=NEFTUNE_NOISE_ALPHA,
        max_seq_length=MAX_SEQ_LENGTH,
        dataset_text_field="text",
        report_to="none",
        run_name=run_name,
    )


def _compute_perplexity(eval_loss: float) -> float:
    return round(math.exp(eval_loss), 4)

def _save_checkpoints_history(trainer, output_dir: Path, base_model: str, run_name: str):
    """
    Extrait l'historique eval par epoch depuis trainer.state.log_history,
    l'associe aux dossiers checkpoint-XXX réellement présents sur disque,
    et écrit le résultat dans models/checkpoints_history.json.
    """
    eval_entries = [
        entry for entry in trainer.state.log_history
        if "eval_loss" in entry
    ]
    eval_entries.sort(key=lambda e: e["epoch"])

    checkpoint_dirs = sorted(
        [d for d in output_dir.iterdir() if d.is_dir() and re.match(r"^checkpoint-\d+$", d.name)],
        key=lambda d: int(d.name.split("-")[1]),
    )

    if len(checkpoint_dirs) != len(eval_entries):
        _log(
            f"ATTENTION — {len(checkpoint_dirs)} dossiers checkpoint trouvés "
            f"mais {len(eval_entries)} entrées eval dans log_history. "
            "Le mapping epoch -> checkpoint peut être incorrect."
        )

    checkpoints = []
    for entry, ckpt_dir in zip(eval_entries, checkpoint_dirs):
        checkpoints.append({
            "epoch": entry["epoch"],
            "checkpoint": ckpt_dir.name,
            "eval_loss": entry["eval_loss"],
            "perplexity": _compute_perplexity(entry["eval_loss"]),
            "eval_mean_token_accuracy": entry.get("eval_mean_token_accuracy"),
            "eval_runtime": entry.get("eval_runtime"),
        })

    history = {
        "run_name": run_name,
        "base_model": base_model,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "checkpoints": checkpoints,
    }

    history_path = MODELS_DIR / "checkpoints_history.json"
    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)

    _log(f"Historique checkpoints → {history_path}")

# ---------------------------------------------------------------------------
# HYPERPARAMETER SEARCH
# ---------------------------------------------------------------------------

def run_hparam_search(train_ds, eval_ds) -> dict:
    """
    Grille hyperparamètres — 1 epoch par combinaison.
    Retourne les meilleurs hyperparamètres selon eval_loss.
    """
    _log("=== Hyperparameter Search ===")

    model, tokenizer = _load_model_and_tokenizer()
    results = []
    best = {"eval_loss": float("inf"), "r": DEFAULT_LORA_R, "lora_alpha": DEFAULT_LORA_ALPHA, "learning_rate": DEFAULT_LEARNING_RATE}

    for r in HPARAM_GRID["r"]:
        for lora_alpha in HPARAM_GRID["lora_alpha"]:
            for lr in HPARAM_GRID["learning_rate"]:
                run_name = f"hparam_r{r}_alpha{lora_alpha}_lr{lr}"
                _log(f"Run : {run_name}")

                lora_config = _build_lora_config(r, lora_alpha)
                peft_model  = get_peft_model(model, lora_config)

                training_args = _build_training_args(
                    output_dir=MODELS_DIR / "hparam_runs" / run_name,
                    epochs=1,
                    learning_rate=lr,
                    run_name=run_name,
                )

                trainer = SFTTrainer(
                    model=peft_model,
                    args=training_args,
                    train_dataset=train_ds,
                    eval_dataset=eval_ds,
                    processing_class=tokenizer,
                )

                trainer.train()
                metrics = trainer.evaluate()
                eval_loss = metrics.get("eval_loss", float("inf"))
                perplexity = _compute_perplexity(eval_loss)

                result = {
                    "run": run_name,
                    "r": r,
                    "lora_alpha": lora_alpha,
                    "learning_rate": lr,
                    "eval_loss": round(eval_loss, 4),
                    "perplexity": perplexity,
                }
                results.append(result)
                _log(f"  eval_loss={eval_loss:.4f} | perplexity={perplexity}")

                if eval_loss < best["eval_loss"]:
                    best = {
                        "eval_loss": eval_loss,
                        "r": r,
                        "lora_alpha": lora_alpha,
                        "learning_rate": lr,
                    }

                # Reset LoRA adapters pour le prochain run
                for name, param in peft_model.named_parameters():
                    if "lora" in name:
                        param.data = torch.zeros_like(param.data)

    # Sauvegarde résultats
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(HPARAM_LOG, "w") as f:
        json.dump({"results": results, "best": best}, f, indent=2)

    _log(f"Meilleurs hyperparamètres : r={best['r']}, lora_alpha={best['lora_alpha']}, lr={best['learning_rate']}")
    _log(f"Résultats sauvegardés → {HPARAM_LOG}")

    return best


# ---------------------------------------------------------------------------
# RUN PRINCIPAL
# ---------------------------------------------------------------------------

def run_finetune(
    r: int = DEFAULT_LORA_R,
    lora_alpha: int = DEFAULT_LORA_ALPHA,
    learning_rate: float = DEFAULT_LEARNING_RATE,
):
    """Run complet — 5 epochs avec les hyperparamètres donnés."""
    _log("=== Fine-tuning Mistral 7B Instruct — Drug Discovery ===")
    _log(f"Hyperparamètres : r={r}, lora_alpha={lora_alpha}, lr={learning_rate}")
    start = time.time()

    train_ds, eval_ds = _load_datasets()
    model, tokenizer  = _load_model_and_tokenizer()

    lora_config   = _build_lora_config(r, lora_alpha)
    peft_model    = get_peft_model(model, lora_config)
    peft_model.print_trainable_parameters()

    LORA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    training_args = _build_training_args(
        output_dir=LORA_OUTPUT_DIR,
        epochs=DEFAULT_EPOCHS,
        learning_rate=learning_rate,
        run_name="mistral7b-drug-discovery",
    )

    trainer = SFTTrainer(
        model=peft_model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        processing_class=tokenizer,
    )

    trainer.train()

    # Traçabilité des checkpoints par epoch (pour sélection ultérieure par export_gguf.py)
    _save_checkpoints_history(
        trainer=trainer,
        output_dir=LORA_OUTPUT_DIR,
        base_model=BASE_MODEL,
        run_name="mistral7b-drug-discovery",
    )

    # Évaluation finale
    metrics = trainer.evaluate()
    eval_loss  = metrics.get("eval_loss", 0)
    perplexity = _compute_perplexity(eval_loss)

    elapsed = time.time() - start
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    # Sauvegarde métriques finales
    final_metrics = {
        "base_model":   BASE_MODEL,
        "r":            r,
        "lora_alpha":   lora_alpha,
        "learning_rate": learning_rate,
        "epochs":       DEFAULT_EPOCHS,
        "eval_loss":    round(eval_loss, 4),
        "perplexity":   perplexity,
        "training_time_minutes": round(elapsed / 60, 1),
    }
    metrics_path = MODELS_DIR / "finetune_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(final_metrics, f, indent=2)

    _log(f"eval_loss  : {eval_loss:.4f}")
    _log(f"perplexité : {perplexity}")
    _log(f"Durée      : {minutes}m {seconds}s")
    _log(f"Adaptateurs LoRA → {LORA_OUTPUT_DIR}")
    _log(f"Métriques  → {metrics_path}")
    _log("=== Fine-tuning terminé ===")


# ---------------------------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fine-tuning QLoRA Mistral 7B — Drug Discovery")
    parser.add_argument(
        "--search-hyperparams",
        action="store_true",
        help="Lancer la grille hyperparamètres avant le run complet",
    )
    args = parser.parse_args()

    # Vérification datasets
    if not TRAIN_FILE.exists() or not EVAL_FILE.exists():
        raise FileNotFoundError(
            "Datasets introuvables — lancer prepare_dataset.py d'abord.\n"
            f"  Train : {TRAIN_FILE}\n"
            f"  Eval  : {EVAL_FILE}"
        )

    train_ds, eval_ds = _load_datasets()

    if args.search_hyperparams:
        best = run_hparam_search(train_ds, eval_ds)
        run_finetune(
            r=best["r"],
            lora_alpha=best["lora_alpha"],
            learning_rate=best["learning_rate"],
        )
    else:
        run_finetune()


if __name__ == "__main__":
    main()
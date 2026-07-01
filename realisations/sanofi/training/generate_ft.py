"""
generate_ft.py
--------------
Subprocess autonome — génère les réponses du modèle FINE-TUNÉ.
Chargement Mistral 7B 4-bit nf4 + adaptateurs LoRA (meilleur checkpoint).
Écrit les réponses dans models/eval_ft_responses.json.

Lancé automatiquement par evaluate.py — ne pas lancer directement.
"""

import json
import sys
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

# ---------------------------------------------------------------------------
# PARAMÈTRES (synchronisés avec evaluate.py)
# ---------------------------------------------------------------------------

MODELS_DIR              = Path(__file__).parent / "models"
LORA_DIR                = MODELS_DIR / "lora"
CHECKPOINTS_HISTORY     = MODELS_DIR / "checkpoints_history.json"
OUTPUT_FILE             = MODELS_DIR / "eval_ft_responses.json"
QUESTIONS_FILE          = MODELS_DIR / "eval_questions.json"

BASE_MODEL              = "mistralai/Mistral-7B-Instruct-v0.3"
MAX_NEW_TOKENS          = 300
TEMPERATURE             = 0.3


def _log(msg: str):
    print(f"[GEN_FT] {msg}", flush=True)


def _get_bnb_config() -> BitsAndBytesConfig:
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )


def _build_prompt(question: str) -> str:
    return f"[INST] {question} [/INST]"


def _select_best_checkpoint() -> Path:
    """Sélectionne le meilleur checkpoint depuis checkpoints_history.json."""
    if not CHECKPOINTS_HISTORY.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {CHECKPOINTS_HISTORY}\n"
            "Lancer finetune.py d'abord."
        )
    with open(CHECKPOINTS_HISTORY) as f:
        history = json.load(f)

    checkpoints = history.get("checkpoints", [])
    if not checkpoints:
        raise ValueError(f"Aucun checkpoint dans {CHECKPOINTS_HISTORY}")

    ranked = sorted(
        checkpoints,
        key=lambda c: c["eval_mean_token_accuracy"],
        reverse=True,
    )
    best = ranked[0]
    checkpoint_path = LORA_DIR / best["checkpoint"]

    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint introuvable : {checkpoint_path}")

    _log(f"Meilleur checkpoint : {best['checkpoint']} "
         f"(accuracy={best['eval_mean_token_accuracy']:.4f})")
    return checkpoint_path


def _generate_response(prompt: str, model, tokenizer) -> str:
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            temperature=TEMPERATURE,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )
    generated = outputs[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(generated, skip_special_tokens=True).strip()


def main():
    _log("=== Génération réponses FINE-TUNÉ ===")

    # Charger les questions
    if not QUESTIONS_FILE.exists():
        _log(f"ERREUR : fichier questions introuvable : {QUESTIONS_FILE}")
        sys.exit(1)

    with open(QUESTIONS_FILE, encoding="utf-8") as f:
        questions = json.load(f)

    _log(f"Questions : {len(questions)}")

    # Sélection checkpoint
    best_checkpoint = _select_best_checkpoint()

    # Chargement tokenizer
    _log(f"Chargement tokenizer {BASE_MODEL}...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token

    # Chargement modèle BASE en 4-bit puis PEFT
    _log("Chargement modèle FINE-TUNÉ en 4-bit + LoRA...")
    bnb_config = _get_bnb_config()
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(model, str(best_checkpoint))
    model.eval()
    _log("Modèle FINE-TUNÉ chargé.")

    # Génération
    responses = []
    for i, q in enumerate(questions):
        prompt = _build_prompt(q["question"])
        resp   = _generate_response(prompt, model, tokenizer)
        responses.append(resp)
        _log(f"  [{i+1}/{len(questions)}] {q['id']} : {resp[:80]}...")

    # Sauvegarde
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(responses, f, indent=2, ensure_ascii=False)

    _log(f"Réponses FINE-TUNÉ sauvegardées → {OUTPUT_FILE}")
    _log("=== Génération FINE-TUNÉ terminée ===")


if __name__ == "__main__":
    main()
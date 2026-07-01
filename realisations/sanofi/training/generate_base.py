"""
generate_base.py
----------------
Subprocess autonome — génère les réponses du modèle BASE Mistral 7B Instruct v0.3.
Chargement 4-bit nf4 sur GPU (RTX 5060).
Écrit les réponses dans models/eval_base_responses.json.

Lancé automatiquement par evaluate.py — ne pas lancer directement.
"""

import json
import sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

# ---------------------------------------------------------------------------
# PARAMÈTRES (synchronisés avec evaluate.py)
# ---------------------------------------------------------------------------

MODELS_DIR          = Path(__file__).parent / "models"
OUTPUT_FILE         = MODELS_DIR / "eval_base_responses.json"
QUESTIONS_FILE      = MODELS_DIR / "eval_questions.json"

BASE_MODEL          = "mistralai/Mistral-7B-Instruct-v0.3"
MAX_NEW_TOKENS      = 300
TEMPERATURE         = 0.3


def _log(msg: str):
    print(f"[GEN_BASE] {msg}", flush=True)


def _get_bnb_config() -> BitsAndBytesConfig:
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )


def _build_prompt(question: str) -> str:
    return f"[INST] {question} [/INST]"


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
    _log("=== Génération réponses BASE ===")

    # Charger les questions depuis le fichier partagé
    if not QUESTIONS_FILE.exists():
        _log(f"ERREUR : fichier questions introuvable : {QUESTIONS_FILE}")
        sys.exit(1)

    with open(QUESTIONS_FILE, encoding="utf-8") as f:
        questions = json.load(f)

    _log(f"Questions : {len(questions)}")

    # Chargement tokenizer
    _log(f"Chargement tokenizer {BASE_MODEL}...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token

    # Chargement modèle BASE en 4-bit sur GPU
    _log(f"Chargement modèle BASE en 4-bit...")
    bnb_config = _get_bnb_config()
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()
    _log("Modèle BASE chargé.")

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

    _log(f"Réponses BASE sauvegardées → {OUTPUT_FILE}")
    _log("=== Génération BASE terminée ===")


if __name__ == "__main__":
    main()
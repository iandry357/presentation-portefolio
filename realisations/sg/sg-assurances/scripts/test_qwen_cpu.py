"""
Test CPU — Qwen2.5-1.5B fine-tuné (sans quantification)
Valide le chargement base + adapters LoRA et la génération.
Lancé en CPU pour contourner l'incompatibilité GPU sm_120.

Usage :
    python test_qwen_cpu.py
"""

from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

# ─────────────────────────────────────────
# Chemins locaux
# ─────────────────────────────────────────
BASE_PATH = Path(__file__).parent / "models" / "qwen-base"
FT_PATH   = Path(__file__).parent / "models" / "qlora" / "qlora_sg_assurances"

PROMPT = "Qu'est-ce qu'un contrat d'assurance vie ?"
MAX_NEW_TOKENS = 100


def main():
    print(f"[test] Device : CPU")
    print(f"[test] Base   : {BASE_PATH}")
    print(f"[test] Adapters : {FT_PATH}\n")

    # Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(BASE_PATH), trust_remote_code=True)
    print("[test] Tokenizer chargé")

    # Base model — float32 CPU, pas de quantification
    print("[test] Chargement base model (CPU, float32)...")
    base = AutoModelForCausalLM.from_pretrained(
        str(BASE_PATH),
        torch_dtype=torch.float32,
        device_map="cpu",
        trust_remote_code=True,
    )

    # Adapters LoRA
    print("[test] Application adapters LoRA...")
    model = PeftModel.from_pretrained(base, str(FT_PATH))
    model.eval()
    print("[test] Modèle prêt\n")

    # Génération
    messages = [{"role": "user", "content": PROMPT}]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(text, return_tensors="pt")

    print(f"[test] Prompt : {PROMPT}")
    print("[test] Génération en cours...\n")

    with torch.no_grad():
        generated = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )

    input_len  = inputs["input_ids"].shape[1]
    new_tokens = generated[0][input_len:]
    response   = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

    print("=" * 60)
    print("RÉPONSE :")
    print(response)
    print("=" * 60)


if __name__ == "__main__":
    main()
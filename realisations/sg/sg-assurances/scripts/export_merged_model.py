"""
Export modèle Qwen2.5-1.5B mergé (base + adapters LoRA)
Lancer depuis scripts/ dans venv-sg-training

Output : training/models/qwen_sg_merged/
"""

import logging
import sys
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# Chemins
# ─────────────────────────────────────────
BASE_DIR     = Path(__file__).parent.parent / "training" / "models"
BASE_PATH    = BASE_DIR / "qwen-base"
ADAPTERS_PATH = BASE_DIR / "qlora" / "qlora_sg_assurances"
OUTPUT_PATH  = BASE_DIR / "qwen_sg_merged"

# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────
def main():
    logger.info(f"[export] Base model    : {BASE_PATH}")
    logger.info(f"[export] Adapters LoRA : {ADAPTERS_PATH}")
    logger.info(f"[export] Output        : {OUTPUT_PATH}")

    if not BASE_PATH.exists():
        logger.error(f"[export] Base model introuvable : {BASE_PATH}")
        sys.exit(1)

    if not ADAPTERS_PATH.exists():
        logger.error(f"[export] Adapters introuvables : {ADAPTERS_PATH}")
        sys.exit(1)

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    logger.info("[export] Chargement tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(str(BASE_PATH), trust_remote_code=True)

    logger.info("[export] Chargement base model (float32)...")
    base = AutoModelForCausalLM.from_pretrained(
        str(BASE_PATH),
        torch_dtype=torch.float32,
        trust_remote_code=True,
    )

    logger.info("[export] Chargement adapters LoRA...")
    model = PeftModel.from_pretrained(base, str(ADAPTERS_PATH))

    logger.info("[export] Merge adapters...")
    model = model.merge_and_unload()
    model.eval()

    logger.info(f"[export] Sauvegarde → {OUTPUT_PATH}")
    model.save_pretrained(str(OUTPUT_PATH))
    tokenizer.save_pretrained(str(OUTPUT_PATH))

    logger.info("[export] Export terminé ✅")


if __name__ == "__main__":
    main()
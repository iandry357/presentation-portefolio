import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import random
from pathlib import Path
from datasets import Dataset
from transformers import AutoTokenizer
import shutil

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------
BASE_DIR     = Path(__file__).resolve().parent.parent          # training/
QA_FILE      = BASE_DIR / "data" / "qa_pairs" / "qa_pairs.jsonl"
OUTPUT_DIR   = BASE_DIR / "data" / "qlora_datasets"
OUT_TRAIN    = OUTPUT_DIR / "qlora_train.jsonl"
OUT_VAL      = OUTPUT_DIR / "qlora_val.jsonl"

# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------
MODEL_ID     = "Qwen/Qwen2.5-1.5B-Instruct"
MAX_LENGTH   = 512
VAL_RATIO    = 0.10
MIN_OUTPUT   = 10      # caractères minimum pour output valide
SEED         = 42

SYSTEM_PROMPT = (
    "Tu es un expert en assurance chez Société Générale Assurances. "
    "Réponds de manière précise et concise aux questions sur les contrats, "
    "garanties, sinistres et conditions générales."
)

# ---------------------------------------------------------------------------
# Chargement et validation des paires QA
# ---------------------------------------------------------------------------
def load_qa_pairs(path: Path) -> list[dict]:
    pairs = []
    skipped = 0
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                print(f"  [WARN] Ligne {i} ignorée — JSON invalide")
                skipped += 1
                continue

            instruction = obj.get("instruction", "").strip()
            output      = obj.get("output", "").strip()

            if not instruction or len(output) < MIN_OUTPUT:
                skipped += 1
                continue

            pairs.append({"instruction": instruction, "output": output})

    print(f"  Paires chargées   : {len(pairs)}")
    print(f"  Paires ignorées   : {skipped}")
    return pairs


# ---------------------------------------------------------------------------
# Formatage prompt chat Qwen (apply_chat_template)
# ---------------------------------------------------------------------------
def format_chat(pair: dict, tokenizer: AutoTokenizer) -> list[dict]:
    messages = [
        {"role": "system",    "content": SYSTEM_PROMPT},
        {"role": "user",      "content": pair["instruction"]},
        {"role": "assistant", "content": pair["output"]},
    ]
    return messages


# ---------------------------------------------------------------------------
# Tokenisation avec masquage des labels system+user
# ---------------------------------------------------------------------------
def tokenize_and_mask(messages: list[dict], tokenizer: AutoTokenizer) -> dict:
    # Prompt complet (system + user + assistant)
    full_text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False
    )

    # Prompt tronqué sans la réponse assistant (pour calculer la longueur à masquer)
    prompt_only = tokenizer.apply_chat_template(
        messages[:-1],                  # system + user uniquement
        tokenize=False,
        add_generation_prompt=True      # ajoute <|im_start|>assistant\n
    )

    full_enc   = tokenizer(full_text,   truncation=True, max_length=MAX_LENGTH)
    prompt_enc = tokenizer(prompt_only, truncation=False)

    input_ids  = full_enc["input_ids"]
    prompt_len = len(prompt_enc["input_ids"])

    # Labels : -100 sur tout le préfixe system+user, valeur réelle sur assistant
    labels = [-100] * prompt_len + input_ids[prompt_len:]

    # Alignement si truncation a raccourci input_ids
    if len(labels) > len(input_ids):
        labels = labels[:len(input_ids)]

    return {
        "input_ids":      input_ids,
        "attention_mask": full_enc["attention_mask"],
        "labels":         labels,
    }


# ---------------------------------------------------------------------------
# Split train / val
# ---------------------------------------------------------------------------
def split(pairs: list[dict], val_ratio: float, seed: int):
    random.seed(seed)
    shuffled = pairs[:]
    random.shuffle(shuffled)
    cut = max(1, int(len(shuffled) * val_ratio))
    return shuffled[cut:], shuffled[:cut]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("QLoRA Dataset — préparation paires QA SG Assurances")
    print("=" * 60)

    # 1. Chargement
    print("\n[1/5] Chargement qa_pairs.jsonl ...")
    pairs = load_qa_pairs(QA_FILE)

    # 2. Split
    print("\n[2/5] Split train / val ...")
    train_pairs, val_pairs = split(pairs, VAL_RATIO, SEED)
    print(f"  Train : {len(train_pairs)} paires")
    print(f"  Val   : {len(val_pairs)} paires")

    # 3. Tokenizer
    print(f"\n[3/5] Chargement tokenizer {MODEL_ID} ...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 4. Tokenisation
    print("\n[4/5] Tokenisation + masquage labels ...")

    def process(pairs_list: list[dict]) -> Dataset:
        records = []
        token_lengths = []
        for p in pairs_list:
            msgs = format_chat(p, tokenizer)
            enc  = tokenize_and_mask(msgs, tokenizer)
            records.append(enc)
            token_lengths.append(len(enc["input_ids"]))
        avg = sum(token_lengths) / len(token_lengths) if token_lengths else 0
        print(f"  Longueur token moyenne : {avg:.0f} tokens")
        return Dataset.from_list(records)

    print("  → Train ...")
    ds_train = process(train_pairs)
    print("  → Val ...")
    ds_val   = process(val_pairs)

    # 5. Sauvegarde
    print("\n[5/5] Sauvegarde sur disque ...")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for out_file in [OUT_TRAIN, OUT_VAL]:
        if out_file.exists():
            out_file.unlink()
            print(f"  [RESET] {out_file.name} supprimé")
    ds_train.to_json(str(OUT_TRAIN), orient="records", lines=True)
    ds_val.to_json(str(OUT_VAL), orient="records", lines=True)
    print(f"  ✅ Train sauvegardé → {OUT_TRAIN}")
    print(f"  ✅ Val   sauvegardé → {OUT_VAL}")

    print("\n" + "=" * 60)
    print("RÉCAP")
    print(f"  Paires totales : {len(pairs)}")
    print(f"  Train          : {len(ds_train)}")
    print(f"  Val            : {len(ds_val)}")
    print(f"  MAX_LENGTH     : {MAX_LENGTH} tokens")
    print("=" * 60)


if __name__ == "__main__":
    main()
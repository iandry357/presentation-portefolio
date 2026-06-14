"""
qlora/evaluate.py
Évaluation avant/après fine-tuning QLoRA sur le val set SG Assurances.
  - ROUGE-L        : similarité textuelle base vs fine-tuné
  - LLM-as-judge   : Mistral local (Ollama) juge les réponses côte à côte

Entrée  : data/qlora_datasets/qlora_val.jsonl
          models/qlora/qlora_sg_assurances/ (adapters LoRA)
Sortie  : models/qlora/qlora_eval_results.json

Lancer depuis training/ :
    python qlora/evaluate.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Empêche le shadow du package HuggingFace 'evaluate' par ce fichier
_qlora_dir = os.path.abspath(os.path.dirname(__file__))
if _qlora_dir in sys.path:
    sys.path.remove(_qlora_dir)

import json
import random
import re
import requests
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel
from evaluate import load as load_metric

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------
BASE_DIR      = Path(__file__).resolve().parent.parent
QA_FILE       = BASE_DIR / "data" / "qa_pairs" / "qa_pairs.jsonl"
ADAPTERS_DIR  = BASE_DIR / "models" / "qlora" / "qlora_sg_assurances"
OUTPUT_FILE   = BASE_DIR / "models" / "qlora" / "qlora_eval_results.json"

# ---------------------------------------------------------------------------
# Paramètres
# ---------------------------------------------------------------------------
MODEL_ID        = "Qwen/Qwen2.5-1.5B-Instruct"
MAX_NEW_TOKENS  = 200
TEMPERATURE     = 0.1

# Ollama
OLLAMA_URL      = "http://localhost:11434/api/generate"
OLLAMA_MODEL    = "mistral"

SYSTEM_PROMPT = (
    "Tu es un expert en assurance chez Société Générale Assurances. "
    "Réponds de manière précise et concise aux questions sur les contrats, "
    "garanties, sinistres et conditions générales."
)

JUDGE_PROMPT_TEMPLATE = """Tu es un expert juridique et technique en assurance IARD française, \
spécialisé dans les produits Société Générale Assurances (Sogessur). \
Tu maîtrises parfaitement le Code des assurances français, les Conditions Générales SG, \
les délais de prescription, les garanties habitation/auto/obsèques et la réglementation prudentielle (SFCR).

On te soumet deux réponses à une question sur les assurances SG Assurances.
Évalue laquelle est la plus fidèle aux conditions contractuelles SG, \
la plus précise juridiquement et la plus utile pour un assuré ou un conseiller SG.
Pénalise les réponses vagues, génériques ou qui ne citent pas les éléments contractuels spécifiques SG.

Question : {question}

Réponse A : {response_a}

Réponse B : {response_b}

Réponds UNIQUEMENT en JSON valide avec ce format exact :
{{"verdict": "A" ou "B" ou "egal", "raison": "explication courte en 1-2 phrases"}}"""


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
# Reconstruction val set (même seed que dataset.py)
# ---------------------------------------------------------------------------
def load_val_pairs() -> list[dict]:
    pairs = []
    with open(QA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            instruction = obj.get("instruction", "").strip()
            output      = obj.get("output", "").strip()
            if instruction and len(output) >= 10:
                pairs.append({"instruction": instruction, "output": output})

    random.seed(42)
    shuffled = pairs[:]
    random.shuffle(shuffled)
    cut = max(1, int(len(shuffled) * 0.10))
    val_pairs = shuffled[:cut]
    print(f"  Val set reconstruit : {len(val_pairs)} paires")
    return val_pairs


# ---------------------------------------------------------------------------
# Génération réponse Qwen
# ---------------------------------------------------------------------------
def generate_response(instruction: str, model, tokenizer) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": instruction},
    ]
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
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


# ---------------------------------------------------------------------------
# ROUGE-L
# ---------------------------------------------------------------------------
def compute_rouge(predictions: list[str], references: list[str]) -> dict:
    rouge = load_metric("rouge")
    results = rouge.compute(
        predictions=predictions,
        references=references,
        use_stemmer=False,
    )
    return {k: round(v, 4) for k, v in results.items()}


# ---------------------------------------------------------------------------
# LLM-as-judge via Ollama Mistral
# ---------------------------------------------------------------------------
def judge_with_ollama(question: str, response_a: str, response_b: str) -> dict:
    prompt = JUDGE_PROMPT_TEMPLATE.format(
        question=question,
        response_a=response_a,
        response_b=response_b,
    )
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model":  OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0},
            },
            timeout=60,
        )
        raw = resp.json().get("response", "").strip()

        # Extraire le JSON de la réponse
        match = re.search(r'\{.*?\}', raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            verdict = parsed.get("verdict", "egal").strip().upper()
            raison  = parsed.get("raison", "").strip()
            if verdict not in ("A", "B", "EGAL"):
                verdict = "EGAL"
            return {"verdict": verdict, "raison": raison}

    except Exception as e:
        print(f"    [WARN] Ollama error : {e}")

    return {"verdict": "EGAL", "raison": "Erreur d'évaluation"}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("QLoRA Evaluate — ROUGE + LLM-as-judge SG Assurances")
    print("=" * 60)

    # 1. Val set
    print("\n[1/6] Chargement val set ...")
    val_pairs = load_val_pairs()

    # 2. Tokenizer
    print(f"\n[2/6] Chargement tokenizer {MODEL_ID} ...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb_config = get_bnb_config()

    # 3. Modèle BASE
    print("\n[3/6] Génération réponses — modèle BASE ...")
    model_base = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=torch.bfloat16,
        trust_remote_code=True,
    )
    model_base.eval()

    base_responses = []
    for i, pair in enumerate(val_pairs):
        resp = generate_response(pair["instruction"], model_base, tokenizer)
        base_responses.append(resp)
        print(f"  [{i+1}/{len(val_pairs)}] BASE : {resp[:80]}...")

    del model_base
    torch.cuda.empty_cache()

    # 4. Modèle FINE-TUNÉ
    print("\n[4/6] Génération réponses — modèle FINE-TUNÉ ...")
    model_ft = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=torch.bfloat16,
        trust_remote_code=True,
    )
    model_ft = PeftModel.from_pretrained(model_ft, str(ADAPTERS_DIR))
    model_ft.eval()

    ft_responses = []
    for i, pair in enumerate(val_pairs):
        resp = generate_response(pair["instruction"], model_ft, tokenizer)
        ft_responses.append(resp)
        print(f"  [{i+1}/{len(val_pairs)}] FT   : {resp[:80]}...")

    del model_ft
    torch.cuda.empty_cache()

    # 5. ROUGE
    print("\n[5/6] Calcul métriques ROUGE ...")
    references  = [p["output"] for p in val_pairs]
    rouge_base  = compute_rouge(base_responses, references)
    rouge_ft    = compute_rouge(ft_responses,   references)
    delta_l     = round(rouge_ft["rougeL"] - rouge_base["rougeL"], 4)
    print(f"  ROUGE BASE      : {rouge_base}")
    print(f"  ROUGE FINE-TUNÉ : {rouge_ft}")
    print(f"  Delta ROUGE-L   : {delta_l:+.4f}")

    # 6. LLM-as-judge
    print("\n[6/6] LLM-as-judge (Mistral via Ollama) ...")
    examples   = []
    ft_wins    = 0
    base_wins  = 0
    ties       = 0

    for i, pair in enumerate(val_pairs):
        verdict = judge_with_ollama(
            question=pair["instruction"],
            response_a=base_responses[i],
            response_b=ft_responses[i],
        )
        v = verdict["verdict"]
        if v == "B":
            ft_wins += 1
        elif v == "A":
            base_wins += 1
        else:
            ties += 1

        print(f"  [{i+1}/{len(val_pairs)}] Verdict : {v} — {verdict['raison'][:60]}...")
        examples.append({
            "question":      pair["instruction"],
            "reference":     pair["output"],
            "base":          base_responses[i],
            "finetuned":     ft_responses[i],
            "judge_verdict": v,          # A=base gagne, B=FT gagne, EGAL
            "judge_raison":  verdict["raison"],
        })

    judge_summary = {
        "ft_wins":   ft_wins,
        "base_wins": base_wins,
        "ties":      ties,
        "total":     len(val_pairs),
        "ft_win_rate": round(ft_wins / len(val_pairs), 3),
    }
    print(f"\n  FT gagne    : {ft_wins}/{len(val_pairs)}")
    print(f"  Base gagne  : {base_wins}/{len(val_pairs)}")
    print(f"  Égalité     : {ties}/{len(val_pairs)}")

    # Export
    results = {
        "model_id":        MODEL_ID,
        "adapters":        str(ADAPTERS_DIR),
        "n_examples":      len(val_pairs),
        "rouge_base":      rouge_base,
        "rouge_ft":        rouge_ft,
        "delta_rougeL":    delta_l,
        "rouge_improved":  bool(delta_l > 0),
        "judge_summary":   judge_summary,
        "examples":        examples,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n  ✅ Résultats sauvegardés → {OUTPUT_FILE}")

    print("\n" + "=" * 60)
    print("RÉCAP ÉVALUATION")
    print(f"  ROUGE-L base      : {rouge_base['rougeL']}")
    print(f"  ROUGE-L fine-tuné : {rouge_ft['rougeL']}")
    print(f"  Delta ROUGE-L     : {delta_l:+.4f}")
    print(f"  FT win rate       : {judge_summary['ft_win_rate']*100:.0f}% ({ft_wins}/{len(val_pairs)})")
    print("=" * 60)


if __name__ == "__main__":
    main()
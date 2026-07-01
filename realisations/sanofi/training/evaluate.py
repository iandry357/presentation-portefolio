"""
evaluate.py
-----------
Évaluation win-rate du modèle Mistral 7B fine-tuné vs modèle base.
Pattern : chargement HuggingFace 4-bit + PEFT sur GPU local (RTX 5060).
Juge    : Gemma 3 12B via Ollama local (format JSON verdict + raison).

Étapes :
    1. Sélection automatique du meilleur checkpoint (checkpoints_history.json)
    2. Génération réponses — modèle BASE (Mistral 7B Instruct v0.3, 4-bit)
    3. Génération réponses — modèle FINE-TUNÉ (base + LoRA checkpoint)
    4. Jugement Gemma 3 12B via Ollama — format JSON
    5. Calcul win-rate global + par langue + par type
    6. Sauvegarde → models/eval_results.json

Usage :
    python evaluate.py

Prérequis :
    - RTX 5060 8GB VRAM
    - Ollama local avec gemma3:12b installé
    - training/models/checkpoints_history.json généré par finetune.py
    - training/models/lora/checkpoint-XXX/ présent sur disque
"""

import json
import random
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# PARAMÈTRES CONFIGURABLES
# ---------------------------------------------------------------------------

MODELS_DIR              = Path(__file__).parent / "models"
LORA_DIR                = MODELS_DIR / "lora"
CHECKPOINTS_HISTORY     = MODELS_DIR / "checkpoints_history.json"
EVAL_RESULTS_FILE       = MODELS_DIR / "eval_results.json"

BASE_MODEL              = "mistralai/Mistral-7B-Instruct-v0.3"

OLLAMA_URL              = "http://localhost:11434/api/generate"
OLLAMA_MODEL_JUDGE      = "gemma3:12b"
OLLAMA_TIMEOUT          = 180

MAX_NEW_TOKENS          = 300
TEMPERATURE             = 0.3

# Seuil de succès (win-rate minimum pour valider le fine-tuning)
WIN_RATE_THRESHOLD      = 30.0

# ---------------------------------------------------------------------------
# SÉLECTION AUTOMATIQUE DU MEILLEUR CHECKPOINT
# (logique autonome — pas de dépendance à export_gguf.py)
# ---------------------------------------------------------------------------

def select_best_checkpoint() -> Path:
    """
    Lit checkpoints_history.json et sélectionne le checkpoint
    avec la meilleure eval_mean_token_accuracy.
    Règle : tri décroissant par accuracy, premier = meilleur.
    """
    if not CHECKPOINTS_HISTORY.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {CHECKPOINTS_HISTORY}\n"
            "Lancer finetune.py (run standard) pour générer ce fichier."
        )

    with open(CHECKPOINTS_HISTORY) as f:
        history = json.load(f)

    checkpoints = history.get("checkpoints", [])
    if not checkpoints:
        raise ValueError(f"Aucun checkpoint listé dans {CHECKPOINTS_HISTORY}")

    ranked = sorted(
        checkpoints,
        key=lambda c: c["eval_mean_token_accuracy"],
        reverse=True,
    )

    best = ranked[0]
    checkpoint_path = LORA_DIR / best["checkpoint"]

    if not checkpoint_path.exists():
        raise FileNotFoundError(
            f"Checkpoint sélectionné introuvable sur disque : {checkpoint_path}"
        )

    print(f"[EVALUATE] Meilleur checkpoint : {best['checkpoint']} "
          f"(accuracy={best['eval_mean_token_accuracy']:.4f}, "
          f"eval_loss={best['eval_loss']:.4f})")

    return checkpoint_path


# ---------------------------------------------------------------------------
# QUESTIONS D'ÉVALUATION (15 questions — 8 EN / 7 FR)
# ---------------------------------------------------------------------------

EVAL_QUESTIONS = [
    # ── Cluster (3) ───────────────────────────────────────────────────────
    {
        "id": "en_01", "lang": "en", "type": "cluster",
        "question": "What does it mean for a therapeutic cluster to have a 'Mature' profile in drug discovery?",
    },
    {
        "id": "en_02", "lang": "en", "type": "cluster",
        "question": "What R&D opportunities does an 'Emergent' cluster profile represent compared to a 'Mature' one?",
    },
    {
        "id": "fr_01", "lang": "fr", "type": "cluster",
        "question": "Qu'est-ce qu'un cluster thérapeutique de profil 'Exploratoire' indique sur le niveau de maturité R&D ?",
    },

    # ── Target (5) ────────────────────────────────────────────────────────
    {
        "id": "en_03", "lang": "en", "type": "target",
        "question": "What does a high OpenTargets association score mean for a biological target in a drug discovery context?",
    },
    {
        "id": "en_04", "lang": "en", "type": "target",
        "question": "Why is cross-cluster frequency an important signal when evaluating a biological target?",
    },
    {
        "id": "en_05", "lang": "en", "type": "target",
        "question": "What is tractability in drug discovery and why does it matter for target selection?",
    },
    {
        "id": "fr_03", "lang": "fr", "type": "target",
        "question": "Pourquoi une cible biologique avec une fréquence transversale élevée est-elle particulièrement intéressante en drug discovery ?",
    },
    {
        "id": "fr_04", "lang": "fr", "type": "target",
        "question": "Quelle est la différence entre un signal fort et un signal faible dans l'analyse des cibles biologiques ?",
    },

    # ── Drug (3) ──────────────────────────────────────────────────────────
    {
        "id": "en_06", "lang": "en", "type": "drug",
        "question": "What is the significance of a target reaching APPROVAL stage in clinical development?",
    },
    {
        "id": "fr_06", "lang": "fr", "type": "drug",
        "question": "Que signifie le stade clinique maximum PHASE3 pour une cible biologique dans le contexte du pipeline Sanofi ?",
    },
    {
        "id": "fr_07", "lang": "fr", "type": "drug",
        "question": "Comment les données OpenTargets permettent-elles d'identifier des opportunités de repositionnement de médicaments ?",
    },

    # ── Pathway (2) ───────────────────────────────────────────────────────
    {
        "id": "en_08", "lang": "en", "type": "pathway",
        "question": "Why are Reactome biological pathways relevant when prioritizing drug targets?",
    },
    {
        "id": "fr_08", "lang": "fr", "type": "pathway",
        "question": "Quel est l'intérêt d'analyser les voies biologiques Reactome associées à une cible thérapeutique ?",
    },

    # ── Comparative (2) ───────────────────────────────────────────────────
    {
        "id": "en_09", "lang": "en", "type": "comparative",
        "question": "What is the difference between a strong signal and a weak signal target in therapeutic clustering?",
    },
    {
        "id": "fr_09", "lang": "fr", "type": "comparative",
        "question": "En quoi un cluster de profil 'Actif' diffère-t-il d'un cluster 'Émergent' du point de vue stratégique ?",
    },
]

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _log(msg: str):
    print(f"[EVALUATE] {msg}", flush=True)


# ---------------------------------------------------------------------------
# JUGE — Gemma 3 12B via Ollama (format JSON)
# ---------------------------------------------------------------------------

JUDGE_PROMPT_TEMPLATE = """You are an expert judge evaluating drug discovery question-answering quality.

Question: {question}

Response A:
{response_a}

Response B:
{response_b}

Evaluate which response is better based on:
1. Scientific accuracy in drug discovery and pharmaceutical R&D context
2. Relevance and completeness relative to the question
3. Clarity and appropriate use of domain-specific terminology

Reply ONLY with valid JSON in this exact format:
{{"verdict": "A" or "B" or "egal", "raison": "short explanation in 1-2 sentences"}}"""


def _judge_with_ollama(question: str, response_a: str, response_b: str) -> dict:
    """Appel Gemma 3 12B via Ollama — retourne verdict + raison."""
    prompt = JUDGE_PROMPT_TEMPLATE.format(
        question=question,
        response_a=response_a,
        response_b=response_b,
    )
    try:
        resp = httpx.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL_JUDGE,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0},
            },
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
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
        _log(f"Ollama juge erreur : {e}")

    return {"verdict": "EGAL", "raison": "Erreur d'évaluation"}


# ---------------------------------------------------------------------------
# ÉVALUATION PAR QUESTION
# ---------------------------------------------------------------------------

def evaluate_question(
    q: dict,
    base_response: str,
    ft_response: str,
) -> dict:
    """
    Juge une paire base/fine-tuné pour une question.
    Randomise l'ordre A/B pour éviter le biais de position.
    """
    random.seed(q["id"])
    finetuned_is_a = random.random() > 0.5

    if finetuned_is_a:
        response_a, response_b = ft_response, base_response
    else:
        response_a, response_b = base_response, ft_response

    judgment = _judge_with_ollama(q["question"], response_a, response_b)
    raw_verdict = judgment["verdict"]

    # Convertir verdict A/B vers fine-tuned/base
    if raw_verdict == "EGAL":
        winner         = "tie"
        finetuned_wins = False
    elif (raw_verdict == "A" and finetuned_is_a) or (raw_verdict == "B" and not finetuned_is_a):
        winner         = "finetuned"
        finetuned_wins = True
    else:
        winner         = "base"
        finetuned_wins = False

    return {
        **q,
        "response_base":      base_response,
        "response_finetuned": ft_response,
        "finetuned_was_a":    finetuned_is_a,
        "judge_raw":          raw_verdict,
        "judge_raison":       judgment["raison"],
        "winner":             winner,
        "finetuned_wins":     finetuned_wins,
    }


# ---------------------------------------------------------------------------
# CALCUL WIN-RATE
# ---------------------------------------------------------------------------

def compute_winrate(results: list) -> dict:
    """Calcule le win-rate global et par catégorie."""
    valid  = [r for r in results if r["winner"] != "error"]
    wins   = [r for r in valid if r["finetuned_wins"]]
    ties   = [r for r in valid if r["winner"] == "tie"]

    win_rate = round(len(wins) / len(valid) * 100, 1) if valid else 0

    by_lang = {}
    for lang in ["en", "fr"]:
        lang_results = [r for r in valid if r["lang"] == lang]
        lang_wins    = [r for r in lang_results if r["finetuned_wins"]]
        by_lang[lang] = {
            "total":    len(lang_results),
            "wins":     len(lang_wins),
            "win_rate": round(len(lang_wins) / len(lang_results) * 100, 1) if lang_results else 0,
        }

    by_type = {}
    for qtype in ["cluster", "target", "drug", "pathway", "comparative"]:
        type_results = [r for r in valid if r["type"] == qtype]
        type_wins    = [r for r in type_results if r["finetuned_wins"]]
        if type_results:
            by_type[qtype] = {
                "total":    len(type_results),
                "wins":     len(type_wins),
                "win_rate": round(len(type_wins) / len(type_results) * 100, 1),
            }

    return {
        "total_questions": len(valid),
        "wins":            len(wins),
        "ties":            len(ties),
        "losses":          len(valid) - len(wins) - len(ties),
        "win_rate":        win_rate,
        "threshold":       WIN_RATE_THRESHOLD,
        "passed":          win_rate >= WIN_RATE_THRESHOLD,
        "by_language":     by_lang,
        "by_type":         by_type,
    }


# ---------------------------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------------------------

def main():
    _log("=== Évaluation win-rate Mistral 7B Drug Discovery ===")
    _log(f"Base      : {BASE_MODEL}")
    _log(f"Juge      : {OLLAMA_MODEL_JUDGE} (Ollama local)")
    _log(f"Questions : {len(EVAL_QUESTIONS)} ({sum(1 for q in EVAL_QUESTIONS if q['lang']=='en')} EN / {sum(1 for q in EVAL_QUESTIONS if q['lang']=='fr')} FR)")

    start = time.time()

    # ── Étape 1 — Sélection du meilleur checkpoint ────────────────────────
    _log("Sélection du meilleur checkpoint...")
    best_checkpoint = select_best_checkpoint()
    _log(f"Checkpoint : {best_checkpoint}")

    questions_file      = MODELS_DIR / "eval_questions.json"
    base_responses_file = MODELS_DIR / "eval_base_responses.json"
    ft_responses_file   = MODELS_DIR / "eval_ft_responses.json"
    generate_base_script = Path(__file__).parent / "generate_base.py"
    generate_ft_script   = Path(__file__).parent / "generate_ft.py"

    # Écrire les questions dans un fichier partagé pour les subprocesses
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(questions_file, "w", encoding="utf-8") as f:
        json.dump(EVAL_QUESTIONS, f, indent=2, ensure_ascii=False)
    _log(f"Questions écrites → {questions_file}")

    # ── Étape 3 — Génération BASE (subprocess) ────────────────────────────
    if base_responses_file.exists():
        _log(f"Réponses BASE déjà présentes → reprise depuis {base_responses_file}")
    else:
        _log("Lancement subprocess generate_base.py...")
        result = subprocess.run(
            [sys.executable, str(generate_base_script)],
            cwd=str(Path(__file__).parent),
            capture_output=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"generate_base.py a échoué (exit {result.returncode})")
        _log("Subprocess BASE terminé.")

    with open(base_responses_file, encoding="utf-8") as f:
        base_responses = json.load(f)

    # ── Étape 4 — Génération FINE-TUNÉ (subprocess) ───────────────────────
    if ft_responses_file.exists():
        _log(f"Réponses FINE-TUNÉ déjà présentes → reprise depuis {ft_responses_file}")
    else:
        _log("Lancement subprocess generate_ft.py...")
        result = subprocess.run(
            [sys.executable, str(generate_ft_script)],
            cwd=str(Path(__file__).parent),
            capture_output=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"generate_ft.py a échoué (exit {result.returncode})")
        _log("Subprocess FINE-TUNÉ terminé.")

    with open(ft_responses_file, encoding="utf-8") as f:
        ft_responses = json.load(f)


    # del model_ft
    # torch.cuda.empty_cache()
    # _log("Modèle FINE-TUNÉ libéré.")

    # ── Étape 5 — Jugement ────────────────────────────────────────────────
    _log(f"Jugement {OLLAMA_MODEL_JUDGE} via Ollama...")
    results = []
    for i, q in enumerate(EVAL_QUESTIONS):
        _log(f"  Juge [{i+1}/{len(EVAL_QUESTIONS)}] {q['id']} ({q['lang'].upper()}) — {q['type']}")
        result = evaluate_question(q, base_responses[i], ft_responses[i])
        results.append(result)
        status = (
            "✓ fine-tuné" if result["finetuned_wins"]
            else ("= tie" if result["winner"] == "tie" else "✗ base")
        )
        _log(f"    → {status} | {result['judge_raison'][:80]}")

    # ── Étape 6 — Win-rate ────────────────────────────────────────────────
    summary = compute_winrate(results)

    elapsed = time.time() - start
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    # Sauvegarde
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        "model_base":       BASE_MODEL,
        "checkpoint":       str(best_checkpoint),
        "model_judge":      OLLAMA_MODEL_JUDGE,
        "summary":          summary,
        "results":          results,
        "evaluation_time_minutes": round(elapsed / 60, 1),
    }
    with open(EVAL_RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Résumé terminal
    print("\n" + "=" * 55)
    print("RÉSULTATS WIN-RATE — Mistral 7B Drug Discovery")
    print("=" * 55)
    print(f"Win-rate global : {summary['win_rate']}%  (seuil : {WIN_RATE_THRESHOLD}%)")
    verdict_global = "✅ VALIDÉ" if summary["passed"] else "❌ NON VALIDÉ"
    print(f"Verdict         : {verdict_global}")
    print(f"  Victoires : {summary['wins']}/{summary['total_questions']}")
    print(f"  Égalités  : {summary['ties']}/{summary['total_questions']}")
    print(f"  Défaites  : {summary['losses']}/{summary['total_questions']}")
    print()
    print("Par langue :")
    for lang, stats in summary["by_language"].items():
        print(f"  {lang.upper()} : {stats['win_rate']}% ({stats['wins']}/{stats['total']})")
    print()
    print("Par type de question :")
    for qtype, stats in summary["by_type"].items():
        print(f"  {qtype:12s} : {stats['win_rate']}% ({stats['wins']}/{stats['total']})")
    print("=" * 55)
    print(f"Durée    : {minutes}m {seconds}s")
    print(f"Résultats → {EVAL_RESULTS_FILE}")
    print()

    if summary["passed"]:
        _log(f"Win-rate {summary['win_rate']}% >= {WIN_RATE_THRESHOLD}% → lancer register_model.py")
    else:
        _log(f"Win-rate {summary['win_rate']}% < {WIN_RATE_THRESHOLD}% → revoir le fine-tuning")

    _log("=== Évaluation terminée ===")


if __name__ == "__main__":
    main()
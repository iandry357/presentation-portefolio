"""
export_gguf.py
--------------
Export du modèle fine-tuné Mistral 7B vers GGUF + Vertex AI Model Registry.

Étapes :
    1. Merge adaptateurs LoRA → modèle full float32
    2. Sauvegarde modèle mergé → models/merged/
    3. Upload modèle mergé vers GCS bucket sanofi-models
    4. Enregistre dans Vertex AI Model Registry (europe-west9)
    5. Affiche les commandes OVH pour quantisation GGUF Q4_K_M

La quantisation GGUF se fait directement sur OVH via llama.cpp.

Usage :
    python export_gguf.py
    python export_gguf.py --skip-vertex   # merge uniquement, sans GCS/Vertex

Prérequis :
    - models/lora/ généré par finetune.py
    - GCP service account avec accès GCS + Vertex AI
"""

import json
import time
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# PARAMÈTRES CONFIGURABLES
# ---------------------------------------------------------------------------
load_dotenv()

MODELS_DIR          = Path(__file__).parent / "models"
LORA_DIR            = MODELS_DIR / "lora"
MERGED_DIR          = MODELS_DIR / "merged"

BASE_MODEL          = "mistralai/Mistral-7B-Instruct-v0.3"
# BASE_MODEL = "google/gemma-2-2b-it"

OVH_USER            = "ubuntu"
OVH_HOST            = "51.68.130.23"
OVH_GGUF_DIR        = "/home/ubuntu/ml-project/realisations/sanofi/ml/models"

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _log(msg: str):
    print(f"[EXPORT] {msg}", flush=True)

def select_best_checkpoint() -> Path:
    """
    Lit models/checkpoints_history.json et sélectionne le checkpoint
    avec la meilleure eval_mean_token_accuracy.

    Règle : tri par accuracy décroissante, le premier gagne (pas de seuil,
    pas de critère combiné — en cas d'égalité stricte, le premier rencontré
    dans l'ordre chronologique est conservé).
    """
    history_path = MODELS_DIR / "checkpoints_history.json"

    if not history_path.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {history_path}\n"
            "Lancer finetune.py (run standard, sans --search-hyperparams) "
            "pour générer ce fichier."
        )

    with open(history_path) as f:
        history = json.load(f)

    checkpoints = history.get("checkpoints", [])
    if not checkpoints:
        raise ValueError(f"Aucun checkpoint listé dans {history_path}")

    ranked = sorted(
        checkpoints,
        key=lambda c: c["eval_mean_token_accuracy"],
        reverse=True,
    )

    _log("Classement des checkpoints par eval_mean_token_accuracy :")
    for rank, c in enumerate(ranked, start=1):
        marker = " <-- sélectionné" if rank == 1 else ""
        _log(
            f"  {rank}. {c['checkpoint']} (epoch {c['epoch']}) "
            f"accuracy={c['eval_mean_token_accuracy']:.4f} "
            f"eval_loss={c['eval_loss']:.4f}{marker}"
        )

    best = ranked[0]
    checkpoint_path = LORA_DIR / best["checkpoint"]

    if not checkpoint_path.exists():
        raise FileNotFoundError(
            f"Le checkpoint sélectionné n'existe plus sur disque : {checkpoint_path}"
        )

    return checkpoint_path

# ---------------------------------------------------------------------------
# ÉTAPE 1 — Merge LoRA
# ---------------------------------------------------------------------------
def merge_lora() -> Path:
    """
    Merge les adaptateurs LoRA dans le modèle base.
    Sauvegarde le modèle mergé en float32 → models/merged/
    """
    best_checkpoint = select_best_checkpoint()

    _log(f"Chargement modèle base : {BASE_MODEL}")
    _log("Note : chargement en float16 pour le merge, converti en float32 après.")

    offload_dir = MODELS_DIR / "offload"
    offload_dir.mkdir(parents=True, exist_ok=True)

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map="auto",
        offload_folder=str(offload_dir),
        trust_remote_code=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)

    _log(f"Chargement adaptateurs LoRA : {best_checkpoint}")
    peft_model = PeftModel.from_pretrained(
        model,
        str(best_checkpoint),
        offload_folder=str(offload_dir),
    )

    _log("Merge LoRA → modèle full...")
    merged_model = peft_model.merge_and_unload()

    # Conversion float32 — requis pour llama.cpp convert
    _log("Conversion float32...")
    merged_model = merged_model.to(torch.float32)

    MERGED_DIR.mkdir(parents=True, exist_ok=True)
    _log(f"Sauvegarde modèle mergé → {MERGED_DIR}")
    merged_model.save_pretrained(str(MERGED_DIR), safe_serialization=True)
    tokenizer.save_pretrained(str(MERGED_DIR))

    _log("Merge terminé.")
    return MERGED_DIR




# ---------------------------------------------------------------------------
# ÉTAPE 4 — Instructions OVH
# ---------------------------------------------------------------------------

def print_ovh_instructions():
    """
    Affiche les commandes exactes à lancer sur OVH pour la quantisation GGUF.
    """
    merged_dir_name = MERGED_DIR.name

    print("\n" + "="*60)
    print("INSTRUCTIONS — Quantisation GGUF sur OVH")
    print("="*60)
    print()
    print("1. Transférer le modèle mergé vers OVH :")
    print(f"   scp -r {MERGED_DIR} {OVH_USER}@{OVH_HOST}:{OVH_GGUF_DIR}/")
    print()
    print("2. Sur OVH — convertir en GGUF :")
    print(f"   cd /home/ubuntu/llama.cpp")
    print(f"   python convert_hf_to_gguf.py {OVH_GGUF_DIR}/{merged_dir_name} \\")
    print(f"     --outfile {OVH_GGUF_DIR}/mistral7b-drug-f32.gguf \\")
    print(f"     --outtype f32")
    print()
    print("3. Sur OVH — quantiser Q4_K_M :")
    print(f"   ./llama-quantize \\")
    print(f"     {OVH_GGUF_DIR}/mistral7b-drug-f32.gguf \\")
    print(f"     {OVH_GGUF_DIR}/mistral7b-drug.gguf \\")
    print(f"     Q4_K_M")
    print()
    print("4. Sur OVH — tester le modèle :")
    print(f"   ./llama-cli -m {OVH_GGUF_DIR}/mistral7b-drug.gguf \\")
    print(f"     -p '[INST] What is IL4R? [/INST]' -n 100")
    print()
    print("5. Mettre à jour graph_rag.py :")
    print("   → Changer GGUF_MODEL_PATH vers mistral7b-drug.gguf")
    print("   → Passer LLM_AVAILABLE = True")
    print("="*60 + "\n")


# ---------------------------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------------------------

def main():
    _log("=== Export Mistral 7B Drug Discovery ===")
    start = time.time()

    # Vérification adaptateurs LoRA (dossier parent uniquement —
    # la sélection du checkpoint précis se fait dans merge_lora())
    if not LORA_DIR.exists():
        raise FileNotFoundError(
            f"Dossier LoRA introuvable : {LORA_DIR}\n"
            "Lancer finetune.py d'abord."
        )

    # Merge
    merge_lora()

    _log("Merge terminé — lancer register_model.py pour upload GCS + Vertex AI.")

    # Instructions OVH
    print_ovh_instructions()

    elapsed = time.time() - start
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    _log(f"=== Export terminé en {minutes}m {seconds}s ===")


if __name__ == "__main__":
    main()
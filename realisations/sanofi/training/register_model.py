"""
register_model.py
-----------------
Upload du modèle fine-tuné Mistral 7B vers GCS + Vertex AI Model Registry.

Prérequis :
    - models/merged/              généré par export_gguf.py
    - models/finetune_metrics.json généré par finetune.py
    - models/eval_results.json    généré par evaluate.py
    - gcp_sa_sanofi.json          en racine training/

Usage :
    python register_model.py
    python register_model.py --force   # ignore le seuil win_rate
"""

import argparse
import json
import sys
import time
from pathlib import Path

from google.cloud import aiplatform, storage
from google.oauth2 import service_account

# ---------------------------------------------------------------------------
# PARAMÈTRES CONFIGURABLES
# ---------------------------------------------------------------------------

TRAINING_DIR        = Path(__file__).parent
MODELS_DIR          = TRAINING_DIR / "models"
# MERGED_DIR          = MODELS_DIR / "merged"
LORA_DIR            = MODELS_DIR / "lora"
CHECKPOINTS_HISTORY = MODELS_DIR / "checkpoints_history.json"
FINETUNE_METRICS    = MODELS_DIR / "finetune_metrics.json"
EVAL_RESULTS        = MODELS_DIR / "eval_results.json"
VERTEX_MODEL_ID_FILE = MODELS_DIR / "vertex_model_id.txt"
SA_KEY_PATH         = TRAINING_DIR.parent / "gcp_sa_sanofi.json"

PROJECT_ID          = "gen-lang-client-0989575872"
GCS_BUCKET          = "sanofi-models"
GCS_PREFIX          = "sanofi"
GCS_MODEL_DIR       = "mistral7b-drug-discovery"
VERTEX_REGION       = "europe-west9"
VERTEX_DISPLAY_NAME = "sanofi-mistral7b-drug-discovery"
VERTEX_FRAMEWORK    = "huggingface-peft-gpu"

WIN_RATE_THRESHOLD  = 30.0   # % minimum pour éligibilité Vertex AI

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _log(msg: str):
    print(f"[REGISTER] {msg}", flush=True)


def _get_credentials() -> service_account.Credentials:
    if not SA_KEY_PATH.exists():
        _log(f"Clé SA introuvable : {SA_KEY_PATH}")
        _log("Copier gcp_sa_sanofi.json dans realisations/sanofi/training/")
        sys.exit(1)
    return service_account.Credentials.from_service_account_file(
        str(SA_KEY_PATH),
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )


def _load_metrics() -> tuple[dict, dict]:
    """Charge finetune_metrics.json + eval_results.json."""
    finetune_metrics = {}
    eval_results     = {}

    if FINETUNE_METRICS.exists():
        with open(FINETUNE_METRICS, encoding="utf-8") as f:
            finetune_metrics = json.load(f)
        _log(f"finetune_metrics — eval_loss={finetune_metrics.get('eval_loss')} / perplexity={finetune_metrics.get('perplexity')}")
    else:
        _log(f"finetune_metrics.json introuvable : {FINETUNE_METRICS}")

    if EVAL_RESULTS.exists():
        with open(EVAL_RESULTS, encoding="utf-8") as f:
            eval_results = json.load(f)
        win_rate = eval_results.get("summary", {}).get("win_rate", 0)
        _log(f"eval_results — win_rate={win_rate}%")
    else:
        _log(f"eval_results.json introuvable : {EVAL_RESULTS}")

    return finetune_metrics, eval_results


# ---------------------------------------------------------------------------
# UPLOAD GCS
# ---------------------------------------------------------------------------

# def upload_to_gcs(credentials: service_account.Credentials) -> str:
def upload_to_gcs(artifact_dir: Path, credentials: service_account.Credentials) -> str:
    """
    Upload models/merged/ vers gs://sanofi-models/sanofi/mistral7b-drug-discovery/
    Retourne le GCS URI.
    """
    _log(f"Upload vers gs://{GCS_BUCKET}/{GCS_PREFIX}/{GCS_MODEL_DIR}/...")
    client = storage.Client(project=PROJECT_ID, credentials=credentials)

    # Créer le bucket si inexistant
    # Le bucket est créé manuellement — on accède directement sans vérifier
    bucket = client.bucket(GCS_BUCKET)
    _log(f"Bucket {GCS_BUCKET} prêt.")

    # Upload tous les fichiers du modèle mergé
    # files   = [f for f in MERGED_DIR.rglob("*") if f.is_file()]
    files   = [f for f in artifact_dir.rglob("*") if f.is_file()]
    total   = len(files)
    uploaded = 0

    for file_path in files:
        # relative  = file_path.relative_to(MERGED_DIR)
        relative  = file_path.relative_to(artifact_dir)
        blob_name = f"{GCS_PREFIX}/{GCS_MODEL_DIR}/{relative}"
        blob      = bucket.blob(blob_name)
        blob.upload_from_filename(str(file_path))
        uploaded += 1
        if uploaded % 5 == 0 or uploaded == total:
            _log(f"  {uploaded}/{total} fichiers uploadés...")

    gcs_uri = f"gs://{GCS_BUCKET}/{GCS_PREFIX}/{GCS_MODEL_DIR}"
    _log(f"Upload terminé → {gcs_uri}")
    return gcs_uri


# ---------------------------------------------------------------------------
# VERTEX AI MODEL REGISTRY
# ---------------------------------------------------------------------------

def register_vertex(
    gcs_uri: str,
    finetune_metrics: dict,
    eval_results: dict,
    credentials: service_account.Credentials,
) -> str:
    """
    Enregistre le modèle dans Vertex AI Model Registry.
    Crée une nouvelle version si le modèle existe déjà.
    Retourne le resource name.
    """
    _log("Enregistrement Vertex AI Model Registry...")

    aiplatform.init(
        project=PROJECT_ID,
        location=VERTEX_REGION,
        credentials=credentials,
    )

    # Labels — métriques clés
    win_rate   = eval_results.get("summary", {}).get("win_rate", 0)
    eval_loss  = finetune_metrics.get("eval_loss", 0)
    perplexity = finetune_metrics.get("perplexity", 0)
    epochs     = finetune_metrics.get("epochs", 0)

    labels = {
        "framework":   VERTEX_FRAMEWORK.replace(".", "-").replace("_", "-")[:63],
        "sector":      "sanofi",
        "model-type":  "mistral7b-qlora",
        "eval-loss":   str(round(eval_loss, 4)).replace(".", "-"),
        "perplexity":  str(round(perplexity, 2)).replace(".", "-"),
        "win-rate":    str(round(win_rate, 1)).replace(".", "-"),
        "epochs":      str(epochs),
        "eligible":    "true" if win_rate >= WIN_RATE_THRESHOLD else "false",
    }

    # Vérifier si le modèle existe déjà → nouvelle version
    existing = aiplatform.Model.list(
        filter=f'display_name="{VERTEX_DISPLAY_NAME}"',
        project=PROJECT_ID,
        location=VERTEX_REGION,
        credentials=credentials,
    )

    parent_model = existing[0].resource_name if existing else None
    if parent_model:
        _log("Modèle existant trouvé — upload nouvelle version.")
    else:
        _log("Nouveau modèle — création dans Vertex AI.")

    model = aiplatform.Model.upload(
        display_name=VERTEX_DISPLAY_NAME,
        description=(
            "Mistral 7B Instruct fine-tuned with QLoRA on drug discovery dataset. "
            "Trained on PubMedQA (filtered) + synthetic Sanofi therapeutic clusters data. "
            f"Win-rate vs base: {win_rate}% | Eval loss: {eval_loss} | Perplexity: {perplexity}. "
            "Served via llama.cpp GGUF Q4_K_M on OVH CPU."
        ),
        artifact_uri=gcs_uri,
        serving_container_image_uri="europe-docker.pkg.dev/vertex-ai/prediction/huggingface-cpu.2-3:latest",
        labels=labels,
        project=PROJECT_ID,
        location=VERTEX_REGION,
        credentials=credentials,
        parent_model=parent_model,
    )

    resource_name = model.resource_name
    _log(f"Modèle enregistré → {resource_name}")

    # Sauvegarde resource name
    VERTEX_MODEL_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(VERTEX_MODEL_ID_FILE, "w") as f:
        f.write(resource_name)
    _log(f"Model ID sauvegardé → {VERTEX_MODEL_ID_FILE}")

    return resource_name


# ---------------------------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Register Mistral 7B Drug Discovery — Vertex AI")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignorer le seuil win_rate — uploader même si le modèle ne dépasse pas le seuil",
    )
    args = parser.parse_args()

    _log("=== Register Mistral 7B Drug Discovery → Vertex AI ===")
    start = time.time()

    # Vérification modèle mergé
    # if not MERGED_DIR.exists():
    #     _log(f"models/merged/ introuvable — lancer export_gguf.py d'abord.")
    #     sys.exit(1)

    # Sélection automatique du meilleur checkpoint
    if not CHECKPOINTS_HISTORY.exists():
        _log(f"checkpoints_history.json introuvable — lancer finetune.py d'abord.")
        sys.exit(1)

    with open(CHECKPOINTS_HISTORY) as f:
        history = json.load(f)
    ranked = sorted(
        history.get("checkpoints", []),
        key=lambda c: c["eval_mean_token_accuracy"],
        reverse=True,
    )
    if not ranked:
        _log("Aucun checkpoint dans checkpoints_history.json.")
        sys.exit(1)

    best = ranked[0]
    artifact_dir = LORA_DIR / best["checkpoint"]
    _log(f"Checkpoint sélectionné : {best['checkpoint']} (accuracy={best['eval_mean_token_accuracy']:.4f})")

    if not artifact_dir.exists():
        _log(f"Checkpoint introuvable sur disque : {artifact_dir}")
        sys.exit(1)

    # Chargement métriques
    finetune_metrics, eval_results = _load_metrics()

    # Vérification éligibilité
    win_rate = eval_results.get("summary", {}).get("win_rate", 0)
    if not args.force and win_rate < WIN_RATE_THRESHOLD:
        _log(f"Win-rate {win_rate}% < seuil {WIN_RATE_THRESHOLD}% — modèle non éligible.")
        _log("Utiliser --force pour ignorer le seuil.")
        sys.exit(1)

    _log(f"Win-rate : {win_rate}% ✓ — modèle éligible.")

    # Credentials
    credentials = _get_credentials()

    # Upload GCS
    # gcs_uri = upload_to_gcs(credentials)
    gcs_uri = upload_to_gcs(artifact_dir, credentials)

    # Vertex AI
    resource_name = register_vertex(gcs_uri, finetune_metrics, eval_results, credentials)

    elapsed = time.time() - start
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    _log(f"=== Enregistrement terminé en {minutes}m {seconds}s ===")
    _log(f"Resource : {resource_name}")


if __name__ == "__main__":
    main()
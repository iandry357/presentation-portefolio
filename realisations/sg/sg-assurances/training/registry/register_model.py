"""
Registry — Enregistrement modèles dans Vertex AI Model Registry
Générique : YOLO / NER / QLoRA

Usage :
    python registry/register_model.py --model yolo
    python registry/register_model.py --model ner
    python registry/register_model.py --model qlora

Prérequis :
    - models/<model>_metrics.json (produit par evaluate.py)
    - models/yolo_sg_assurances.pt | ner_sg_assurances/ | qlora_sg_assurances/
    - gcp_sa_sg.json en racine training/
    - Bucket GCS gs://sg-assurances-models
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import storage
from google.oauth2 import service_account
from google.cloud import aiplatform

import subprocess
import shutil

# ─────────────────────────────────────────
# Chemins
# ─────────────────────────────────────────
TRAINING_DIR = Path(__file__).parent.parent
load_dotenv(TRAINING_DIR / ".env")

MODELS_DIR  = TRAINING_DIR / "models"
SA_KEY_PATH = TRAINING_DIR.parent / "gcp_sa_sg.json"

# ─────────────────────────────────────────
# Config GCP
# ─────────────────────────────────────────
PROJECT_ID   = "gen-lang-client-0989575872"
LOCATION     = "europe-west9"
GCS_BUCKET   = "sg-assurances-models"
GCS_PREFIX   = "sg-assurances"

MAR_DIR = MODELS_DIR / "yolo" / "mar"
MAR_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────
# Config modèles — mappings génériques
# ─────────────────────────────────────────
MODEL_CONFIG = {
    "yolo": {
        "artifact":     "yolo/yolo_sg_assurances.pt",
        "metrics":      "yolo/yolo_metrics.json",
        "display_name": "sg-assurances-yolo",
        "description":  "YOLOv8s fine-tuné sur documents SG Assurances — détection zones (contract, identity, amount, signature)",
        "framework":    "ultralytics-yolov8",
        "gcs_dir":      "yolo",
    },
    "ner": {
        "artifact":     "ner/ner_sg_assurances",
        "metrics":      "ner/ner_sg_assurances/eval_results.json",
        "display_name": "sg-assurances-ner",
        "description":  "CamemBERT fine-tuné sur documents SG Assurances — extraction entités nommées assurance",
        "framework":    "huggingface-transformers",
        "gcs_dir":      "ner",
    },
    "qlora": {
        "artifact":     "qlora/qlora_sg_assurances",
        "metrics":      "qlora/qlora_eval_results.json",
        "display_name": "sg-assurances-qlora",
        "description":  "Qwen2.5-1.5B QLoRA fine-tuné sur paires QA SG Assurances",
        "framework":    "huggingface-peft",
        "gcs_dir":      "qlora",
    },
}


# ─────────────────────────────────────────
# Credentials GCP
# ─────────────────────────────────────────
def _get_credentials() -> service_account.Credentials:
    if not SA_KEY_PATH.exists():
        print(f"[registry] Clé SA introuvable : {SA_KEY_PATH}")
        sys.exit(1)
    return service_account.Credentials.from_service_account_file(
        str(SA_KEY_PATH),
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

def _package_mar(model_type: str, config: dict) -> Path:
    """
    Package le modèle en model.mar via torch-model-archiver.
    Retourne le chemin vers le .mar généré.
    """
    artifact_path = MODELS_DIR / config["artifact"]
    handler_path  = TRAINING_DIR / "registry" / "handlers" / f"{model_type}_handler.py"
    mar_path      = MAR_DIR / "model.mar"

    # Supprimer l'ancien .mar si existe
    if mar_path.exists():
        mar_path.unlink()
        print(f"[registry] Ancien model.mar supprimé")

    if not handler_path.exists():
        print(f"[registry] Handler introuvable : {handler_path}")
        sys.exit(1)

    cmd = [
        "torch-model-archiver",
        "--model-name",    "model",
        "--version",       "1.0",
        "--serialized-file", str(artifact_path),
        "--handler",       str(handler_path),
        "--export-path",   str(MAR_DIR),
        "--force",
    ]

    print(f"[registry] Packaging model.mar...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"[registry] Erreur packaging : {result.stderr}")
        sys.exit(1)

    print(f"[registry] model.mar généré → {mar_path}")
    return mar_path

# ─────────────────────────────────────────
# Upload GCS
# ─────────────────────────────────────────
def _upload_to_gcs(
    local_path: Path,
    gcs_dir: str,
    credentials: service_account.Credentials,
) -> str:
    """
    Upload fichier ou répertoire vers GCS.
    Retourne le gs:// URI du répertoire parent.
    """
    client = storage.Client(project=PROJECT_ID, credentials=credentials)
    bucket = client.bucket(GCS_BUCKET)
    gcs_base = f"{GCS_PREFIX}/{gcs_dir}"

    if local_path.is_file():
        blob_name = f"{gcs_base}/{local_path.name}"
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(local_path))
        print(f"[registry] Uploadé → gs://{GCS_BUCKET}/{blob_name}")
    elif local_path.is_dir():
        for f in local_path.rglob("*"):
            if f.is_file():
                rel = f.relative_to(local_path)
                blob_name = f"{gcs_base}/{local_path.name}/{rel}"
                blob = bucket.blob(blob_name)
                blob.upload_from_filename(str(f))
                print(f"[registry] Uploadé → gs://{GCS_BUCKET}/{blob_name}")
    else:
        print(f"[registry] Artefact introuvable : {local_path}")
        sys.exit(1)

    return f"gs://{GCS_BUCKET}/{gcs_base}/"

def _get_serving_container(framework: str) -> str:
    """Retourne l'image container Vertex adaptée au framework."""
    if framework == "ultralytics-yolov8":
        return "europe-docker.pkg.dev/vertex-ai/prediction/pytorch-cpu.2-0:latest"
    elif framework in ("huggingface-transformers", "huggingface-peft"):
        return "europe-docker.pkg.dev/vertex-ai/prediction/huggingface-cpu.2-3:latest"
    else:
        return "europe-docker.pkg.dev/vertex-ai/prediction/pytorch-cpu.2-0:latest"

# ─────────────────────────────────────────
# Vertex AI — enregistrement modèle
# ─────────────────────────────────────────
def _register_vertex(
    config: dict,
    metrics: dict,
    gcs_uri: str,
    credentials: service_account.Credentials,
) -> str:
    """
    Enregistre le modèle dans Vertex AI Model Registry.
    Retourne le resource name du modèle.
    """
    aiplatform.init(
        project=PROJECT_ID,
        location=LOCATION,
        credentials=credentials,
    )

    # Labels — métriques globales tronquées pour Vertex AI (max 63 chars, alphanum+tiret)
    eligible = metrics.get("eligible_vertex_ai") or metrics.get("threshold_reached") or metrics.get("rouge_improved", False)

    if config["gcs_dir"] == "yolo":
        perf_label = {"map50": str(round(metrics.get("global", {}).get("mAP50", 0), 4)).replace(".", "-")}
    elif config["gcs_dir"] == "ner":
        perf_label = {"f1-macro": str(round(metrics.get("finetuned", {}).get("f1_macro", 0), 4)).replace(".", "-")}
    else:  # qlora
        rouge_l = metrics.get("rouge_ft", {}).get("rougeL", 0)
        win_rate = str(round(metrics.get("judge_summary", {}).get("ft_win_rate", 0), 3)).replace(".", "-")
        perf_label = {
            "rougel-ft":  str(round(rouge_l, 4)).replace(".", "-"),
            "ft-win-rate": win_rate,
        }

    labels = {
        "framework":  config["framework"].replace(".", "-").replace("_", "-")[:63],
        "eligible":   "true" if bool(eligible) else "false",
        "sector":     "sg-assurances",
        "model-type": config["gcs_dir"],
        **perf_label,
    }
    
    # Vérifier si le modèle existe déjà — update sinon create
    models = aiplatform.Model.list(
        filter=f'display_name="{config["display_name"]}"',
        project=PROJECT_ID,
        location=LOCATION,
        credentials=credentials,
    )

    if models:
        print(f"[registry] Modèle existant trouvé — upload nouvelle version")
        parent_model = models[0].resource_name
    else:
        print(f"[registry] Création nouveau modèle dans Vertex AI")
        parent_model = None

    model = aiplatform.Model.upload(
        display_name=config["display_name"],
        description=config["description"],
        artifact_uri=gcs_uri,
        serving_container_image_uri=_get_serving_container(config["framework"]),
        serving_container_predict_route="/predictions/model",
        serving_container_health_route="/ping",
        labels=labels,
        project=PROJECT_ID,
        location=LOCATION,
        credentials=credentials,
        parent_model=parent_model,      # ← nouvelle version si existant
    )

    print(f"[registry] Modèle enregistré → {model.resource_name}")
    return model.resource_name


# ─────────────────────────────────────────
# Sauvegarde model ID
# ─────────────────────────────────────────
def _save_model_id(model_type: str, resource_name: str) -> None:
    id_path = MODELS_DIR / model_type / f"{model_type}_vertex_model_id.txt"
    with open(id_path, "w", encoding="utf-8") as f:
        f.write(resource_name)
    print(f"[registry] Model ID sauvegardé → {id_path}")


# ─────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────
def register(model_type: str) -> None:
    if model_type not in MODEL_CONFIG:
        print(f"[registry] Type inconnu : {model_type} — choisir parmi {list(MODEL_CONFIG.keys())}")
        sys.exit(1)

    config = MODEL_CONFIG[model_type]

    # Vérifier métriques
    metrics_path = MODELS_DIR / config["metrics"]
    if not metrics_path.exists():
        print(f"[registry] metrics.json introuvable : {metrics_path}")
        print(f"[registry] Lance yolo/evaluate.py d'abord")
        sys.exit(1)

    with open(metrics_path, encoding="utf-8") as f:
        metrics = json.load(f)

    # eligible = metrics.get("eligible_vertex_ai") or metrics.get("threshold_reached")
    eligible = (
        metrics.get("eligible_vertex_ai") or
        metrics.get("threshold_reached") or
        metrics.get("rouge_improved", False)
    )
    if not eligible:
        print(f"[registry] Modèle non éligible — seuil non atteint")
        sys.exit(1)

    # if not metrics.get("eligible_vertex_ai"):
    #     print(f"[registry] Modèle non éligible — mAP50 < {metrics.get('threshold', 0.40)}")
    #     sys.exit(1)

    # Vérifier artefact
    artifact_path = MODELS_DIR / config["artifact"]

    print(f"[registry] Démarrage enregistrement — modèle : {model_type}")
    print(f"[registry] Artefact : {artifact_path}")
    if model_type == "qlora":
        print(f"[registry] ROUGE-L FT : {metrics.get('rouge_ft', {}).get('rougeL', 'N/A')}")
        print(f"[registry] Win rate   : {metrics.get('judge_summary', {}).get('ft_win_rate', 'N/A')}")
    else:
        print(f"[registry] mAP50    : {metrics.get('global', {}).get('mAP50', 'N/A')}")

    # Credentials
    credentials = _get_credentials()

    # Packaging MAR uniquement pour YOLO (.pt)
    if model_type == "yolo":
        mar_path = _package_mar(model_type, config)
        # Upload GCS — on uploade le .mar + le .pt original
        print(f"[registry] Upload GCS → gs://{GCS_BUCKET}/{GCS_PREFIX}/{config['gcs_dir']}/")
        gcs_uri = _upload_to_gcs(mar_path, config["gcs_dir"], credentials)
        _upload_to_gcs(artifact_path, config["gcs_dir"], credentials)
    else:
        # NER / QLoRA — upload répertoire HuggingFace direct
        print(f"[registry] Upload GCS → gs://{GCS_BUCKET}/{GCS_PREFIX}/{config['gcs_dir']}/")
        gcs_uri = _upload_to_gcs(artifact_path, config["gcs_dir"], credentials)

    # Vertex AI
    resource_name = _register_vertex(config, metrics, gcs_uri, credentials)

    # Sauvegarde ID
    _save_model_id(model_type, resource_name)

    print(f"\n[registry] Done — {model_type} enregistré dans Vertex AI Model Registry")
    print(f"[registry] Resource : {resource_name}")


# ─────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Register model in Vertex AI Model Registry")
    parser.add_argument(
        "--model",
        required=True,
        choices=["yolo", "ner", "qlora"],
        help="Type de modèle à enregistrer",
    )
    args = parser.parse_args()
    register(args.model)
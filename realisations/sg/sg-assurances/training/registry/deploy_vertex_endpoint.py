"""
Déploiement Vertex AI Endpoint — Qwen base + fine-tuné
1 endpoint unique, 1 T4, 2 deployed models

Usage :
    python registry/deploy_vertex_endpoint.py

Prérequis :
    - models/qwen-base/qwen-base_vertex_model_id.txt
    - models/qlora/qlora_vertex_model_id.txt
    - gcp_sa_sg.json en racine sg-assurances/
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import aiplatform
from google.oauth2 import service_account

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
PROJECT_ID    = "gen-lang-client-0989575872"
ENDPOINT_NAME = "sg-assurances-qwen"
LOCATION      = "europe-west4"
MACHINE_TYPE  = "n1-standard-4"
ACCELERATOR   = "NVIDIA_TESLA_T4"
ENDPOINT_ID_FILE = MODELS_DIR / "qwen_endpoint_id.json"
CUSTOM_IMAGE    = "europe-west4-docker.pkg.dev/gen-lang-client-0989575872/sg-assurances-serving/qwen-serving:latest"
HEALTH_ROUTE    = "/health"
PREDICT_ROUTE   = "/predict"

# ─────────────────────────────────────────
# Modèles à déployer
# ─────────────────────────────────────────
MODELS_TO_DEPLOY = {
    "qlora": {
        "display_name": "qwen-finetuned",
        "model_type":   "finetuned",
        "traffic_pct":  100,
    },
    # "qwen-base": {
    #     "display_name": "qwen-base",
    #     "model_type":   "base",
    #     "traffic_pct":  50,
    # },
}

# ─────────────────────────────────────────
# Credentials
# ─────────────────────────────────────────
def _get_credentials() -> service_account.Credentials:
    if not SA_KEY_PATH.exists():
        print(f"[deploy] Clé SA introuvable : {SA_KEY_PATH}")
        sys.exit(1)
    return service_account.Credentials.from_service_account_file(
        str(SA_KEY_PATH),
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

# ─────────────────────────────────────────
# Création endpoint
# ─────────────────────────────────────────
def _create_or_get_endpoint(credentials) -> aiplatform.Endpoint:
    existing = aiplatform.Endpoint.list(
        filter=f'display_name="{ENDPOINT_NAME}"',
        project=PROJECT_ID,
        location=LOCATION,
        credentials=credentials,
    )
    if existing:
        print(f"[deploy] Endpoint existant trouvé — réutilisation")
        return existing[0]

    print(f"[deploy] Création endpoint : {ENDPOINT_NAME}")
    endpoint = aiplatform.Endpoint.create(
        display_name=ENDPOINT_NAME,
        project=PROJECT_ID,
        location=LOCATION,
        credentials=credentials,
    )
    print(f"[deploy] Endpoint créé → {endpoint.resource_name}")
    return endpoint

# ─────────────────────────────────────────
# Déploiement modèles sur endpoint
# ─────────────────────────────────────────
def _deploy_model(
    endpoint: aiplatform.Endpoint,
    model_key: str,
    config: dict,
    credentials,
) -> str:
    print(f"\n[deploy] Déploiement modèle : {model_key} (MODEL_TYPE={config['model_type']})")

    model = aiplatform.Model.upload(
        display_name=config["display_name"],
        serving_container_image_uri=CUSTOM_IMAGE,
        serving_container_predict_route=PREDICT_ROUTE,
        serving_container_health_route=HEALTH_ROUTE,
        serving_container_environment_variables={
            "MODEL_TYPE": config["model_type"],
        },
        project=PROJECT_ID,
        location=LOCATION,
        credentials=credentials,
    )
    print(f"[deploy] Modèle uploadé → {model.resource_name}")

    print(f"[deploy] Déploiement sur endpoint ({MACHINE_TYPE} + {ACCELERATOR})...")
    endpoint.deploy(
        model=model,
        deployed_model_display_name=config["display_name"],
        machine_type=MACHINE_TYPE,
        accelerator_type=ACCELERATOR,
        accelerator_count=1,
        traffic_percentage=config["traffic_pct"],
        sync=True,
    )

    print(f"[deploy] {model_key} déployé ✓")
    return model.resource_name

# ─────────────────────────────────────────
# Sauvegarde endpoint + deployed model IDs
# ─────────────────────────────────────────
def _save_endpoint_info(endpoint: aiplatform.Endpoint, deployed_ids: dict) -> None:
    info = {
        "endpoint_resource_name": endpoint.resource_name,
        "endpoint_display_name":  ENDPOINT_NAME,
        "deployed_models":        deployed_ids,
    }
    with open(ENDPOINT_ID_FILE, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)
    print(f"\n[deploy] Endpoint info sauvegardée → {ENDPOINT_ID_FILE}")

# ─────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────
def main() -> None:
    credentials = _get_credentials()

    aiplatform.init(
        project=PROJECT_ID,
        location=LOCATION,
        credentials=credentials,
    )

    # Créer ou récupérer l'endpoint
    endpoint = _create_or_get_endpoint(credentials)

    # Déployer les deux modèles
    deployed_ids = {}
    for model_key, config in MODELS_TO_DEPLOY.items():
        did = _deploy_model(endpoint, model_key, config, credentials)
        deployed_ids[model_key] = did

    # Sauvegarder
    _save_endpoint_info(endpoint, deployed_ids)

    print(f"\n[deploy] Done — 2 modèles déployés sur endpoint {ENDPOINT_NAME}")
    print(f"[deploy] Endpoint : {endpoint.resource_name}")


if __name__ == "__main__":
    main()
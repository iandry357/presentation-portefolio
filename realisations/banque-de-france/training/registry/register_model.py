"""
register_model.py — MVP Banque de France / registre MLOps générique

Upload vers GCS + enregistrement Vertex AI Model Registry, générique pour
tous les types de modèles du MVP Banque de France (classification, ner, eba,
webstat...). La logique commune (upload GCS, appel API Vertex AI, gestion du
versioning) vit ici ; tout ce qui est spécifique à un type de modèle
(chemin de l'artefact, description, labels/métriques, image de serving) est
délégué à un handler dédié dans registry/handlers/.

Utilisé uniquement comme registre MLOps / traçabilité — aucun déploiement
d'endpoint Vertex AI n'est prévu (les services d'inférence réels tournent
sur OVH, comme les autres MVPs du projet).

Contrat attendu de chaque handler (registry/handlers/<model>_handler.py) :
    get_artifact_dir() -> Path
    get_display_name() -> str
    get_description() -> str
    get_labels() -> dict
    get_serving_container_uri() -> str

Usage :
    python register_model.py --model classification
"""

import argparse
import importlib
import sys
import time
from pathlib import Path

from google.cloud import aiplatform, storage
from google.oauth2 import service_account

# ---------------------------------------------------------------------------
# PARAMÈTRES CONFIGURABLES
# ---------------------------------------------------------------------------

TRAINING_DIR = Path(__file__).resolve().parent.parent  # training/
SA_KEY_PATH = TRAINING_DIR.parent / "gcp_sa_banque.json"

PROJECT_ID = "gen-lang-client-0989575872"
GCS_BUCKET = "banque-de-france-models"
GCS_PREFIX = "banque-de-france"
VERTEX_REGION = "europe-west9"

# Handlers disponibles : nom passé en --model -> module dans registry/handlers/
AVAILABLE_HANDLERS = {
    "classification": "handlers.classification_handler",
    # "ner": "handlers.ner_handler",       # à activer une fois train_ner.py opérationnel
    # "eba": "handlers.eba_handler",        # idem
    # "webstat": "handlers.webstat_handler",
}


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _log(msg: str):
    print(f"[REGISTER] {msg}", flush=True)


def _get_credentials() -> service_account.Credentials:
    if not SA_KEY_PATH.exists():
        _log(f"Clé SA introuvable : {SA_KEY_PATH}")
        _log("Copier gcp_sa_banque.json dans realisations/banque-de-france/")
        sys.exit(1)
    return service_account.Credentials.from_service_account_file(
        str(SA_KEY_PATH),
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )


def _load_handler(model_name: str):
    if model_name not in AVAILABLE_HANDLERS:
        _log(f"Modèle '{model_name}' inconnu. Options : {list(AVAILABLE_HANDLERS.keys())}")
        sys.exit(1)

    module_path = AVAILABLE_HANDLERS[model_name]
    try:
        handler = importlib.import_module(module_path)
    except ImportError as e:
        _log(f"Impossible de charger le handler '{module_path}' : {e}")
        sys.exit(1)

    required_functions = [
        "get_artifact_dir", "get_display_name", "get_description",
        "get_labels", "get_serving_container_uri",
    ]
    missing = [fn for fn in required_functions if not hasattr(handler, fn)]
    if missing:
        _log(f"Handler '{module_path}' incomplet — fonctions manquantes : {missing}")
        sys.exit(1)

    return handler


# ---------------------------------------------------------------------------
# UPLOAD GCS
# ---------------------------------------------------------------------------

def upload_to_gcs(artifact_dir: Path, gcs_model_dir: str,
                   credentials: service_account.Credentials) -> str:
    """Upload artifact_dir vers gs://banque-de-france-models/banque-de-france/<gcs_model_dir>/"""
    _log(f"Upload vers gs://{GCS_BUCKET}/{GCS_PREFIX}/{gcs_model_dir}/...")
    client = storage.Client(project=PROJECT_ID, credentials=credentials)

    # Bucket créé manuellement au préalable — accès direct, pas de vérification
    bucket = client.bucket(GCS_BUCKET)

    files = [f for f in artifact_dir.rglob("*") if f.is_file()]
    total = len(files)
    uploaded = 0

    for file_path in files:
        relative = file_path.relative_to(artifact_dir)
        blob_name = f"{GCS_PREFIX}/{gcs_model_dir}/{relative}"
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(file_path))
        uploaded += 1
        if uploaded % 5 == 0 or uploaded == total:
            _log(f"  {uploaded}/{total} fichiers uploadés...")

    gcs_uri = f"gs://{GCS_BUCKET}/{GCS_PREFIX}/{gcs_model_dir}"
    _log(f"Upload terminé -> {gcs_uri}")
    return gcs_uri


# ---------------------------------------------------------------------------
# VERTEX AI MODEL REGISTRY
# ---------------------------------------------------------------------------

def register_vertex(gcs_uri: str, display_name: str, description: str,
                     labels: dict, serving_container_uri: str,
                     credentials: service_account.Credentials) -> str:
    """Enregistre le modèle dans Vertex AI Model Registry (registre seul,
    aucun déploiement d'endpoint). Crée une nouvelle version si le modèle
    existe déjà (même display_name)."""
    _log("Enregistrement Vertex AI Model Registry...")

    aiplatform.init(project=PROJECT_ID, location=VERTEX_REGION, credentials=credentials)

    existing = aiplatform.Model.list(
        filter=f'display_name="{display_name}"',
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
        display_name=display_name,
        description=description,
        artifact_uri=gcs_uri,
        serving_container_image_uri=serving_container_uri,
        labels=labels,
        project=PROJECT_ID,
        location=VERTEX_REGION,
        credentials=credentials,
        parent_model=parent_model,
    )

    resource_name = model.resource_name
    _log(f"Modèle enregistré -> {resource_name}")
    return resource_name


# ---------------------------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Register Banque de France models -> Vertex AI")
    parser.add_argument(
        "--model", required=True, choices=list(AVAILABLE_HANDLERS.keys()),
        help="Type de modèle à enregistrer",
    )
    args = parser.parse_args()

    _log(f"=== Register Banque de France — {args.model} -> Vertex AI ===")
    start = time.time()

    handler = _load_handler(args.model)

    artifact_dir = handler.get_artifact_dir()
    if not artifact_dir.exists():
        _log(f"{artifact_dir} introuvable — lancer l'entraînement final de '{args.model}' d'abord.")
        sys.exit(1)

    display_name = handler.get_display_name()
    description = handler.get_description()
    labels = handler.get_labels()
    serving_container_uri = handler.get_serving_container_uri()

    credentials = _get_credentials()

    gcs_uri = upload_to_gcs(artifact_dir, args.model, credentials)
    resource_name = register_vertex(
        gcs_uri, display_name, description, labels, serving_container_uri, credentials,
    )

    vertex_model_id_file = artifact_dir / "vertex_model_id.txt"
    with open(vertex_model_id_file, "w") as f:
        f.write(resource_name)
    _log(f"Model ID sauvegardé -> {vertex_model_id_file}")

    elapsed = time.time() - start
    minutes, seconds = int(elapsed // 60), int(elapsed % 60)
    _log(f"=== Enregistrement terminé en {minutes}m {seconds}s ===")
    _log(f"Resource : {resource_name}")


if __name__ == "__main__":
    main()
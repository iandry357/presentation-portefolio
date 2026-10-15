import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "vrai", "oui")


# GCP / BigQuery
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "gen-lang-client-0989575872")
BQ_LOCATION = os.environ.get("BQ_LOCATION", "EU")
BQ_DATASET_SOURCE = os.environ.get("BQ_DATASET_SOURCE", "emploi_marche")  # lecture seule
BQ_DATASET = os.environ.get("BQ_DATASET", "top_offres")  # toutes les écritures
GOOGLE_APPLICATION_CREDENTIALS = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

# GCS — liste des entreprises exclues (tableau JSON)
GCS_BUCKET = os.environ.get("GCS_BUCKET", "portfolio-emploi-config")
EXCLUDED_BLOB = os.environ.get("EXCLUDED_BLOB", "excluded_companies.json")

# PostgreSQL prod (utilisateur lecture seule)
PG_HOST = os.environ["PG_HOST"]
PG_PORT = int(os.environ["PG_PORT"])
PG_DB = os.environ["PG_DB"]
PG_USER = os.environ["PG_USER"]
PG_PASSWORD = os.environ["PG_PASSWORD"]

# LLM local (Ollama)
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11434")
MODELE_SCORING = os.environ.get("MODELE_SCORING", "")  # à fixer après benchmark (D7)
MODELE_CIBLES = os.environ.get("MODELE_CIBLES", "gemma3:12b")
MODELE_SECTEUR = os.environ.get("MODELE_SECTEUR", "mistral:latest")
THINKING_SCORING = _bool("THINKING_SCORING", False)
TAILLE_LOT_LLM = int(os.environ.get("TAILLE_LOT_LLM", "20"))

# Embeddings — service OVH existant (via l'orchestrateur wake-on-demand)
OVH_ML_HOST = os.environ.get("OVH_ML_HOST", "51.68.130.23")
OVH_ORCHESTRATOR_PORT = os.environ.get("OVH_ORCHESTRATOR_PORT", "8080")
EMBEDDING_PORT = os.environ.get("EMBEDDING_PORT", "8004")
EMBEDDING_SERVICE_KEY = os.environ.get("EMBEDDING_SERVICE_KEY", "embedding-service")
ORCHESTRATOR_BASE_URL = f"http://{OVH_ML_HOST}:{OVH_ORCHESTRATOR_PORT}"
EMBEDDING_URL = f"http://{OVH_ML_HOST}:{EMBEDDING_PORT}"
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "paraphrase-multilingual-mpnet-base-v2")
EMBEDDING_DIMENSIONS = int(os.environ.get("EMBEDDING_DIMENSIONS", "768"))
TAILLE_LOT_EMBED = int(os.environ.get("TAILLE_LOT_EMBED", "50"))
WAKE_TIMEOUT_SECONDS = int(os.environ.get("WAKE_TIMEOUT_SECONDS", "120"))
WAKE_POLL_INTERVAL_SECONDS = 2

# Seuils des listes (provisoires, D4) — passés à dbt en variables
SEUIL_HAUT = int(os.environ.get("SEUIL_HAUT", "70"))
SEUIL_BAS = int(os.environ.get("SEUIL_BAS", "45"))
APPLIQUER_EXCLUSIONS = _bool("APPLIQUER_EXCLUSIONS", True)

# Pipeline
TAUX_ERREUR_LLM_MAX = float(os.environ.get("TAUX_ERREUR_LLM_MAX", "0.05"))
DERNIERS_JOURS_DEFAUT = int(os.environ.get("DERNIERS_JOURS_DEFAUT", "30"))
CACHE_ENTREPRISE_JOURS = int(os.environ.get("CACHE_ENTREPRISE_JOURS", "90"))
MAX_APPELS_API_PAR_RUN = int(os.environ.get("MAX_APPELS_API_PAR_RUN", "200"))
MAX_RECHERCHES_WEB_PAR_RUN = int(os.environ.get("MAX_RECHERCHES_WEB_PAR_RUN", "50"))
NB_ESSAIS_SECTEUR_MAX = int(os.environ.get("NB_ESSAIS_SECTEUR_MAX", "3"))
PAUSE_RECHERCHE_WEB_SECONDS = float(os.environ.get("PAUSE_RECHERCHE_WEB_SECONDS", "3"))

# Chemins (racine du MVP = /app dans le conteneur)
RESULTS_DIR = BASE_DIR / "results"
PROMPTS_DIR = BASE_DIR / "agents" / "prompts"
DBT_DIR = BASE_DIR / "dbt"

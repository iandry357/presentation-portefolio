"""
config.py

Configuration centralisée du pipeline gestion-patrimoine.
Toutes les variables d'environnement et constantes partagées entre les
collectors/loaders/transformation vivent ici, sur le pattern des autres
MVPs du portfolio.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# API PISTE / Légifrance
# ---------------------------------------------------------------------------

PISTE_ENV = os.getenv("PISTE_ENV", "sandbox")
PISTE_CLIENT_ID = os.getenv("PISTE_CLIENT_ID")
PISTE_CLIENT_SECRET = os.getenv("PISTE_CLIENT_SECRET")

CODE_CIBLE = "Code général des impôts"
CODE_TEXT_ID = "LEGITEXT000006069577"  # confirmé via test_piste_connection.py

# Nom de la facette utilisée par /search pour filtrer sur un code précis.
# Conservé pour référence, mais /search n'est plus utilisé pour la collecte
# finale (couverture partielle non exploitable, voir table_matieres).
CODE_FACETTE_NAME = "NOM_CODE"

PAGE_SIZE = 20
MAX_PAGES_PAR_MOT_CLE = 5  # garde-fou pour éviter un run qui part en boucle
DELAI_ENTRE_APPELS_SEC = 0.5  # politesse envers l'API

# ---------------------------------------------------------------------------
# Thématiques et mots-clés (v1, validés avec Ian'ch)
# ---------------------------------------------------------------------------

THEMATIQUES = {
    "donations_successions": [
        "mutation à titre gratuit",
        "donation",
        "succession",
        "droits de mutation",
    ],
    "ifi": [
        "impôt sur la fortune immobilière",
        "fortune immobilière",
    ],
    "plus_values": [
        "plus-value",
        "plus-values",
    ],
    "assurance_vie": [
        "assurance-vie",
        "assurance sur la vie",
    ],
    "per": [
        "plan d'épargne retraite",
        "épargne retraite",
    ],
}

# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

SEUIL_MOTS_SOUS_DECOUPAGE = 500

# ---------------------------------------------------------------------------
# BigQuery
# ---------------------------------------------------------------------------

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "gen-lang-client-0989575872")
BQ_DATASET = "referentiel_patrimoine"
BQ_TABLE_ARTICLES = "articles_cgi"

GCP_SA_KEY_PATH = os.getenv(
    "GCP_SA_KEY_PATH",
    os.path.join(os.path.dirname(__file__), "..", "gcp_sa_gestion_patrimoine.json"),
)

# ---------------------------------------------------------------------------
# ChromaDB
# ---------------------------------------------------------------------------

CHROMA_HOST = os.getenv("CHROMA_HOST", "51.68.130.23")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_COLLECTION = "referentiel_patrimoine"
CHROMA_USER = os.getenv("CHROMA_USER")
CHROMA_PASSWORD = os.getenv("CHROMA_PASSWORD")

# ---------------------------------------------------------------------------
# Orchestrateur OVH (wake-on-demand) — appelé directement par le pipeline
# ---------------------------------------------------------------------------

OVH_ORCHESTRATOR_URL = os.getenv("OVH_ORCHESTRATOR_URL", "http://51.68.130.23:8080")
EMBEDDING_SERVICE_KEY = "embedding-service"  # clé partagée dans registry.yaml
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://51.68.130.23:8004")

WAKE_TIMEOUT_SEC = 120
WAKE_POLL_INTERVAL_SEC = 3

# ---------------------------------------------------------------------------
# Chemins de sortie intermédiaires
# ---------------------------------------------------------------------------

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
RAW_ARTICLES_PATH = os.path.join(DATA_DIR, "raw_articles.json")
CHUNKS_PATH = os.path.join(DATA_DIR, "chunks.json")

os.makedirs(DATA_DIR, exist_ok=True)
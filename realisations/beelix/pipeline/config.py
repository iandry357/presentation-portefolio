"""
Configuration du pipeline Beelix — signaux de prospection pour une commerciale.
Sources : Google News (vitrine) et offres déjà collectées (emploi_marche, top_offres).
Aucune collecte du site : robots.txt de beelix.fr = Disallow / (exploration du 2026-11-20).
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# GCP / BigQuery
GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
GCP_SA_KEY_PATH = BASE_DIR / os.environ["GCP_SA_KEY_PATH"]
BQ_DATASET = os.environ["BQ_DATASET"]           # beelix_veille
BQ_TABLE_NEWS = "articles_bruts"
BQ_TABLE_OFFRES = "offres_signaux"              # remplacée à chaque run (fenêtre glissante)

# Tables sources (lecture seule)
BQ_SRC_MART = f"{GCP_PROJECT_ID}.top_offres.mart_top_du_jour"
BQ_SRC_ENTREPRISES = f"{GCP_PROJECT_ID}.top_offres.entreprises_ref"
BQ_SRC_OFFRES = f"{GCP_PROJECT_ID}.emploi_marche.stg_offres"

# ChromaDB
CHROMA_HOST = os.environ["CHROMA_HOST"]
CHROMA_PORT = int(os.environ["CHROMA_PORT"])
CHROMA_USER = os.environ["CHROMA_USER"]
CHROMA_PASSWORD = os.environ["CHROMA_PASSWORD"]
CHROMA_COLLECTION = os.environ["CHROMA_COLLECTION"]   # beelix_veille

# Embeddings — Embedding Service OVH (paraphrase-multilingual-mpnet-base-v2, dim 768)
OVH_ML_HOST = os.environ.get("OVH_ML_HOST", "51.68.130.23")
OVH_ORCHESTRATOR_PORT = os.environ.get("OVH_ORCHESTRATOR_PORT", "8080")
EMBEDDING_SERVICE_PORT = os.environ.get("EMBEDDING_SERVICE_PORT", "8004")
EMBEDDING_DIMENSIONS = 768

# Google News (5 articles au 2026-11-20, aucun sur un an : pas de filtre de date)
RSS_FEEDS = [
    {
        "name": "beelix_fr",
        "url": "https://news.google.com/rss/search?q=%22Beelix%22&hl=fr&gl=FR&ceid=FR:fr",
        "max_articles": 100,
    },
]

# Offres
FENETRE_JOURS = 90                    # sur date_collecte, offres représentantes du mart Top Offres
BEELIX_NOM_NORMALISE = "beelix"       # entreprise_normalise du mart : repère Beelix parmi la concurrence
LONGUEUR_MIN_DESCRIPTION = 1000       # au-delà : texte complet dans la fiche (France Travail API)

# Secteurs : préfixe du code NAF (format « 62.02A ») -> secteur ; le préfixe le plus long l'emporte.
SECTEURS_NAF = {
    # Banque / Finance / Assurance
    "64": "banque_finance_assurance",
    "65": "banque_finance_assurance",
    "66": "banque_finance_assurance",
    # Énergie (production et distribution, extraction, raffinage)
    "35": "energie",
    "06": "energie",
    "19": "energie",
    # Automobile (construction ; commerce et réparation, division 45, laissés en « autre »)
    "29": "automobile",
    # Médias / Télécoms (58.2 = édition de logiciels, exclue)
    "58.1": "medias_telecoms",
    "59": "medias_telecoms",
    "60": "medias_telecoms",
    "61": "medias_telecoms",
    "63.91": "medias_telecoms",
    # Défense
    "25.40": "defense",
    "30.30": "defense",
    "30.40": "defense",
    "84.22": "defense",
    # Luxe / Retail
    "14": "luxe_retail",
    "15": "luxe_retail",
    "20.42": "luxe_retail",
    "32.12": "luxe_retail",
    "32.13": "luxe_retail",
    "46.42": "luxe_retail",
    "46.45": "luxe_retail",
    "46.48": "luxe_retail",
    "47": "luxe_retail",
    # Concurrence : ESN, conseil, ingénierie (Beelix est en 70.22Z)
    "62": "concurrence",
    "63.11": "concurrence",
    "70.22": "concurrence",
    "71.12": "concurrence",
    # Intermédiaires de l'emploi (placement, intérim, portage)
    "78": "intermediaire",
}
SECTEUR_AUTRE = "autre"                  # code NAF présent mais hors table
SECTEUR_NON_CLASSE = "non_classe"        # code NAF absent
SECTEUR_INTERMEDIAIRE = "intermediaire"  # aussi quand le mart indique type_entreprise = cabinet_recrutement

SECTEURS_LIBELLES = {
    "banque_finance_assurance": "Banque, Finance, Assurance",
    "energie": "Énergie",
    "automobile": "Automobile",
    "medias_telecoms": "Médias et Télécoms",
    "defense": "Défense",
    "luxe_retail": "Luxe et Retail",
    "concurrence": "Concurrence (ESN, conseil, ingénierie)",
    "intermediaire": "Intermédiaires de l'emploi",
    "autre": "Autres secteurs",
    "non_classe": "Non classées (NAF inconnu)",
}

SECTEURS_BEELIX = [
    "banque_finance_assurance",
    "energie",
    "automobile",
    "medias_telecoms",
    "defense",
    "luxe_retail",
]
SECTEURS_RAG = SECTEURS_BEELIX + ["concurrence"]   # offres indexées dans ChromaDB

# Trafilatura (Google News)
TRAFILATURA_TIMEOUT = 10
TRAFILATURA_MAX_RETRIES = 2

# Pipeline
PIPELINE_BATCH_SIZE = 10
PIPELINE_ENV = os.environ.get("PIPELINE_ENV", "local")

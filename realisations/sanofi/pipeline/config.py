"""
Configuration centralisée du pipeline Sanofi.
Toutes les variables sont lues depuis .env — aucune magic string ailleurs.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Charge le .env depuis la racine de realisations/sanofi/
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


# ─────────────────────────────────────────
# GCP / BigQuery
# ─────────────────────────────────────────
GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
GCP_SA_KEY_PATH = BASE_DIR / os.environ["GCP_SA_KEY_PATH"]

BQ_DATASET_CLINICAL_TRIALS = os.environ["BQ_DATASET_CLINICAL_TRIALS"]
BQ_DATASET_PUBMED = os.environ["BQ_DATASET_PUBMED"]
BQ_DATASET_NEWS = os.environ["BQ_DATASET_NEWS"]

BQ_TABLE_CLINICAL_TRIALS = "raw_studies"
BQ_TABLE_PUBMED = "raw_articles"
BQ_TABLE_NEWS = "raw_news"

# ─────────────────────────────────────────
# ChromaDB
# ─────────────────────────────────────────
CHROMA_HOST = os.environ["CHROMA_HOST"]
CHROMA_PORT = int(os.environ["CHROMA_PORT"])
CHROMA_USER = os.environ["CHROMA_USER"]
CHROMA_PASSWORD = os.environ["CHROMA_PASSWORD"]

CHROMA_COLLECTION_CLINICAL_TRIALS = os.environ["CHROMA_COLLECTION_CLINICAL_TRIALS"]
CHROMA_COLLECTION_PUBMED = os.environ["CHROMA_COLLECTION_PUBMED"]
CHROMA_COLLECTION_NEWS = os.environ["CHROMA_COLLECTION_NEWS"]

# ─────────────────────────────────────────
# VoyageAI
# ─────────────────────────────────────────
VOYAGE_API_KEY = os.environ["VOYAGE_API_KEY"]
VOYAGE_EMBEDDING_MODEL = os.environ["VOYAGE_EMBEDDING_MODEL"]
VOYAGE_EMBEDDING_DIMENSIONS = int(os.environ["VOYAGE_EMBEDDING_DIMENSIONS"])

# ─────────────────────────────────────────
# LLM
# ─────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# ─────────────────────────────────────────
# Sources collecteurs
# ─────────────────────────────────────────
CLINICAL_TRIALS_BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
CLINICAL_TRIALS_QUERY = "Sanofi"
CLINICAL_TRIALS_MAX_RESULTS = 200

PUBMED_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PUBMED_QUERY = "Sanofi"
PUBMED_MAX_RESULTS = 100
PUBMED_DATE_FROM = "2024/01/01"

GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search?q=Sanofi+IA+Data&hl=fr&gl=FR&ceid=FR:fr"
GOOGLE_NEWS_MAX_RESULTS = 50

# ─────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────
PIPELINE_ENV = os.environ.get("PIPELINE_ENV", "local")
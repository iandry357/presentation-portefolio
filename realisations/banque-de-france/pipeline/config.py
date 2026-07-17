import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# GCP / BigQuery
GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
GCP_SA_KEY_PATH = BASE_DIR / os.environ["GCP_SA_KEY_PATH"]
BQ_DATASET = os.environ["BQ_DATASET"]
BQ_TABLE_NEWS = "articles_bruts"

# ChromaDB
CHROMA_HOST = os.environ["CHROMA_HOST"]
CHROMA_PORT = int(os.environ["CHROMA_PORT"])
CHROMA_USER = os.environ["CHROMA_USER"]
CHROMA_PASSWORD = os.environ["CHROMA_PASSWORD"]
CHROMA_COLLECTION = os.environ["CHROMA_COLLECTION"]

# Embeddings — sentence-transformers (local, no API key)
EMBEDDING_MODEL = "paraphrase-multilingual-mpnet-base-v2"
EMBEDDING_DIMENSIONS = 768

# LLM
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# RSS Sources — veille Banque de France / ACPR (2 flux séparés)
RSS_FEEDS = [
    {
        "name": "banque_de_france_actualites",
        "url": "https://news.google.com/rss/search?q=%22Banque+de+France%22+actualit%C3%A9s&hl=fr&gl=FR&ceid=FR:fr",
        "max_articles": 50,
    },
    {
        "name": "acpr_sanctions",
        "url": "https://news.google.com/rss/search?q=ACPR+%22Commission+des+sanctions%22&hl=fr&gl=FR&ceid=FR:fr",
        "max_articles": 50,
    },
]

# ACPR — Recueil des sanctions (page unique, pas de pagination)
ACPR_RECUEIL_URL = "https://acpr.banque-france.fr/fr/reglementation/recueil-des-sanctions"

# Cache local des décisions ACPR déjà traitées — persistant via volume Docker
ACPR_CACHE_PATH = BASE_DIR / "data" / "acpr_processed.json"

# Trafilatura
TRAFILATURA_TIMEOUT = 10
TRAFILATURA_MAX_RETRIES = 2

# Pipeline
PIPELINE_BATCH_SIZE = 10
PIPELINE_ENV = os.environ.get("PIPELINE_ENV", "local")
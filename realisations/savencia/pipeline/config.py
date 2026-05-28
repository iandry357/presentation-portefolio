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

# VoyageAI
VOYAGE_API_KEY = os.environ["VOYAGE_API_KEY"]
VOYAGE_EMBEDDING_MODEL = os.environ["VOYAGE_EMBEDDING_MODEL"]
VOYAGE_EMBEDDING_DIMENSIONS = int(os.environ["VOYAGE_EMBEDDING_DIMENSIONS"])

# LLM
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# RSS Sources
RSS_FEEDS = [
    {
        "name": "savencia_news",
        "url": "https://news.google.com/rss/search?q=Savencia&hl=fr&gl=FR&ceid=FR:fr",
        "max_articles": 50,
    },
    {
        "name": "agroalimentaire_ia",
        "url": "https://news.google.com/rss/search?q=agroalimentaire+IA+data+science+France&hl=fr&gl=FR&ceid=FR:fr",
        "max_articles": 50,
    },
]

# Trafilatura
TRAFILATURA_TIMEOUT = 10
TRAFILATURA_MAX_RETRIES = 2

# Pipeline
PIPELINE_BATCH_SIZE = 10
PIPELINE_ENV = os.environ.get("PIPELINE_ENV", "local")
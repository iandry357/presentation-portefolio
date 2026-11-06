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

# Embeddings — Embedding Service OVH (paraphrase-multilingual-mpnet-base-v2, dim 768)
OVH_ML_HOST = os.environ.get("OVH_ML_HOST", "51.68.130.23")
OVH_ORCHESTRATOR_PORT = os.environ.get("OVH_ORCHESTRATOR_PORT", "8080")
EMBEDDING_SERVICE_PORT = os.environ.get("EMBEDDING_SERVICE_PORT", "8004")
EMBEDDING_DIMENSIONS = 768

# RSS Sources
RSS_FEEDS = [
    {
        "name": "sqli_news",
        "url": "https://news.google.com/rss/search?q=%22SQLI%22+digital+when%3A1y&hl=fr&gl=FR&ceid=FR:fr",
        "max_articles": 100,
    },
    {
        "name": "sqli_fr",
        "url": "https://news.google.com/rss/search?q=%22SQLI%22&hl=fr&gl=FR&ceid=FR:fr",
        "max_articles": 100,
    },
    {
        "name": "sqli_group_en",
        "url": "https://news.google.com/rss/search?q=%22SQLI+Group%22&hl=en&gl=US&ceid=US:en",
        "max_articles": 100,
    },
    {
        "name": "sqli_agency_en",
        "url": "https://news.google.com/rss/search?q=%22SQLI%22+digital+agency&hl=en&gl=US&ceid=US:en",
        "max_articles": 100,
    },
]

# Site SQLI (sitemap)
# Site SQLI : première page de chaque liste seulement (/*?page=* est interdit par robots.txt)
SITE_BASE_URL = "https://www.sqli.com"
SITE_REQUEST_DELAY = 1.0   # secondes entre deux pages
SITE_USER_AGENT = "portfolio-cv-bot/1.0"

# Groupes : page de liste -> liens d'articles dans l'ordre de la page, plafond par groupe
SITE_GROUPS = [
    {
        "name": "actualites_en",
        "list_url": "/int-en/news-events",
        "link_prefixes": ["/int-en/news-events/", "/int-en/actualites-evenements/", "/int-en/insights/"],
        "max_pages": 12,
        "dated": True,
    },
    {
        "name": "actualites_fr",
        "list_url": "/fr-fr/actualites-evenements",
        "link_prefixes": ["/fr-fr/actualites-evenements/", "/fr-fr/news-events/", "/fr-fr/insights/"],
        "max_pages": 12,
        "dated": True,
    },
    {
        "name": "cas_clients",
        "list_url": "/fr-fr/cas-clients",
        "link_prefixes": ["/fr-fr/cas-clients/", "/fr-fr/case-studies/"],
        "max_pages": 15,
        "dated": False,
    },
]

# Pages fixes : une URL = un document
SITE_PAGES = [
    {"name": "expertise_data_ai", "url": "/fr-fr/expertise/data-ai", "dated": False},
]



# Trafilatura
TRAFILATURA_TIMEOUT = 10
TRAFILATURA_MAX_RETRIES = 2

# Pipeline
PIPELINE_BATCH_SIZE = 10
PIPELINE_ENV = os.environ.get("PIPELINE_ENV", "local")

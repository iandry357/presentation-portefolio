"""
Configuration du pipeline Wavestone — veille entreprise et signaux de recrutement (POC cooptation).
Sources : site wavestone.com (sitemaps Yoast, FR et EN), Google News (presse), offres déjà collectées (top_offres).
robots.txt du 2026-11-20 : seuls /wp-json/ et /?rest_route= sont interdits ; aucune API WordPress utilisée.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# GCP / BigQuery
GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
GCP_SA_KEY_PATH = BASE_DIR / os.environ["GCP_SA_KEY_PATH"]
BQ_DATASET = os.environ["BQ_DATASET"]           # wavestone_veille
BQ_TABLE_NEWS = "articles_bruts"                # site + presse, ajout avec dédoublonnage
BQ_TABLE_OFFRES = "offres_wavestone"            # remplacée à chaque run (fenêtre glissante)

# Tables sources (lecture seule)
BQ_SRC_MART = f"{GCP_PROJECT_ID}.top_offres.mart_top_du_jour"
BQ_SRC_ENTREPRISES = f"{GCP_PROJECT_ID}.top_offres.entreprises_ref"
BQ_SRC_OFFRES = f"{GCP_PROJECT_ID}.emploi_marche.stg_offres"
BQ_SRC_CIBLES = f"{GCP_PROJECT_ID}.top_offres.cibles"   # intitulés des métiers cibles (cible_id -> intitule)

# ChromaDB
CHROMA_HOST = os.environ["CHROMA_HOST"]
CHROMA_PORT = int(os.environ["CHROMA_PORT"])
CHROMA_USER = os.environ["CHROMA_USER"]
CHROMA_PASSWORD = os.environ["CHROMA_PASSWORD"]
CHROMA_COLLECTION = os.environ["CHROMA_COLLECTION"]   # wavestone_veille

# Embeddings — Embedding Service OVH (paraphrase-multilingual-mpnet-base-v2, dim 768)
OVH_ML_HOST = os.environ.get("OVH_ML_HOST", "51.68.130.23")
OVH_ORCHESTRATOR_PORT = os.environ.get("OVH_ORCHESTRATOR_PORT", "8080")
EMBEDDING_SERVICE_PORT = os.environ.get("EMBEDDING_SERVICE_PORT", "8004")
EMBEDDING_DIMENSIONS = 768

# Google News (exploration du 2026-11-20 : FR 52 articles sur un an, EN 45 ; ~75 % viennent de wavestone.com)
RSS_FEEDS = [
    {
        "name": "wavestone_fr",
        "url": "https://news.google.com/rss/search?q=Wavestone&hl=fr&gl=FR&ceid=FR:fr",
        "max_articles": 100,
    },
    {
        "name": "wavestone_en",
        "url": "https://news.google.com/rss/search?q=Wavestone&hl=en-US&gl=US&ceid=US:en",
        "max_articles": 100,
    },
]
# Sources écartées : déjà collectées directement sur le site (évite les doublons RAG / LDA)
RSS_SOURCES_EXCLUES = ["https://www.wavestone.com"]

# Site Wavestone (sitemaps Yoast : FR, EN et DE mélangés dans chaque sous-sitemap)
SITE_BASE_URL = "https://www.wavestone.com"
SITE_REQUEST_DELAY = 1.0   # secondes entre deux pages (pas de Crawl-delay déclaré)
SITE_USER_AGENT = "portfolio-cv-bot/1.0"
SITE_LANGUES = ["fr", "en"]   # premier segment du chemin ; /de/ écarté

# Sections : sous-sitemap -> URL gardées si le chemin commence par /<langue>/<segment>/
SITE_SECTIONS = [
    {"name": "news", "sitemap": "/news-sitemap.xml", "segment": "news"},
    {"name": "insight", "sitemap": "/insight-sitemap.xml", "segment": "insight"},
    {"name": "clients_story", "sitemap": "/clients-story-sitemap.xml", "segment": "clients-story"},
]
# capability-sitemap.xml écarté : ses URL FR et EN répondent 404 (contrôle du 2026-11-20, sitemap périmé)
# Plafond de pages par section et par langue (0 = pas de plafond) ; mettre 5 pour un test local
SITE_MAX_PAGES_PAR_SECTION = int(os.environ.get("SITE_MAX_PAGES_PAR_SECTION", "0"))
# Incrémental : une URL déjà présente en base (articles_bruts) n'est pas recollectée ; seules les nouvelles pages entrent
SITE_INCREMENTAL = True

# Bruit restant après extraction : le texte est coupé au premier marqueur de fin trouvé,
# les fragments sont supprimés. Marqueurs relevés le 2026-11-20 (pages HTML puis contrôle du premier run).
SITE_MARQUEURS_FIN = [
    "Vous souhaitez échanger avec nous",
    "Andere Inhalte erkunden",
    "Partager ce contenu",
    # Cas clients (FR / EN)
    "Explorez nos expertises",
    "Découvrez notre expertise",
    "Rencontrez les experts",
    "Autres succès clients",
    "Autres réussites clients",
    "Notre expert:",
    "Explore our expertise",
    "Meet the experts behind",
    "Other client successes",
    "Our Expert:",
    # Paragraphe standard des communiqués (identique partout : bruit pour la LDA)
    "A propos de Wavestone",
    "À propos de Wavestone",
    "About Wavestone",
]
SITE_FRAGMENTS_A_SUPPRIMER = ["Link copied"]

# Offres (mart Top Offres)
FENETRE_JOURS = 90                                    # sur date_collecte, offres représentantes
WAVESTONE_NOMS_NORMALISES = ["wavestone", "wavestone1"]   # variantes de entreprise_normalise
LONGUEUR_MIN_DESCRIPTION = 1000                       # au-delà : texte complet dans la fiche

# Trafilatura
TRAFILATURA_TIMEOUT = 10
TRAFILATURA_MAX_RETRIES = 2

# Pipeline
PIPELINE_BATCH_SIZE = 10
PIPELINE_ENV = os.environ.get("PIPELINE_ENV", "local")

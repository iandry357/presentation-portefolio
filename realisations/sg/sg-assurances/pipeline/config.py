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

# PDF Sources
PDF_SOURCES = [
    {
        "name": "cg_auto",
        "url": "https://particuliers.sg.fr/static/Particuliers/Medias/Home/PDF/Auto_CG_SGRF_DOM_SOGESSUR_DocCliCont.pdf",
        "doc_type": "conditions_generales",
    },
    {
        "name": "cg_habitation_2026",
        "url": "https://static.sg.fr/bigfiles/pri/MRH_CG_G190315_DEMAT_17102025_A.pdf",
        "doc_type": "conditions_generales",
    },
    {
        "name": "cg_protection_juridique",
        "url": "https://particuliers.sg.fr/static/Particuliers/Medias/Home/PDF/CG_PJ_mars_24.pdf",
        "doc_type": "conditions_generales",
    },
    {
        "name": "reperes_2023",
        "url": "https://www.assurances.societegenerale.com/fileadmin/2023/Reperes/2024/Reperes_2023.pdf",
        "doc_type": "rapport_annuel",
    },
    {
        "name": "dic_garantie_obseques",
        "url": "https://www.assurances.societegenerale.com/fileadmin/user_upload/pdf/DIC_Garantie__Obs%C3%A8ques_Vf.pdf",
        "doc_type": "dic",
    },
    {
        "name": "ipid_deces_accidentel",
        "url": "https://www.assurances.societegenerale.com/fileadmin/2023/IPID/Antarius/IPID_S%C3%A9curit%C3%A9_12.pdf",
        "doc_type": "ipid",
    },
    {
        "name": "sfcr_sogessur_2021",
        "url": "https://www.assurances.societegenerale.com/uploads/tx_bisgnews/SFCR_SOGESSUR_2021_VF.pdf",
        "doc_type": "sfcr",
    },
]

# RSS Sources
RSS_FEEDS = [
    {
        "name": "sg_assurances_ia_data",
        "url": "https://news.google.com/rss/search?q=Soci%C3%A9t%C3%A9+G%C3%A9n%C3%A9rale+Assurances+IA+Data&hl=fr&gl=FR&ceid=FR:fr",
        "max_articles": 50,
    },
]

# Trafilatura
TRAFILATURA_TIMEOUT = 10
TRAFILATURA_MAX_RETRIES = 2

# Pipeline
PIPELINE_BATCH_SIZE = 10
PIPELINE_ENV = os.environ.get("PIPELINE_ENV", "local")
from pydantic_settings import BaseSettings
from typing import Optional
import os
from pydantic import Field


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: int = 5433

    # AI Services
    VOYAGE_API_KEY: str
    MISTRAL_API_KEY: str
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: str = "portfolio-rag"
    SERPER_API_KEY: str = ""

    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    COMPANY_BROWSE_MAX_CHARS: int = 4000

    # App Config
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = "INFO"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    SECRET_KEY: str

    CORS_ORIGINS: str = Field(default="", env="CORS_ORIGINS")

    # RAG Config
    EMBEDDING_MODEL: str = "voyage-4"
    EMBEDDING_DIMENSIONS: int = 1024
    RETRIEVAL_TOP_K: int = 10
    RETRIEVAL_SCORE_THRESHOLD: float = 0.13

    # Scaleway Cockpit
    # COCKPIT_TOKEN: str
    # COCKPIT_LOGS_URL: str

    FRANCE_TRAVAIL_CLIENT_ID: str = ""
    FRANCE_TRAVAIL_CLIENT_SECRET: str = ""
    
    USER_AGENT: str = "portfolio-cv-bot/1.0"

    cv_edit_secret_code: str = Field(default="dev123")

    gmail_client_id: Optional[str] = None
    gmail_client_secret: Optional[str] = None
    gmail_refresh_token: Optional[str] = None

    GCP_SERVICE_ACCOUNT_JSON: Optional[str] = None
    BQ_PROJECT_ID: str = "gen-lang-client-0989575872"
    BQ_DATASET: str = "emploi_marche"
    BQ_TABLE: str = "offres_brutes"

    # ─── Sanofi ───────────────────────────────────────────────
    GCP_SA_KEY_PATH_SANOFI: str = "realisations/sanofi/gcp_sa_sanofi.json"
    GCP_SERVICE_ACCOUNT_JSON_SANOFI: Optional[str] = None

    BQ_DATASET_SANOFI_CLINICAL_TRIALS: str = "sanofi_clinical_trials"
    BQ_DATASET_SANOFI_PUBMED: str = "sanofi_pubmed"
    BQ_DATASET_SANOFI_NEWS: str = "sanofi_news"

    CHROMA_HOST: str = "portefolio-chromadb"
    CHROMA_PORT: int = 8000
    CHROMA_USER: str = "portefolio"
    CHROMA_PASSWORD: str = ""

    CHROMA_COLLECTION_SANOFI_CLINICAL_TRIALS: str = "sanofi_clinical_trials"
    CHROMA_COLLECTION_SANOFI_PUBMED: str = "sanofi_pubmed"
    CHROMA_COLLECTION_SANOFI_NEWS: str = "sanofi_news"

    CHROMA_COLLECTION_SANOFI_PRESS_RELEASES: str = os.getenv("CHROMA_COLLECTION_SANOFI_PRESS_RELEASES", "sanofi_press_releases")

    GCP_SERVICE_ACCOUNT_JSON_SAVENCIA: str = ""
    CHROMA_COLLECTION_SAVENCIA: str = "savencia_veille"
    OVH_ML_PORT_SAVENCIA: str = "8002"

    # ─── SG Assurances ────────────────────────────────────────
    GCP_SERVICE_ACCOUNT_JSON_SG: Optional[str] = None
    CHROMA_COLLECTION_SG: str = "sg_assurances_news"
    OVH_ML_PORT_SG: str = "8003"
    EMBEDDING_SERVICE_PORT: str = "8004"

    VOYAGE_EMBEDDING_MODEL: str = "voyage-4"
    VOYAGE_EMBEDDING_DIMENSIONS: int = 1024


    @property
    def is_dev(self) -> bool:
        return self.ENVIRONMENT == "development"

    class Config:
        # env_file = ".env"
        env_file = ".env" if os.path.exists(".env") else None
        case_sensitive = False


settings = Settings()
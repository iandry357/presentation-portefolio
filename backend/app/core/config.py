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

    # App Config
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = "INFO"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    SECRET_KEY: str

    CORS_ORIGINS: str = Field(default="", env="CORS_ORIGINS")

    # RAG Config
    EMBEDDING_MODEL: str = "voyage-3"
    EMBEDDING_DIMENSIONS: int = 1024
    RETRIEVAL_TOP_K: int = 10
    RETRIEVAL_SCORE_THRESHOLD: float = 0.13

    # Historique conversationnel
    HISTORY_LIMIT_MESSAGES: int = 4  # 2 Q-A = 4 messages
    HISTORY_TRUNCATE_THRESHOLD: int = 1000  # tokens
    HISTORY_TRUNCATE_MAX: int = 400  # tokens

    class Config:
        # env_file = ".env"
        env_file = ".env" if os.path.exists(".env") else None
        case_sensitive = False


settings = Settings()
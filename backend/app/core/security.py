from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings


def setup_cors(app: FastAPI) -> None:
    """
    Configure CORS middleware for the application
    """
    # Allowed origins
    origins = [
        "http://localhost:3000",  # Next.js dev
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "https://presentation-portefolio.vercel.app",
    ]
    
    # Add production origins if not in development
    # if settings.ENVIRONMENT == "production":
    #     origins.extend([
    #         "https://your-frontend-domain.com",
    #         "https://www.your-frontend-domain.com",
    #     ])
    if settings.ENVIRONMENT == "production":
        production_origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS else []
        origins.extend(production_origins)
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
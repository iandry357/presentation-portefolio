from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
import logging
import sys
import importlib.metadata

from app.core.database import get_db
from app.core.config import settings

router = APIRouter(prefix="/api", tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint
    Returns API status and database connectivity
    """
    try:
        result = await db.execute(text("SELECT 1"))
        db_status = "connected" if result else "disconnected"

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": db_status,
            "environment": "development"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "disconnected",
            "error": str(e)
        }


@router.get("/debug/versions")
async def debug_versions(x_secret_key: str = Header(None)):
    """
    Debug endpoint — retourne les versions des packages critiques.
    Protégé par X-Secret-Key header.
    """
    if x_secret_key != settings.SECRET_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

    packages = ["litellm", "crewai", "httpx", "pydantic", "fastapi"]
    versions = {}

    for pkg in packages:
        try:
            versions[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            versions[pkg] = "not found"

    return {
        "python": sys.version,
        "packages": versions
    }
from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.security import setup_cors
from app.routers import health, cv, chat

from app.routers.jobs import router as jobs_router

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.scheduler.job_pipeline import schedule_pipeline

from app.core.logging_config import setup_logging
setup_logging()

# Configure logging
# logging.basicConfig(
#     level=getattr(logging, settings.LOG_LEVEL),
#     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
# )
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"🚀 Starting Portfolio RAG API - Environment: {settings.ENVIRONMENT}")
    db_connected = await init_db()
    if not db_connected:
        logger.error("Failed to connect to database. Exiting...")
        raise Exception("Database connection failed")

    # Scheduler pipeline jobs (prod uniquement)
    scheduler = AsyncIOScheduler()
    if settings.ENVIRONMENT == "production":
        scheduler.add_job(schedule_pipeline, CronTrigger(hour="8,13,18"))
        scheduler.start()
        logger.info("✅ Scheduler démarré : pipeline jobs 3x/jour (8h, 13h, 18h)")
    
    yield
    
    # Shutdown
    if settings.ENVIRONMENT == "production":
        scheduler.shutdown()
    # Shutdown
    logger.info("Shutting down Portfolio RAG API...")
    await close_db()


# Create FastAPI application
app = FastAPI(
    title="Portfolio CV",
    description="AI-powered portfolio cv with RAG capabilities",
    version="0.1.0",
    lifespan=lifespan,
)

# Setup CORS
setup_cors(app)

# Include routers
app.include_router(health.router)
app.include_router(cv.router)
app.include_router(chat.router)
app.include_router(jobs_router)

@app.get("/")
async def root():
    return {
        "message": "Portfolio RAG API",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.ENVIRONMENT == "development"
    )
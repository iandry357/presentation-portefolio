import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from resource_manager import ensure_service_running
from timer_manager import start_timer, reset_timer, get_status
from docker_client import load_registry, is_running

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Orchestrateur démarré")
    yield
    logger.info("Orchestrateur arrêté")


app = FastAPI(title="OVH Orchestrator", lifespan=lifespan)


@app.post("/wake/{service_key}")
async def wake(service_key: str):
    """
    Appelé par le backend Scaleway quand un utilisateur ouvre un projet.
    Démarre le service si nécessaire et arme le timer.
    """
    registry = load_registry()
    if service_key not in registry:
        raise HTTPException(status_code=404, detail=f"Service inconnu : {service_key}")

    success = ensure_service_running(service_key)
    if not success:
        raise HTTPException(status_code=503, detail=f"Impossible de démarrer {service_key}")

    start_timer(service_key)
    return {"status": "ok", "service": service_key}


@app.post("/heartbeat/{service_key}")
async def heartbeat(service_key: str):
    """
    Appelé à chaque activité sur un service.
    Remet le timer à zéro.
    """
    registry = load_registry()
    if service_key not in registry:
        raise HTTPException(status_code=404, detail=f"Service inconnu : {service_key}")

    reset_timer(service_key)
    return {"status": "ok", "service": service_key}


@app.get("/status")
async def status():
    """
    Retourne l'état de tous les services et des timers actifs.
    """
    registry = load_registry()
    services = {
        key: {
            "running": is_running(key),
            "priority": svc["priority"],
            "mvp": svc["mvp"],
            "port": svc["port"],
            "ram_mb": svc["ram_mb"],
        }
        for key, svc in registry.items()
    }
    return {
        "services": services,
        "timers": get_status()
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
import asyncio
import logging
import os
import httpx

logger = logging.getLogger(__name__)

OVH_ML_HOST = os.getenv("OVH_ML_HOST", "51.68.130.23")
OVH_ORCHESTRATOR_PORT = os.getenv("OVH_ORCHESTRATOR_PORT", "8080")
ORCHESTRATOR_BASE_URL = f"http://{OVH_ML_HOST}:{OVH_ORCHESTRATOR_PORT}"

WAKE_TIMEOUT_SECONDS = 120
POLL_INTERVAL_SECONDS = 2

# Port health par service
SERVICE_PORTS = {
    "sanofi-ml": "8001",
    "savencia-ml": "8002",
    "sg-ml": "8003",
    "embedding-service": "8004",
    "banque-ml": "8007",
    "gestion-patrimoine-ml": "8008",
}


async def _wait_for_health(service_key: str) -> bool:
    """Poll le /health du service ML directement jusqu'à ce qu'il réponde."""
    port = SERVICE_PORTS.get(service_key)
    if not port:
        return True

    url = f"http://{OVH_ML_HOST}:{port}/health"
    elapsed = 0
    while elapsed < WAKE_TIMEOUT_SECONDS:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    logger.info(f"{service_key} health OK sur port {port}")
                    return True
        except Exception:
            pass
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        elapsed += POLL_INTERVAL_SECONDS

    return False


async def wake(service_key: str) -> None:
    """
    Démarre le service via l'orchestrateur et attend qu'il soit prêt.
    Bloquant — le premier appel ML attend que le /health réponde.
    """
    # Signal de démarrage
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            await client.post(f"{ORCHESTRATOR_BASE_URL}/wake/{service_key}")
        except Exception as e:
            logger.warning(f"Wake signal failed for {service_key}: {e}")

    # Poll /health direct sur le service ML
    ready = await _wait_for_health(service_key)
    if not ready:
        raise TimeoutError(f"Service {service_key} did not become healthy within {WAKE_TIMEOUT_SECONDS}s")

    logger.info(f"{service_key} is ready")


async def heartbeat(service_key: str) -> None:
    """Réinitialise le timer d'inactivité — fire-and-forget."""
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            await client.post(f"{ORCHESTRATOR_BASE_URL}/heartbeat/{service_key}")
    except Exception as e:
        logger.debug(f"Heartbeat failed for {service_key}: {e}")
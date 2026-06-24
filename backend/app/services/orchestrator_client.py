import asyncio
import logging
import os
import httpx

logger = logging.getLogger(__name__)

OVH_ML_HOST = os.getenv("OVH_ML_HOST", "51.68.130.23")
OVH_ORCHESTRATOR_PORT = os.getenv("OVH_ORCHESTRATOR_PORT", "8080")
ORCHESTRATOR_BASE_URL = f"http://{OVH_ML_HOST}:{OVH_ORCHESTRATOR_PORT}"

WAKE_TIMEOUT_SECONDS = 60
POLL_INTERVAL_SECONDS = 2


async def wake(service_key: str) -> None:
    """
    Démarre le service via l'orchestrateur et attend qu'il soit running.
    Bloquant — le premier appel ML attend que le service soit prêt.
    Lève une exception si timeout dépassé.
    """
    # Signal de démarrage — client séparé
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            await client.post(f"{ORCHESTRATOR_BASE_URL}/wake/{service_key}")
        except Exception as e:
            logger.warning(f"Wake signal failed for {service_key}: {e}")

    # Poll — client séparé avec timeout plus long
    elapsed = 0
    while elapsed < WAKE_TIMEOUT_SECONDS:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{ORCHESTRATOR_BASE_URL}/status")
                status = resp.json()
                if status["services"].get(service_key, {}).get("running"):
                    logger.info(f"{service_key} is running")
                    return
        except Exception as e:
            logger.warning(f"Status poll failed: {e}")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        elapsed += POLL_INTERVAL_SECONDS

    raise TimeoutError(f"Service {service_key} did not start within {WAKE_TIMEOUT_SECONDS}s")


async def heartbeat(service_key: str) -> None:
    """
    Réinitialise le timer d'inactivité — fire-and-forget.
    """
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            await client.post(f"{ORCHESTRATOR_BASE_URL}/heartbeat/{service_key}")
    except Exception as e:
        logger.debug(f"Heartbeat failed for {service_key}: {e}")
import logging
from docker_client import (
    load_registry,
    is_running,
    start_service,
    stop_service,
    get_ram_available_mb
)

logger = logging.getLogger(__name__)


def get_running_on_demand_services() -> list[str]:
    """Retourne la liste des services on-demand actuellement en cours d'exécution."""
    registry = load_registry()
    return [
        key for key, svc in registry.items()
        if svc["priority"] == "on-demand" and is_running(key)
    ]


def ensure_service_running(service_key: str) -> bool:
    """
    Point d'entrée principal.
    S'assure qu'un service est démarré, en libérant de la RAM si nécessaire.
    Retourne True si le service est opérationnel, False sinon.
    """
    registry = load_registry()

    if service_key not in registry:
        logger.error(f"Service inconnu : {service_key}")
        return False

    service = registry[service_key]

    # Déjà en cours — rien à faire
    if is_running(service_key):
        logger.info(f"{service_key} déjà actif")
        return True

    # Vérification RAM disponible
    ram_needed = service["ram_mb"]
    ram_available = get_ram_available_mb()

    if ram_available < ram_needed:
        logger.info(f"RAM insuffisante ({ram_available}Mo dispo, {ram_needed}Mo requis) — libération en cours")
        _free_ram(service_key, ram_needed - ram_available, registry)

    # Démarrage
    logger.info(f"Démarrage de {service_key}")
    success = start_service(service_key)

    if success:
        logger.info(f"{service_key} démarré avec succès")
    else:
        logger.error(f"Échec du démarrage de {service_key}")

    return success


def _free_ram(requesting_key: str, ram_to_free: int, registry: dict) -> None:
    """
    Arrête des services on-demand pour libérer suffisamment de RAM.
    Priorité : services d'un MVP différent de celui demandé.
    """
    requesting_mvp = registry[requesting_key]["mvp"]
    running = get_running_on_demand_services()

    # D'abord les services d'un autre MVP
    other_mvp = [
        k for k in running
        if registry[k]["mvp"] != requesting_mvp
    ]
    # Ensuite les services du même MVP si nécessaire
    same_mvp = [
        k for k in running
        if registry[k]["mvp"] == requesting_mvp and k != requesting_key
    ]

    freed = 0
    for key in other_mvp + same_mvp:
        if freed >= ram_to_free:
            break
        logger.info(f"Arrêt de {key} pour libérer {registry[key]['ram_mb']}Mo")
        stop_service(key)
        freed += registry[key]["ram_mb"]
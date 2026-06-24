import yaml
import docker
from pathlib import Path

REGISTRY_PATH = Path(__file__).parent / "registry.yaml"


def load_registry() -> dict:
    with open(REGISTRY_PATH) as f:
        return yaml.safe_load(f)["services"]


def _client():
    return docker.from_env()


def is_running(service_key: str) -> bool:
    registry = load_registry()
    container_name = registry[service_key]["container_name"]
    try:
        container = _client().containers.get(container_name)
        return container.status == "running"
    except docker.errors.NotFound:
        return False


def start_service(service_key: str) -> bool:
    registry = load_registry()
    service = registry[service_key]
    container_name = service["container_name"]
    try:
        client = _client()
        try:
            container = client.containers.get(container_name)
            container.start()
        except docker.errors.NotFound:
            # Container n'existe pas encore — on le crée via l'image existante
            return False
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"start_service {service_key}: {e}")
        return False


def stop_service(service_key: str) -> bool:
    registry = load_registry()
    container_name = registry[service_key]["container_name"]
    try:
        container = _client().containers.get(container_name)
        container.stop()
        return True
    except docker.errors.NotFound:
        return False
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"stop_service {service_key}: {e}")
        return False


def get_ram_available_mb() -> int:
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable"):
                return int(line.split()[1]) // 1024
    return 0
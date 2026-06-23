import subprocess
import yaml
import docker
from pathlib import Path

REGISTRY_PATH = Path(__file__).parent / "registry.yaml"


def load_registry() -> dict:
    with open(REGISTRY_PATH) as f:
        return yaml.safe_load(f)["services"]


def is_running(service_key: str) -> bool:
    """Vérifie si le container est en cours d'exécution."""
    registry = load_registry()
    service = registry[service_key]
    container_name = service["container_name"]

    client = docker.from_env()
    try:
        container = client.containers.get(container_name)
        return container.status == "running"
    except docker.errors.NotFound:
        return False


def start_service(service_key: str) -> bool:
    """Démarre un service via docker compose up -d."""
    registry = load_registry()
    service = registry[service_key]
    compose_file = service["compose_file"]
    compose_service = service["compose_service"]

    result = subprocess.run(
        ["docker", "compose", "-f", compose_file, "up", "-d", compose_service],
        capture_output=True,
        text=True
    )
    return result.returncode == 0


def stop_service(service_key: str) -> bool:
    """Arrête un service via docker compose stop."""
    registry = load_registry()
    service = registry[service_key]
    compose_file = service["compose_file"]
    compose_service = service["compose_service"]

    result = subprocess.run(
        ["docker", "compose", "-f", compose_file, "stop", compose_service],
        capture_output=True,
        text=True
    )
    return result.returncode == 0


def get_ram_available_mb() -> int:
    """Retourne la RAM disponible en Mo."""
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable"):
                return int(line.split()[1]) // 1024
    return 0
import threading
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

INACTIVITY_TIMEOUT = 300  # 5 minutes en secondes

# Dictionnaire des timers actifs : service_key -> threading.Timer
_timers: dict[str, threading.Timer] = {}
# Timestamp de dernière activité par service
_last_activity: dict[str, datetime] = {}
_lock = threading.Lock()


def _on_timeout(service_key: str) -> None:
    """Callback déclenché après 5 min d'inactivité — arrête le service."""
    from resource_manager import stop_service_safe
    logger.info(f"Timeout {service_key} — aucune activité depuis {INACTIVITY_TIMEOUT}s")
    with _lock:
        _timers.pop(service_key, None)
        _last_activity.pop(service_key, None)
    stop_service_safe(service_key)


def start_timer(service_key: str) -> None:
    """Démarre le timer d'inactivité pour un service."""
    with _lock:
        _cancel_existing(service_key)
        timer = threading.Timer(INACTIVITY_TIMEOUT, _on_timeout, args=[service_key])
        timer.daemon = True
        timer.start()
        _timers[service_key] = timer
        _last_activity[service_key] = datetime.now()
        logger.info(f"Timer démarré pour {service_key}")


def reset_timer(service_key: str) -> None:
    """Remet le timer à zéro — appelé à chaque activité sur le service."""
    with _lock:
        if service_key not in _timers:
            return
        _cancel_existing(service_key)
        timer = threading.Timer(INACTIVITY_TIMEOUT, _on_timeout, args=[service_key])
        timer.daemon = True
        timer.start()
        _timers[service_key] = timer
        _last_activity[service_key] = datetime.now()


def cancel_timer(service_key: str) -> None:
    """Annule le timer d'un service arrêté manuellement."""
    with _lock:
        _cancel_existing(service_key)
        _timers.pop(service_key, None)
        _last_activity.pop(service_key, None)
        logger.info(f"Timer annulé pour {service_key}")


def get_status() -> dict:
    """Retourne l'état de tous les timers actifs."""
    with _lock:
        return {
            key: {
                "last_activity": _last_activity[key].isoformat(),
                "seconds_remaining": max(
                    0,
                    INACTIVITY_TIMEOUT - (datetime.now() - _last_activity[key]).seconds
                )
            }
            for key in _timers
        }


def _cancel_existing(service_key: str) -> None:
    """Annule un timer existant sans lock — doit être appelé dans un contexte locké."""
    if service_key in _timers:
        _timers[service_key].cancel()
import logging
import logging.handlers
from app.core.config import settings


def setup_logging():
    """Configure logging - local en dev, Loki en production."""
    
    log_level = getattr(logging, settings.LOG_LEVEL)
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Configuration de base (toujours active)
    logging.basicConfig(
        level=log_level,
        format=log_format
    )

    # Handler Loki uniquement en production
    # if settings.ENVIRONMENT == "production" and settings.COCKPIT_TOKEN and settings.COCKPIT_LOGS_URL:
    #     try:
    #         import logging_loki
            
    #         loki_handler = logging_loki.LokiHandler(
    #             url=f"{settings.COCKPIT_LOGS_URL}/loki/api/v1/push",
    #             tags={"application": "portfolio-cv-backend", "environment": "production"},
    #             auth=("scaleway", settings.COCKPIT_TOKEN),
    #             version="1",
    #         )
    #         loki_handler.setLevel(log_level)
            
    #         # Ajouter le handler Loki au root logger
    #         logging.getLogger().addHandler(loki_handler)
    #         logging.getLogger(__name__).info("Loki logging handler configured successfully")
            
    #     except ImportError:
    #         logging.getLogger(__name__).warning("python-logging-loki not installed, skipping Loki handler")
    #     except Exception as e:
    #         logging.getLogger(__name__).warning(f"Failed to configure Loki handler: {e}")
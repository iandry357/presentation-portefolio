"""
Cloud Run Job — Orchestrateur principal.

Modes :
  MODE=sync          → collecte France Travail → BigQuery (défaut)
  MODE=explore_rome  → exploration et validation codes ROME

Variables d'environnement communes :
  MODE              (défaut: sync)
  FT_CLIENT_ID
  FT_CLIENT_SECRET

Variables MODE=sync :
  BQ_PROJECT_ID, BQ_DATASET, BQ_TABLE
  ROME_CODES        (séparés par virgule)
  MOTS_CLES         (séparés par virgule, optionnel)
  REGION            (défaut: 11)
  BOOTSTRAP_MODE    (défaut: false)

Variables MODE=explore_rome :
  OPENAI_API_KEY
  SCORE_MIN         (défaut: 0.5)
"""

import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("main")

MODE = os.environ.get("MODE", "sync").strip().lower()

if __name__ == "__main__":
    logger.info(f"Cloud Run Job démarré — MODE={MODE}")

    if MODE == "sync":
        logger.info("Lancement sync France Travail → BigQuery")
        from sync import main
        main()

    elif MODE == "explore_rome":
        logger.info("Lancement exploration codes ROME")
        from explore_rome import main
        main()

    else:
        logger.error(f"MODE inconnu : '{MODE}' — valeurs acceptées : sync, explore_rome")
        sys.exit(1)
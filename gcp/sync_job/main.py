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
from sources.gmail_alerts.service import GmailSyncService

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
        # logger.info("Lancement sync France Travail → BigQuery")
        # from sync import main
        # main()

        # Construction bq_client pour Gmail
        from google.cloud import bigquery

        BQ_PROJECT_ID = os.environ.get("BQ_PROJECT_ID", "").strip()
        BQ_DATASET    = os.environ.get("BQ_DATASET", "").strip()
        BQ_TABLE      = os.environ.get("BQ_TABLE", "").strip()
        BQ_TABLE_REF  = f"{BQ_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"

        sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if sa_path:
            import json
            from google.oauth2 import service_account
            with open(sa_path) as f:
                sa_info = json.load(f)
            credentials = service_account.Credentials.from_service_account_info(sa_info)
            bq_client = bigquery.Client(project=BQ_PROJECT_ID, credentials=credentials)
        else:
            bq_client = bigquery.Client(project=BQ_PROJECT_ID)

        logger.info("=" * 60)
        logger.info("Sync Gmail → BigQuery — démarrage")
        logger.info("=" * 60)

        # DEBUG — dump HTML nouvelles sources
        # from sources.gmail_alerts.reader import GmailReader
        # debug_reader = GmailReader()
        # debug_reader.dump_html("contact@jobijoba.com", "/app/debug")
        # debug_reader.dump_html("jobs@free-work.com", "/app/debug")
        # debug_reader.dump_html("alerts@welcometothejungle.com", "/app/debug")
        # debug_reader.dump_html("donotreply@jobalert.indeed.com", "/app/debug")

        gmail_service = GmailSyncService()
        gmail_result  = gmail_service.run(bq_client, BQ_TABLE_REF)
        logger.info(f"Gmail sync terminé : {gmail_result}")

    elif MODE == "explore_rome":
        logger.info("Lancement exploration codes ROME")
        from explore_rome import main
        main()

    else:
        logger.error(f"MODE inconnu : '{MODE}' — valeurs acceptées : sync, explore_rome")
        sys.exit(1)
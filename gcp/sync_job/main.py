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

DBT_JOB_NAME = os.environ.get("DBT_JOB_NAME", "dbt-emploi-marche")
DBT_JOB_REGION = os.environ.get("DBT_JOB_REGION", "europe-west9")


def _trigger_dbt_job() -> None:
    """
    Déclenche le Cloud Run Job dbt-emploi-marche une fois la sync
    (France Travail + Gmail) terminée avec succès.

    Fire-and-forget, comme les Workflows existants (trigger_sync_job) :
    ne bloque pas sur la fin d'exécution de dbt. Le seul objectif est de
    garantir que dbt démarre APRÈS l'ingestion, pas en parallèle.

    Le SA pipeline_emploi (utilisé par ce job) doit avoir le droit
    d'invoquer le job dbt-emploi-marche (voir IAM à ajouter côté infra).
    """
    import google.auth
    import google.auth.transport.requests
    import requests

    project_id = os.environ.get("BQ_PROJECT_ID", "").strip()
    if not project_id:
        logger.error("BQ_PROJECT_ID absent — impossible de déclencher dbt-emploi-marche")
        return

    url = (
        f"https://{DBT_JOB_REGION}-run.googleapis.com/apis/run.googleapis.com/v1/"
        f"namespaces/{project_id}/jobs/{DBT_JOB_NAME}:run"
    )

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(google.auth.transport.requests.Request())

    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {credentials.token}"},
        timeout=30,
    )

    if response.status_code >= 300:
        logger.error(
            f"Déclenchement {DBT_JOB_NAME} — statut {response.status_code} : {response.text}"
        )
    else:
        logger.info(f"Job {DBT_JOB_NAME} déclenché avec succès (statut {response.status_code})")


if __name__ == "__main__":
    logger.info(f"Cloud Run Job démarré — MODE={MODE}")

    if MODE == "sync":
        logger.info("Lancement sync France Travail → BigQuery")
        from sync import main
        main()

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
        from sources.gmail_alerts.reader import GmailReader
        debug_reader = GmailReader()
        # debug_reader.dump_html("contact@jobijoba.com", "/app/debug")
        # debug_reader.dump_html("jobs@free-work.com", "/app/debug")
        # debug_reader.dump_html("alerts@welcometothejungle.com", "/app/debug")
        # debug_reader.dump_html("donotreply@jobalert.indeed.com", "/app/debug")
        # debug_reader.dump_html("offres@diffusion.apec.fr", "/app/debug")
        # debug_reader.dump_html("ne-pas-repondre@meteojob.com", "/app/debug")
        # debug_reader.dump_html("mailer@jobleads.com", "/app/debug")

        # "jobalerts-noreply@linkedin.com":       LinkedInParser(),
        # "jobs-listings@linkedin.com":       LinkedInParser(),
        # "jobs-noreply@linkedin.com":        LinkedInParser(),
        # debug_reader.dump_html("jobalerts-noreply@linkedin.com", "/app/debug")
        # debug_reader.dump_html("jobs-listings@linkedin.com", "/app/debug")
        # debug_reader.dump_html("jobs-noreply@linkedin.com", "/app/debug")

        gmail_service = GmailSyncService()
        gmail_result  = gmail_service.run(bq_client, BQ_TABLE_REF)
        logger.info(f"Gmail sync terminé : {gmail_result}")

        # Déclenchement dbt — uniquement si FT sync + Gmail sync ont réussi
        # sans lever d'exception (sinon le script se serait arrêté avant).
        try:
            _trigger_dbt_job()
        except Exception as e:
            logger.error(f"Échec du déclenchement du job dbt-emploi-marche : {e}")

    elif MODE == "explore_rome":
        logger.info("Lancement exploration codes ROME")
        from explore_rome import main
        main()

    else:
        logger.error(f"MODE inconnu : '{MODE}' — valeurs acceptées : sync, explore_rome")
        sys.exit(1)
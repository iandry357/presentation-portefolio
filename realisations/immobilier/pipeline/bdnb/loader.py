import logging

from google.cloud import bigquery

from pipeline.bdnb.config import BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH, TABLES

logger = logging.getLogger(__name__)


def charger_parquet(chemin_parquet, table):
    """Charge un Parquet dans BigQuery en remplacement complet de la table. Retourne le nombre de lignes chargées."""
    client = bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)
    table_id = f"{GCP_PROJECT_ID}.{BQ_DATASET}.{table}"
    config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        clustering_fields=TABLES[table]["cluster"],
    )
    with open(chemin_parquet, "rb") as f:
        job = client.load_table_from_file(f, table_id, job_config=config)
    job.result()
    logger.info("Table %s chargée : %d lignes", table_id, job.output_rows)
    return job.output_rows

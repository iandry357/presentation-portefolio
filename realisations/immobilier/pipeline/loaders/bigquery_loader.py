import logging

from google.cloud import bigquery

from pipeline.config import BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH, NULL_MARKER

logger = logging.getLogger(__name__)


def charger_csv(chemin_csv, table, schema):
    """Charge un CSV dans BigQuery en remplacement complet de la table. Retourne le nombre de lignes chargées."""
    client = bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)
    table_id = f"{GCP_PROJECT_ID}.{BQ_DATASET}.{table}"
    config = bigquery.LoadJobConfig(
        schema=[bigquery.SchemaField(nom, type_) for nom, type_ in schema],
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        null_marker=NULL_MARKER,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    with open(chemin_csv, "rb") as f:
        job = client.load_table_from_file(f, table_id, job_config=config)
    job.result()
    logger.info("Table %s chargée : %d lignes", table_id, job.output_rows)
    return job.output_rows

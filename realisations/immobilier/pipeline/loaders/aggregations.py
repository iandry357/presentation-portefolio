import logging

from google.cloud import bigquery

from pipeline.config import BQ_DATASET, BQ_TABLE_DPE, BQ_TABLE_DVF, GCP_PROJECT_ID, GCP_SA_KEY_PATH

logger = logging.getLogger(__name__)

# Paramètres
TABLE_AGG_DPE = "agg_dpe_parc"
TABLE_AGG_DVF = "agg_dvf_prix"


def _table(nom):
    return f"`{GCP_PROJECT_ID}.{BQ_DATASET}.{nom}`"


def _creer_table(nom, requete):
    """Crée ou remplace une table à partir d'une requête SELECT. Retourne le nombre de lignes."""
    client = bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)
    client.query(f"CREATE OR REPLACE TABLE {_table(nom)} AS {requete}").result()
    nb_lignes = client.get_table(f"{GCP_PROJECT_ID}.{BQ_DATASET}.{nom}").num_rows
    logger.info("Table agrégée %s : %d lignes", nom, nb_lignes)
    return nb_lignes


def construire_agg_dpe():
    """Parc DPE : arrondissement x étiquette x chauffage électrique."""
    return _creer_table(TABLE_AGG_DPE, f"""
        SELECT
            arrondissement,
            etiquette_dpe,
            flag_chauffage_electrique,
            COUNT(*) AS nb_dpe,
            COUNTIF(numero_dpe_remplace IS NOT NULL) AS nb_remplacants,
            CURRENT_TIMESTAMP() AS date_maj
        FROM {_table(BQ_TABLE_DPE)}
        GROUP BY arrondissement, etiquette_dpe, flag_chauffage_electrique
    """)


def construire_agg_dvf():
    """Prix DVF : arrondissement x année x type de logement (nombre de ventes et prix au m² médian)."""
    return _creer_table(TABLE_AGG_DVF, f"""
        SELECT
            arrondissement,
            annee,
            type_local,
            COUNT(*) AS nb_ventes,
            ROUND(APPROX_QUANTILES(prix_m2, 2)[OFFSET(1)], 0) AS prix_m2_median,
            CURRENT_TIMESTAMP() AS date_maj
        FROM {_table(BQ_TABLE_DVF)}
        GROUP BY arrondissement, annee, type_local
    """)

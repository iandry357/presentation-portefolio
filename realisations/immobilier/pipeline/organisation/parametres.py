import logging

from google.cloud import bigquery

from pipeline.organisation.config import (
    BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH, TABLE_PARAMETRES, VUE_DVF_BRUT,
)

logger = logging.getLogger(__name__)


def _client():
    return bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)


def _table(nom):
    return f"`{GCP_PROJECT_ID}.{BQ_DATASET}.{nom}`"


def _litteral(valeur):
    """Texte SQL entre apostrophes (échappées avec un antislash, comme en GoogleSQL)."""
    return "'" + str(valeur).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _fenetre(colonne, debut, fin):
    """Condition SQL sur la période : début inclus ; fin incluse si elle est donnée (None : jusqu'à la dernière date)."""
    condition = f"{colonne} >= DATE {_litteral(debut)}"
    return condition if fin is None else f"{condition} AND {colonne} <= DATE {_litteral(fin)}"


def ecrire(livraison, departement, debut, fin):
    """Table à une ligne : période demandée (date_fin NULL = jusqu'aux dernières données) et période réellement couverte
    par les ventes de la vue brute (première et dernière vente). Retourne la ligne écrite."""
    client = _client()
    fin_sql = "CAST(NULL AS DATE)" if fin is None else f"DATE {_litteral(fin)}"
    client.query(f"""
        CREATE OR REPLACE TABLE {_table(TABLE_PARAMETRES)} AS
        SELECT {_litteral(livraison)} AS livraison,
               {_litteral(departement)} AS code_departement,
               DATE {_litteral(debut)} AS date_debut,
               {fin_sql} AS date_fin,
               MIN(date_mutation) AS premiere_vente,
               MAX(date_mutation) AS derniere_vente,
               CURRENT_TIMESTAMP() AS date_maj
        FROM {_table(VUE_DVF_BRUT)}
        WHERE livraison = {_litteral(livraison)} AND code_departement = {_litteral(departement)}
          AND {_fenetre("date_mutation", debut, fin)}
    """).result()
    ligne = dict(next(iter(client.query(f"SELECT * FROM {_table(TABLE_PARAMETRES)}").result())))
    if ligne["premiere_vente"] is None:
        raise ValueError(f"{TABLE_PARAMETRES} : aucune vente dans la période demandée, livraison ou dates à vérifier")
    logger.info("Table %s : demandé du %s au %s, couvert du %s au %s", TABLE_PARAMETRES, ligne["date_debut"],
                ligne["date_fin"] or "dernières données", ligne["premiere_vente"], ligne["derniere_vente"])
    return ligne

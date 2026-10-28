import logging

import polars as pl
from google.cloud import bigquery

from pipeline.organisation.config import (
    BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH, TABLE_CUBE_BATIMENT, VUE_BATIMENT_BRUT,
)

logger = logging.getLogger(__name__)


def _client():
    return bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)


def _table(nom):
    return f"`{GCP_PROJECT_ID}.{BQ_DATASET}.{nom}`"


def _afficher(titre, lignes):
    print(f"\n== {titre}")
    with pl.Config(tbl_rows=-1, tbl_cols=-1):
        print(pl.DataFrame(lignes, infer_schema_length=None) if lignes else "(aucune ligne)")


def construire():
    """Une ligne par cellule (arrondissement, époque, usage, taille de copropriété, inondation, patrimoine) avec le
    nombre d'immeubles et de logements. Stock BDNB : pas de période. Modalité inconnue = NULL. Retourne le nombre de cellules."""
    client = _client()
    client.query(f"""
        CREATE OR REPLACE TABLE {_table(TABLE_CUBE_BATIMENT)} CLUSTER BY arrondissement AS
        SELECT arrondissement, epoque_ff, usage_batiment, taille_copro, inondation, patrimoine,
               COUNT(*) AS nb_immeubles,
               SUM(IFNULL(nb_log, 0)) AS nb_logements,
               CURRENT_TIMESTAMP() AS date_maj
        FROM {_table(VUE_BATIMENT_BRUT)}
        WHERE arrondissement BETWEEN 1 AND 20
        GROUP BY arrondissement, epoque_ff, usage_batiment, taille_copro, inondation, patrimoine
    """).result()

    nb_cellules = client.get_table(f"{GCP_PROJECT_ID}.{BQ_DATASET}.{TABLE_CUBE_BATIMENT}").num_rows
    if nb_cellules == 0:
        raise ValueError(f"{TABLE_CUBE_BATIMENT} : aucune ligne, vue {VUE_BATIMENT_BRUT} à vérifier")
    attendu = next(iter(client.query(
        f"SELECT COUNT(*) AS n FROM {_table(VUE_BATIMENT_BRUT)} WHERE arrondissement BETWEEN 1 AND 20"
    ).result()))["n"]
    immeubles = next(iter(client.query(f"SELECT SUM(nb_immeubles) AS n FROM {_table(TABLE_CUBE_BATIMENT)}").result()))["n"]
    if immeubles != attendu:
        raise ValueError(f"{TABLE_CUBE_BATIMENT} : {immeubles} immeubles agrégés pour {attendu} dans la vue {VUE_BATIMENT_BRUT}")
    logger.info("Table %s : %d cellules, %d immeubles", TABLE_CUBE_BATIMENT, nb_cellules, immeubles)

    _afficher("Immeubles par époque de construction (contrôle)", [
        dict(r) for r in client.query(f"""
            SELECT epoque_ff, SUM(nb_immeubles) AS immeubles,
                   ROUND(SUM(nb_immeubles) / SUM(SUM(nb_immeubles)) OVER () * 100, 1) AS pct
            FROM {_table(TABLE_CUBE_BATIMENT)} GROUP BY 1 ORDER BY 1
        """).result()
    ])
    return nb_cellules

import logging

import polars as pl
from google.cloud import bigquery

from pipeline.organisation.config import (
    BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH, LIBELLES_SURFACE, PIECES_MAX, PRIX_M2_MAX, PRIX_M2_MIN,
    TABLE_CUBE_DVF, TRANCHES_SURFACE, VUE_DVF_BRUT,
)

logger = logging.getLogger(__name__)

# Rappel : la vue brute ne borne pas le prix au m² ; les bornes sont appliquées ici.


def _client():
    return bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)


def _table(nom):
    return f"`{GCP_PROJECT_ID}.{BQ_DATASET}.{nom}`"


def _litteral(valeur):
    """Texte SQL entre apostrophes (échappées avec un antislash, comme en GoogleSQL)."""
    return "'" + str(valeur).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _tranche_surface(colonne):
    """Expression SQL : libellé de la tranche de surface (bornes basses incluses), NULL si surface absente ou nulle."""
    cas = " ".join(
        f"WHEN {colonne} < {borne} THEN {_litteral(libelle)}"
        for borne, libelle in zip(TRANCHES_SURFACE, LIBELLES_SURFACE)
    )
    return f"CASE WHEN {colonne} IS NULL OR {colonne} <= 0 THEN NULL {cas} ELSE {_litteral(LIBELLES_SURFACE[-1])} END"


def _fenetre(colonne, debut, fin):
    """Condition SQL sur la période : début inclus ; fin incluse si elle est donnée (None : jusqu'à la dernière date)."""
    condition = f"{colonne} >= DATE {_litteral(debut)}"
    return condition if fin is None else f"{condition} AND {colonne} <= DATE {_litteral(fin)}"


def _afficher(titre, lignes):
    print(f"\n== {titre}")
    with pl.Config(tbl_rows=-1, tbl_cols=-1):
        print(pl.DataFrame(lignes, infer_schema_length=None) if lignes else "(aucune ligne)")


def construire(livraison, departement, debut, fin):
    """Une ligne par cellule (mois, arrondissement, type de local, pièces, tranche de surface) avec la liste triée
    des prix au m² : les médianes se calculent exactement à la lecture. Retourne le nombre de cellules."""
    client = _client()
    filtre = f"""livraison = {_litteral(livraison)} AND code_departement = {_litteral(departement)}
          AND {_fenetre("date_mutation", debut, fin)}
          AND prix_m2 BETWEEN {PRIX_M2_MIN} AND {PRIX_M2_MAX} AND arrondissement BETWEEN 1 AND 20"""
    client.query(f"""
        CREATE OR REPLACE TABLE {_table(TABLE_CUBE_DVF)} CLUSTER BY mois, arrondissement AS
        SELECT FORMAT_DATE('%Y-%m', date_mutation) AS mois,
               arrondissement,
               type_local,
               IF(nombre_pieces_principales >= 1, LEAST(nombre_pieces_principales, {PIECES_MAX}), NULL) AS pieces,
               {_tranche_surface("surface_reelle_bati")} AS tranche_surface,
               COUNT(*) AS nb_ventes,
               ARRAY_AGG(prix_m2 ORDER BY prix_m2) AS prix_m2,
               CURRENT_TIMESTAMP() AS date_maj
        FROM {_table(VUE_DVF_BRUT)}
        WHERE {filtre}
        GROUP BY mois, arrondissement, type_local, pieces, tranche_surface
    """).result()

    nb_cellules = client.get_table(f"{GCP_PROJECT_ID}.{BQ_DATASET}.{TABLE_CUBE_DVF}").num_rows
    if nb_cellules == 0:
        raise ValueError(f"{TABLE_CUBE_DVF} : aucune ligne, livraison, période ou vue {VUE_DVF_BRUT} à vérifier")
    attendu = next(iter(client.query(f"SELECT COUNT(*) AS n FROM {_table(VUE_DVF_BRUT)} WHERE {filtre}").result()))["n"]
    ventes = next(iter(client.query(f"SELECT SUM(nb_ventes) AS n FROM {_table(TABLE_CUBE_DVF)}").result()))["n"]
    if ventes != attendu:
        raise ValueError(f"{TABLE_CUBE_DVF} : {ventes} ventes agrégées pour {attendu} dans la vue {VUE_DVF_BRUT}")
    logger.info("Table %s : %d cellules, %d ventes", TABLE_CUBE_DVF, nb_cellules, ventes)

    _afficher("Prix médian au m² par type de local et nombre de pièces (contrôle de la forme de la courbe)", [
        dict(r) for r in client.query(f"""
            SELECT DISTINCT type_local, pieces,
                   COUNT(*) OVER (PARTITION BY type_local, pieces) AS ventes,
                   ROUND(PERCENTILE_CONT(p, 0.5) OVER (PARTITION BY type_local, pieces)) AS prix_m2_median
            FROM {_table(TABLE_CUBE_DVF)}, UNNEST(prix_m2) AS p
            ORDER BY type_local, pieces
        """).result()
    ])
    return nb_cellules

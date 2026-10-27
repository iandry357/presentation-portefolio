import logging

import polars as pl
from google.cloud import bigquery

from pipeline.analyse.config import (
    BDNB_DPE, BDNB_REL_DPE_BATIMENT, DATE_DEBUT_FENETRE, DATE_FIN_FENETRE, ETIQUETTE_INCONNUE, PIECES_MAX,
    PRIX_M2_MAX, PRIX_M2_MIN, TABLE_VENTES, VUE_VENTES_BATIMENT,
)
from pipeline.analyse.cube import _tranche_surface, _trimestre
from pipeline.bdnb_complement.config import (
    BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH, TABLE_ATTRIBUTS_BATIMENT, TABLE_CUBE_BATI,
)

logger = logging.getLogger(__name__)

# Même sélection de ventes que pipeline/analyse/cube.py (construire_ventes), recopiée pour ne pas modifier l'existant ;
# _tranche_surface et _trimestre sont importés de ce module. Les deux cubes doivent rester identiques sur les ventes :
# le contrôle compare leurs effectifs.
DIMENSIONS_BATI = ["epoque_ff", "taille_copro", "inondation", "patrimoine", "usage_batiment"]


def _client():
    return bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)


def _table(nom):
    return f"`{GCP_PROJECT_ID}.{BQ_DATASET}.{nom}`"


def _litteral(valeur):
    """Texte SQL entre apostrophes (échappées avec un antislash, comme en GoogleSQL)."""
    return "'" + str(valeur).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _lignes(client, requete):
    return [dict(r) for r in client.query(requete).result()]


def _afficher(titre, lignes):
    print(f"\n== {titre}")
    with pl.Config(tbl_rows=-1, tbl_cols=-1):
        print(pl.DataFrame(lignes, infer_schema_length=None) if lignes else "(aucune ligne)")


def construire_cube_bati(livraison, departement):
    """Une ligne par cellule (dimensions d'« Analyse » plus époque, taille de copropriété, inondation, patrimoine, usage)
    avec la liste triée des prix au m². Étiquette du bâtiment = médiane basse des classes de ses DPE (règle de la phase 3).
    Un attribut absent (vente sans bâtiment, bâtiment sans ligne dans la table source) reste NULL."""
    client = _client()
    dimensions = ", ".join(DIMENSIONS_BATI)
    client.query(f"""
        CREATE OR REPLACE TABLE {_table(TABLE_CUBE_BATI)} CLUSTER BY trimestre, arrondissement AS
        WITH classe_batiment AS (
            SELECT r.batiment_groupe_id,
                   ARRAY_AGG(d.classe_bilan_dpe ORDER BY d.classe_bilan_dpe) AS classes
            FROM {_table(BDNB_REL_DPE_BATIMENT)} r
            JOIN {_table(BDNB_DPE)} d USING (identifiant_dpe)
            WHERE d.classe_bilan_dpe IS NOT NULL
            GROUP BY r.batiment_groupe_id
        ),
        ventes AS (
            SELECT v.date_mutation, v.prix_m2, v.surface_reelle_bati, v.nombre_pieces_principales, v.batiment_groupe_id,
                   SAFE_CAST(v.code_commune AS INT64) - 75100 AS arrondissement,
                   c.classes[OFFSET(DIV(ARRAY_LENGTH(c.classes) - 1, 2))] AS etiquette_batiment,
                   a.epoque_ff, a.taille_copro, a.inondation, a.patrimoine, a.usage_batiment
            FROM {_table(VUE_VENTES_BATIMENT)} v
            LEFT JOIN classe_batiment c ON c.batiment_groupe_id = v.batiment_groupe_id
            LEFT JOIN {_table(TABLE_ATTRIBUTS_BATIMENT)} a ON a.batiment_groupe_id = v.batiment_groupe_id
            WHERE v.livraison = {_litteral(livraison)} AND v.code_departement = {_litteral(departement)}
              AND v.date_mutation BETWEEN DATE '{DATE_DEBUT_FENETRE}' AND DATE '{DATE_FIN_FENETRE}'
              AND v.prix_m2 BETWEEN {PRIX_M2_MIN} AND {PRIX_M2_MAX}
        )
        SELECT {_trimestre("date_mutation")} AS trimestre,
               arrondissement,
               IF(nombre_pieces_principales >= 1, LEAST(nombre_pieces_principales, {PIECES_MAX}), NULL) AS pieces,
               {_tranche_surface("surface_reelle_bati")} AS tranche_surface,
               IFNULL(etiquette_batiment, {_litteral(ETIQUETTE_INCONNUE)}) AS etiquette,
               batiment_groupe_id IS NOT NULL AS rattachee,
               {dimensions},
               COUNT(*) AS nb_ventes,
               ARRAY_AGG(prix_m2 ORDER BY prix_m2) AS prix_m2,
               CURRENT_TIMESTAMP() AS date_maj
        FROM ventes
        WHERE arrondissement BETWEEN 1 AND 20
        GROUP BY trimestre, arrondissement, pieces, tranche_surface, etiquette, rattachee, {dimensions}
    """).result()
    nb = client.get_table(f"{GCP_PROJECT_ID}.{BQ_DATASET}.{TABLE_CUBE_BATI}").num_rows
    if nb == 0:
        raise ValueError(f"{TABLE_CUBE_BATI} : aucune ligne, sources ou fenêtre à vérifier")
    logger.info("Table %s : %d lignes", TABLE_CUBE_BATI, nb)
    _controler(client)
    return nb


def _controler(client):
    """Arrêt si les effectifs diffèrent de ceux du cube « Analyse » ; affiche les ventes par attribut du bâti."""
    cube = _lignes(client, f"""
        SELECT SUM(nb_ventes) AS ventes, SUM(IF(rattachee, nb_ventes, 0)) AS rattachees FROM {_table(TABLE_CUBE_BATI)}
    """)[0]
    reference = _lignes(client, f"""
        SELECT SUM(nb_ventes) AS ventes, SUM(IF(rattachee, nb_ventes, 0)) AS rattachees FROM {_table(TABLE_VENTES)}
    """)[0]
    if cube != reference:
        raise ValueError(
            f"{TABLE_CUBE_BATI} : {cube} contre {reference} dans {TABLE_VENTES} "
            "(cube « Analyse » à reconstruire avec la même livraison et la même fenêtre ?)"
        )
    logger.info("%s : %d ventes dont %d rattachées, identiques au cube « Analyse »", TABLE_CUBE_BATI, cube["ventes"], cube["rattachees"])

    for dimension in DIMENSIONS_BATI:
        _afficher(f"{dimension} (ventes)", _lignes(client, f"""
            SELECT {dimension} AS modalite, SUM(nb_ventes) AS ventes,
                   ROUND(SUM(nb_ventes) / SUM(SUM(nb_ventes)) OVER () * 100, 1) AS pct
            FROM {_table(TABLE_CUBE_BATI)} GROUP BY 1 ORDER BY 1
        """))

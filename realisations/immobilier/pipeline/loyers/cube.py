import logging

from google.cloud import bigquery

from pipeline.loyers.config import (
    BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH, TABLE_AGREGAT, VUE_VENTES_LOYER,
)

logger = logging.getLogger(__name__)


def _client():
    return bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)


def _table(nom):
    return f"`{GCP_PROJECT_ID}.{BQ_DATASET}.{nom}`"


def _litteral(valeur):
    """Texte SQL entre apostrophes (échappées avec un antislash, comme en GoogleSQL)."""
    return "'" + str(valeur).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _trimestre(colonne):
    return f"CONCAT(CAST(EXTRACT(YEAR FROM {colonne}) AS STRING), '-T', CAST(EXTRACT(QUARTER FROM {colonne}) AS STRING))"


def construire_agregat(livraison, departement):
    """Une ligne par cellule (trimestre, année de loyer, arrondissement, quartier, pièces, époque, marquages, meublé)
    avec les listes triées des prix au m², des loyers (référence, majoré, minoré) et des rendements bruts.
    Rendement central = loyer de référence ; rendement majoré = borne haute (colonne rendement_brut de la vue)."""
    client = _client()
    l, d = _litteral(livraison), _litteral(departement)
    client.query(f"""
        CREATE OR REPLACE TABLE {_table(TABLE_AGREGAT)} CLUSTER BY trimestre, arrondissement AS
        SELECT {_trimestre("date_mutation")} AS trimestre,
               annee_loyer,
               arrondissement,
               id_quartier,
               nom_quartier,
               pieces,
               epoque,
               epoque_ambigue,
               periode_heterogene,
               meuble,
               COUNT(*) AS nb_ventes,
               ARRAY_AGG(prix_m2 IGNORE NULLS ORDER BY prix_m2) AS prix_m2,
               ANY_VALUE(loyer_reference) AS loyer_reference,
               ANY_VALUE(loyer_majore) AS loyer_majore,
               ANY_VALUE(loyer_minore) AS loyer_minore,
               ARRAY_AGG(rendement_reference IGNORE NULLS ORDER BY rendement_reference) AS rendement_reference,
               ARRAY_AGG(rendement_brut IGNORE NULLS ORDER BY rendement_brut) AS rendement_majore,
               CURRENT_TIMESTAMP() AS date_maj
        FROM (
            SELECT *, SAFE_DIVIDE(loyer_reference * surface_reelle_bati * 12, valeur_fonciere) AS rendement_reference
            FROM {_table(VUE_VENTES_LOYER)}
            WHERE livraison = {l} AND code_departement = {d} AND arrondissement BETWEEN 1 AND 20
        )
        GROUP BY trimestre, annee_loyer, arrondissement, id_quartier, nom_quartier, pieces, epoque,
                 epoque_ambigue, periode_heterogene, meuble
    """).result()

    nb_cellules = client.get_table(f"{GCP_PROJECT_ID}.{BQ_DATASET}.{TABLE_AGREGAT}").num_rows
    if nb_cellules == 0:
        raise ValueError(f"{TABLE_AGREGAT} : aucune ligne, vue {VUE_VENTES_LOYER} ou livraison à vérifier")
    attendu = next(iter(client.query(f"""
        SELECT COUNT(*) AS n FROM {_table(VUE_VENTES_LOYER)}
        WHERE livraison = {l} AND code_departement = {d} AND arrondissement BETWEEN 1 AND 20
    """).result()))["n"]
    ligne = next(iter(client.query(
        f"SELECT SUM(nb_ventes) AS lignes, SUM(IF(meuble, 0, nb_ventes)) AS ventes FROM {_table(TABLE_AGREGAT)}"
    ).result()))
    if ligne["lignes"] != attendu:
        raise ValueError(f"{TABLE_AGREGAT} : {ligne['lignes']} lignes agrégées pour {attendu} dans la vue {VUE_VENTES_LOYER}")
    logger.info("Table %s : %d cellules, %d ventes (%d lignes avec meublé et non meublé)",
                TABLE_AGREGAT, nb_cellules, ligne["ventes"], ligne["lignes"])
    return nb_cellules

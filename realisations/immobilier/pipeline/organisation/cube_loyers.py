import logging

from pipeline.organisation.config import TABLE_CUBE_DVF, TABLE_CUBE_LOYERS, VUE_VENTES_LOYER
from pipeline.organisation.sql import afficher, client, fenetre, lignes, litteral, mois, table, une_ligne

logger = logging.getLogger(__name__)


def construire(livraison, departement, debut, fin):
    """Une ligne par cellule (mois, année de loyer, arrondissement, quartier, pièces, époque, marquages, meublé) avec les listes
    triées des prix au m², des loyers (référence, majoré, minoré) et des rendements bruts. Rendement central = loyer de référence ;
    rendement majoré = borne haute (colonne rendement_brut de la vue). La vue a une ligne par vente et par état meublé ;
    une vente sans loyer de référence a une seule ligne, avec meuble NULL. À construire après le cube DVF."""
    connexion = client()
    filtre = f"""livraison = {litteral(livraison)} AND code_departement = {litteral(departement)}
          AND arrondissement BETWEEN 1 AND 20 AND {fenetre("date_mutation", debut, fin)}"""
    connexion.query(f"""
        CREATE OR REPLACE TABLE {table(TABLE_CUBE_LOYERS)} CLUSTER BY mois, arrondissement AS
        SELECT {mois("date_mutation")} AS mois,
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
            FROM {table(VUE_VENTES_LOYER)}
            WHERE {filtre}
        )
        GROUP BY mois, annee_loyer, arrondissement, id_quartier, nom_quartier, pieces, epoque,
                 epoque_ambigue, periode_heterogene, meuble
    """).result()

    nb_cellules = une_ligne(connexion, f"SELECT COUNT(*) AS n FROM {table(TABLE_CUBE_LOYERS)}")["n"]
    if nb_cellules == 0:
        raise ValueError(f"{TABLE_CUBE_LOYERS} : aucune ligne, vue {VUE_VENTES_LOYER} ou période à vérifier")
    attendu = une_ligne(connexion, f"SELECT COUNT(*) AS n FROM {table(VUE_VENTES_LOYER)} WHERE {filtre}")["n"]
    cube = une_ligne(connexion, f"""
        SELECT SUM(nb_ventes) AS lignes, SUM(IF(meuble, 0, nb_ventes)) AS ventes,
               SUM(IF(meuble IS NULL, nb_ventes, 0)) AS sans_loyer
        FROM {table(TABLE_CUBE_LOYERS)}
    """)
    if cube["lignes"] != attendu:
        raise ValueError(f"{TABLE_CUBE_LOYERS} : {cube['lignes']} lignes agrégées pour {attendu} dans la vue {VUE_VENTES_LOYER}")
    dvf = une_ligne(connexion, f"SELECT SUM(nb_ventes) AS ventes FROM {table(TABLE_CUBE_DVF)}")["ventes"]
    logger.info(
        "Table %s : %d cellules, %d ventes (%d lignes avec meublé et non meublé), soit %.1f %% des %d ventes du cube DVF",
        TABLE_CUBE_LOYERS, nb_cellules, cube["ventes"], cube["lignes"], 100 * cube["ventes"] / dvf, dvf,
    )
    if cube["sans_loyer"]:
        logger.warning("%d ventes rattachées sans loyer de référence (millésime de l'arrêté absent du jeu ?)", cube["sans_loyer"])
    afficher("Ventes par année de loyer (arrêté appliqué)", lignes(connexion, f"""
        SELECT annee_loyer, SUM(IF(meuble, 0, nb_ventes)) AS ventes
        FROM {table(TABLE_CUBE_LOYERS)} GROUP BY 1 ORDER BY 1
    """))
    return nb_cellules

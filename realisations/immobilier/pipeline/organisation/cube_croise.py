import logging

from pipeline.organisation.config import (
    BDNB_ATTRIBUTS_BATIMENT, BDNB_DPE, BDNB_REL_BATIMENT_ADRESSE, BDNB_REL_DPE_BATIMENT, ETIQUETTE_INCONNUE, PIECES_MAX,
    PRIX_M2_MAX, PRIX_M2_MIN, TABLE_CUBE_CROISE_DPE, TABLE_CUBE_CROISE_VENTES, TABLE_CUBE_DVF, TABLE_TYPOLOGIE,
    VUE_VENTES_BATIMENT,
)
from pipeline.organisation.sql import afficher, client, fenetre, lignes, litteral, mois, table, tranche_surface, une_ligne

logger = logging.getLogger(__name__)

# Attributs du bâtiment des ventes (bdnb_batiment_attributs), comme DIMENSIONS_BATI de pipeline/bdnb_complement/cube_bati.py
DIMENSIONS_BATI = ["epoque_ff", "taille_copro", "inondation", "patrimoine", "usage_batiment"]


def construire_ventes(livraison, departement, debut, fin):
    """Une ligne par cellule (mois, arrondissement, pièces, tranche de surface, étiquette du bâtiment, rattachée, attributs du
    bâti) avec la liste triée des prix au m². Étiquette du bâtiment = médiane basse des classes de ses DPE (règle de la phase 3).
    Un attribut absent (vente sans bâtiment, bâtiment sans ligne dans la table source) reste NULL.
    À construire après le cube DVF : le contrôle compare leurs effectifs."""
    connexion = client()
    dimensions = ", ".join(DIMENSIONS_BATI)
    connexion.query(f"""
        CREATE OR REPLACE TABLE {table(TABLE_CUBE_CROISE_VENTES)} CLUSTER BY mois, arrondissement AS
        WITH classe_batiment AS (
            SELECT r.batiment_groupe_id,
                   ARRAY_AGG(d.classe_bilan_dpe ORDER BY d.classe_bilan_dpe) AS classes
            FROM {table(BDNB_REL_DPE_BATIMENT)} r
            JOIN {table(BDNB_DPE)} d USING (identifiant_dpe)
            WHERE d.classe_bilan_dpe IS NOT NULL
            GROUP BY r.batiment_groupe_id
        ),
        ventes AS (
            SELECT v.date_mutation, v.prix_m2, v.surface_reelle_bati, v.nombre_pieces_principales, v.batiment_groupe_id,
                   SAFE_CAST(v.code_commune AS INT64) - 75100 AS arrondissement,
                   c.classes[OFFSET(DIV(ARRAY_LENGTH(c.classes) - 1, 2))] AS etiquette_batiment,
                   a.epoque_ff, a.taille_copro, a.inondation, a.patrimoine, a.usage_batiment
            FROM {table(VUE_VENTES_BATIMENT)} v
            LEFT JOIN classe_batiment c ON c.batiment_groupe_id = v.batiment_groupe_id
            LEFT JOIN {table(BDNB_ATTRIBUTS_BATIMENT)} a ON a.batiment_groupe_id = v.batiment_groupe_id
            WHERE v.livraison = {litteral(livraison)} AND v.code_departement = {litteral(departement)}
              AND {fenetre("v.date_mutation", debut, fin)}
              AND v.prix_m2 BETWEEN {PRIX_M2_MIN} AND {PRIX_M2_MAX}
        )
        SELECT {mois("date_mutation")} AS mois,
               arrondissement,
               IF(nombre_pieces_principales >= 1, LEAST(nombre_pieces_principales, {PIECES_MAX}), NULL) AS pieces,
               {tranche_surface("surface_reelle_bati")} AS tranche_surface,
               IFNULL(etiquette_batiment, {litteral(ETIQUETTE_INCONNUE)}) AS etiquette,
               batiment_groupe_id IS NOT NULL AS rattachee,
               {dimensions},
               COUNT(*) AS nb_ventes,
               ARRAY_AGG(prix_m2 ORDER BY prix_m2) AS prix_m2,
               CURRENT_TIMESTAMP() AS date_maj
        FROM ventes
        WHERE arrondissement BETWEEN 1 AND 20
        GROUP BY mois, arrondissement, pieces, tranche_surface, etiquette, rattachee, {dimensions}
    """).result()

    nb_cellules = une_ligne(connexion, f"SELECT COUNT(*) AS n FROM {table(TABLE_CUBE_CROISE_VENTES)}")["n"]
    if nb_cellules == 0:
        raise ValueError(f"{TABLE_CUBE_CROISE_VENTES} : aucune ligne, sources ou période à vérifier")
    cube = une_ligne(connexion, f"""
        SELECT SUM(nb_ventes) AS ventes, SUM(IF(rattachee, nb_ventes, 0)) AS rattachees FROM {table(TABLE_CUBE_CROISE_VENTES)}
    """)
    reference = une_ligne(connexion, f"SELECT SUM(nb_ventes) AS ventes FROM {table(TABLE_CUBE_DVF)}")
    if cube["ventes"] != reference["ventes"]:
        raise ValueError(
            f"{TABLE_CUBE_CROISE_VENTES} : {cube['ventes']} ventes pour {reference['ventes']} dans {TABLE_CUBE_DVF} "
            "(cube DVF à reconstruire avec la même livraison et la même période ?)"
        )
    logger.info(
        "Table %s : %d cellules, %d ventes dont %d rattachées, identiques au cube DVF",
        TABLE_CUBE_CROISE_VENTES, nb_cellules, cube["ventes"], cube["rattachees"],
    )
    afficher("Prix médian au m² par étiquette du bâtiment (contrôle de l'écart F et G contre D)", lignes(connexion, f"""
        SELECT DISTINCT etiquette, COUNT(*) OVER (PARTITION BY etiquette) AS ventes,
               ROUND(PERCENTILE_CONT(p, 0.5) OVER (PARTITION BY etiquette)) AS prix_m2_median
        FROM {table(TABLE_CUBE_CROISE_VENTES)}, UNNEST(prix_m2) AS p
        ORDER BY etiquette
    """))
    return nb_cellules


def _cte_dpe(debut, fin):
    """CTE des DPE de la BDNB dans la période, avec arrondissement du bâtiment et pièces ADEME.
    Un DPE relié à plusieurs bâtiments garde celui de plus petit identifiant ; un bâtiment à plusieurs adresses garde
    le plus petit arrondissement (règles de pipeline/analyse/cube.py)."""
    return f"""
        arrondissement_batiment AS (
            SELECT batiment_groupe_id,
                   MIN(SAFE_CAST(SUBSTR(cle_interop_adr, 1, 5) AS INT64) - 75100) AS arrondissement
            FROM {table(BDNB_REL_BATIMENT_ADRESSE)}
            GROUP BY batiment_groupe_id
        ),
        lien AS (
            SELECT identifiant_dpe, MIN(batiment_groupe_id) AS batiment_groupe_id
            FROM {table(BDNB_REL_DPE_BATIMENT)}
            GROUP BY identifiant_dpe
        ),
        dpe AS (
            SELECT d.date_etablissement_dpe, d.surface_habitable_logement, d.classe_bilan_dpe, a.arrondissement, t.pieces
            FROM {table(BDNB_DPE)} d
            JOIN lien l USING (identifiant_dpe)
            JOIN arrondissement_batiment a USING (batiment_groupe_id)
            LEFT JOIN {table(TABLE_TYPOLOGIE)} t USING (identifiant_dpe)
            WHERE {fenetre("d.date_etablissement_dpe", debut, fin)}
        )"""


def construire_dpe(debut, fin):
    """Une ligne par cellule (mois, arrondissement, pièces ADEME, tranche de surface, étiquette du logement) avec le nombre de
    DPE de la BDNB. pieces est NULL pour les DPE sans typologie."""
    connexion = client()
    cte = _cte_dpe(debut, fin)
    connexion.query(f"""
        CREATE OR REPLACE TABLE {table(TABLE_CUBE_CROISE_DPE)} CLUSTER BY mois, arrondissement AS
        WITH {cte}
        SELECT {mois("date_etablissement_dpe")} AS mois,
               arrondissement,
               pieces,
               {tranche_surface("surface_habitable_logement")} AS tranche_surface,
               IFNULL(classe_bilan_dpe, {litteral(ETIQUETTE_INCONNUE)}) AS etiquette,
               COUNT(*) AS nb_dpe,
               CURRENT_TIMESTAMP() AS date_maj
        FROM dpe
        WHERE arrondissement BETWEEN 1 AND 20
        GROUP BY mois, arrondissement, pieces, tranche_surface, etiquette
    """).result()

    nb_cellules = une_ligne(connexion, f"SELECT COUNT(*) AS n FROM {table(TABLE_CUBE_CROISE_DPE)}")["n"]
    if nb_cellules == 0:
        raise ValueError(f"{TABLE_CUBE_CROISE_DPE} : aucune ligne, sources ou période à vérifier")
    cube = une_ligne(connexion, f"""
        SELECT SUM(nb_dpe) AS dpe, SUM(IF(pieces IS NOT NULL, nb_dpe, 0)) AS avec_typologie FROM {table(TABLE_CUBE_CROISE_DPE)}
    """)
    source = une_ligne(connexion, f"""
        WITH {cte}
        SELECT COUNT(*) AS dpe, MIN(date_etablissement_dpe) AS premiere, MAX(date_etablissement_dpe) AS derniere
        FROM dpe WHERE arrondissement BETWEEN 1 AND 20
    """)
    if cube["dpe"] != source["dpe"]:
        raise ValueError(f"{TABLE_CUBE_CROISE_DPE} : {cube['dpe']} DPE agrégés pour {source['dpe']} dans la source")
    logger.info(
        "Table %s : %d cellules, %d DPE dont %d avec typologie, du %s au %s",
        TABLE_CUBE_CROISE_DPE, nb_cellules, cube["dpe"], cube["avec_typologie"], source["premiere"], source["derniere"],
    )
    afficher("DPE de la BDNB par étiquette (contrôle)", lignes(connexion, f"""
        SELECT etiquette, SUM(nb_dpe) AS dpe,
               ROUND(SUM(nb_dpe) / SUM(SUM(nb_dpe)) OVER () * 100, 1) AS pct
        FROM {table(TABLE_CUBE_CROISE_DPE)} GROUP BY 1 ORDER BY 1
    """))
    return nb_cellules

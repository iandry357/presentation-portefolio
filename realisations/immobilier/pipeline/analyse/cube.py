import logging

from google.cloud import bigquery

from pipeline.analyse.config import (
    BDNB_DPE, BDNB_REL_BATIMENT_ADRESSE, BDNB_REL_DPE_BATIMENT, BQ_DATASET, DATE_DEBUT_FENETRE, DATE_FIN_FENETRE,
    ETIQUETTE_INCONNUE, GCP_PROJECT_ID, GCP_SA_KEY_PATH, LIBELLES_SURFACE, PIECES_MAX, PRIX_M2_MAX, PRIX_M2_MIN,
    TABLE_DPE, TABLE_TYPOLOGIE, TABLE_VENTES, TRANCHES_SURFACE, VUE_VENTES_BATIMENT,
)

logger = logging.getLogger(__name__)

# Rappel : la vue des ventes ne filtre pas les bornes de prix ; elles sont appliquées ici.


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


def _trimestre(colonne):
    return f"CONCAT(CAST(EXTRACT(YEAR FROM {colonne}) AS STRING), '-T', CAST(EXTRACT(QUARTER FROM {colonne}) AS STRING))"


def _creer_table(client, nom, requete):
    """Crée ou remplace une table à partir d'une requête SELECT. Retourne le nombre de lignes."""
    client.query(
        f"CREATE OR REPLACE TABLE {_table(nom)} CLUSTER BY trimestre, arrondissement AS {requete}"
    ).result()
    nb_lignes = client.get_table(f"{GCP_PROJECT_ID}.{BQ_DATASET}.{nom}").num_rows
    if nb_lignes == 0:
        raise ValueError(f"{nom} : aucune ligne, sources ou fenêtre à vérifier")
    logger.info("Table %s : %d lignes", nom, nb_lignes)
    return nb_lignes


def construire_ventes(livraison, departement):
    """Une ligne par cellule (trimestre, arrondissement, pièces, tranche de surface, étiquette du bâtiment, rattachée)
    avec la liste triée des prix au m². Étiquette du bâtiment = médiane basse des classes de ses DPE (règle de la phase 3)."""
    client = _client()
    nb = _creer_table(client, TABLE_VENTES, f"""
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
                   c.classes[OFFSET(DIV(ARRAY_LENGTH(c.classes) - 1, 2))] AS etiquette_batiment
            FROM {_table(VUE_VENTES_BATIMENT)} v
            LEFT JOIN classe_batiment c USING (batiment_groupe_id)
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
               COUNT(*) AS nb_ventes,
               ARRAY_AGG(prix_m2 ORDER BY prix_m2) AS prix_m2,
               CURRENT_TIMESTAMP() AS date_maj
        FROM ventes
        WHERE arrondissement BETWEEN 1 AND 20
        GROUP BY trimestre, arrondissement, pieces, tranche_surface, etiquette, rattachee
    """)
    ligne = next(iter(client.query(
        f"SELECT SUM(nb_ventes) AS ventes, COUNTIF(rattachee) AS cellules_rattachees FROM {_table(TABLE_VENTES)}"
    ).result()))
    logger.info("Ventes dans le cube : %d (%d cellules rattachées sur %d)", ligne["ventes"], ligne["cellules_rattachees"], nb)
    return nb


def construire_dpe():
    """Une ligne par cellule (trimestre, arrondissement, pièces ADEME, tranche de surface, étiquette du logement).
    Un DPE relié à plusieurs bâtiments garde celui de plus petit identifiant ; un bâtiment à plusieurs adresses garde
    le plus petit arrondissement. pieces est NULL pour les DPE sans typologie."""
    client = _client()
    nb = _creer_table(client, TABLE_DPE, f"""
        WITH arrondissement_batiment AS (
            SELECT batiment_groupe_id,
                   MIN(SAFE_CAST(SUBSTR(cle_interop_adr, 1, 5) AS INT64) - 75100) AS arrondissement
            FROM {_table(BDNB_REL_BATIMENT_ADRESSE)}
            GROUP BY batiment_groupe_id
        ),
        lien AS (
            SELECT identifiant_dpe, MIN(batiment_groupe_id) AS batiment_groupe_id
            FROM {_table(BDNB_REL_DPE_BATIMENT)}
            GROUP BY identifiant_dpe
        ),
        dpe AS (
            SELECT d.date_etablissement_dpe, d.surface_habitable_logement, d.classe_bilan_dpe, a.arrondissement, t.pieces
            FROM {_table(BDNB_DPE)} d
            JOIN lien l USING (identifiant_dpe)
            JOIN arrondissement_batiment a USING (batiment_groupe_id)
            LEFT JOIN {_table(TABLE_TYPOLOGIE)} t USING (identifiant_dpe)
            WHERE d.date_etablissement_dpe BETWEEN DATE '{DATE_DEBUT_FENETRE}' AND DATE '{DATE_FIN_FENETRE}'
        )
        SELECT {_trimestre("date_etablissement_dpe")} AS trimestre,
               arrondissement,
               pieces,
               {_tranche_surface("surface_habitable_logement")} AS tranche_surface,
               IFNULL(classe_bilan_dpe, {_litteral(ETIQUETTE_INCONNUE)}) AS etiquette,
               COUNT(*) AS nb_dpe,
               CURRENT_TIMESTAMP() AS date_maj
        FROM dpe
        WHERE arrondissement BETWEEN 1 AND 20
        GROUP BY trimestre, arrondissement, pieces, tranche_surface, etiquette
    """)
    ligne = next(iter(client.query(
        f"SELECT SUM(nb_dpe) AS dpe, SUM(IF(pieces IS NOT NULL, nb_dpe, 0)) AS avec_typologie FROM {_table(TABLE_DPE)}"
    ).result()))
    logger.info("DPE dans le cube : %d dont %d avec typologie", ligne["dpe"], ligne["avec_typologie"])
    return nb

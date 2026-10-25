import logging

import polars as pl
from google.cloud import bigquery

from pipeline.loyers.config import (
    BDNB_DPE, BDNB_REL_DPE_BATIMENT, BQ_DATASET, CLUSTER, COLONNE_PERIODE, GCP_PROJECT_ID, GCP_SA_KEY_PATH,
    MOIS_ARRETE, PERIODES_EPOQUES, PIECES_MAX, PRIX_M2_MAX, PRIX_M2_MIN, SEUIL_ACCORD_PERIODE,
    STATUT_EPOQUE_INDETERMINEE, STATUT_HORS_QUARTIER, STATUT_PIECES_INVALIDES, STATUT_RATTACHEE, STATUT_SANS_BATIMENT,
    STATUT_SANS_COORDONNEES, STATUT_SANS_PERIODE, TABLE_DVF, TABLE_QUARTIERS, TABLE_RATTACHEMENT,
    TABLE_RATTACHEMENT_TRAVAIL, TABLE_REFERENCE, VUE_VENTES_BATIMENT, VUE_VENTES_LOYER,
)

logger = logging.getLogger(__name__)

COLONNES_RATTACHEMENT = [
    "livraison", "code_departement", "id_mutation", "id_quartier", "pieces", "annee_loyer", "batiment_groupe_id",
    "periode_batiment", "epoque", "epoque_ambigue", "periode_heterogene", "nb_dpe", "part_majoritaire", "statut",
]


def _client():
    return bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)


def _table(nom):
    return f"`{GCP_PROJECT_ID}.{BQ_DATASET}.{nom}`"


def _litteral(valeur):
    """Texte SQL entre apostrophes (échappées avec un antislash, comme en GoogleSQL)."""
    return "'" + str(valeur).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _booleen(valeur):
    return "TRUE" if valeur else "FALSE"


def _afficher(titre, lignes):
    print(f"\n== {titre}")
    with pl.Config(tbl_rows=-1, tbl_cols=-1):
        print(pl.DataFrame(lignes, infer_schema_length=None) if lignes else "(aucune ligne)")


def _verifier_periodes(client):
    """Arrêt si la BDNB contient une période absente de PERIODES_EPOQUES (vérifie aussi que la colonne existe)."""
    lignes = client.query(
        f"SELECT DISTINCT {COLONNE_PERIODE} AS periode FROM {_table(BDNB_DPE)} WHERE {COLONNE_PERIODE} IS NOT NULL"
    ).result()
    inconnues = sorted(r["periode"] for r in lignes if r["periode"] not in PERIODES_EPOQUES)
    if inconnues:
        raise ValueError(f"Périodes de construction absentes de PERIODES_EPOQUES : {inconnues}")


def _requete_rattachement(livraison, departement):
    l, d = _litteral(livraison), _litteral(departement)
    carte = ", ".join(
        f"STRUCT({_litteral(periode)} AS periode, {_litteral(epoque)} AS epoque, {_booleen(ambigue)} AS ambigue)"
        for periode, (epoque, ambigue) in PERIODES_EPOQUES.items()
    )
    return f"""
        WITH carte AS (
            SELECT * FROM UNNEST([{carte}])
        ),
        periodes AS (
            SELECT r.batiment_groupe_id, d.{COLONNE_PERIODE} AS periode, COUNT(*) AS n
            FROM {_table(BDNB_REL_DPE_BATIMENT)} r
            JOIN {_table(BDNB_DPE)} d USING (identifiant_dpe)
            WHERE d.{COLONNE_PERIODE} IS NOT NULL
            GROUP BY 1, 2
        ),
        comptes AS (
            SELECT *, SUM(n) OVER (PARTITION BY batiment_groupe_id) AS nb_dpe,
                   MAX(n) OVER (PARTITION BY batiment_groupe_id) AS nb_majoritaire
            FROM periodes
        ),
        batiment AS (
            SELECT batiment_groupe_id, ANY_VALUE(nb_dpe) AS nb_dpe, ANY_VALUE(nb_majoritaire) AS nb_majoritaire,
                   COUNTIF(n = nb_majoritaire) AS nb_ex_aequo,
                   ARRAY_AGG(IF(n = nb_majoritaire, periode, NULL) IGNORE NULLS LIMIT 1)[SAFE_OFFSET(0)] AS periode
            FROM comptes
            GROUP BY batiment_groupe_id
        ),
        ventes AS (
            SELECT v.livraison, v.code_departement, v.id_mutation, v.batiment_groupe_id,
                   IF(v.nombre_pieces_principales >= 1, LEAST(v.nombre_pieces_principales, {PIECES_MAX}), NULL) AS pieces,
                   EXTRACT(YEAR FROM v.date_mutation) - IF(EXTRACT(MONTH FROM v.date_mutation) < {MOIS_ARRETE}, 1, 0) AS annee_loyer,
                   IF(m.longitude IS NULL OR m.latitude IS NULL, NULL, ST_GEOGPOINT(m.longitude, m.latitude)) AS point
            FROM {_table(VUE_VENTES_BATIMENT)} v
            LEFT JOIN {_table(TABLE_DVF)} m
              ON m.livraison = v.livraison AND m.code_departement = v.code_departement
             AND m.id_mutation = v.id_mutation AND m.type_local = v.type_local
            WHERE v.livraison = {l} AND v.code_departement = {d}
        ),
        localisees AS (
            SELECT t.*, q.id_quartier
            FROM ventes t
            LEFT JOIN {_table(TABLE_QUARTIERS)} q ON ST_CONTAINS(q.geometrie, t.point)
        ),
        evaluees AS (
            SELECT t.*, b.periode, b.nb_dpe, b.nb_majoritaire, b.nb_ex_aequo, c.epoque, c.ambigue
            FROM localisees t
            LEFT JOIN batiment b ON b.batiment_groupe_id = t.batiment_groupe_id
            LEFT JOIN carte c ON c.periode = b.periode
        )
        SELECT livraison, code_departement, id_mutation, id_quartier, pieces, annee_loyer, batiment_groupe_id,
               periode AS periode_batiment,
               IF(nb_ex_aequo = 1, epoque, NULL) AS epoque,
               IF(nb_ex_aequo = 1, ambigue, NULL) AS epoque_ambigue,
               SAFE_DIVIDE(nb_majoritaire, nb_dpe) < {SEUIL_ACCORD_PERIODE} AS periode_heterogene,
               nb_dpe,
               SAFE_DIVIDE(nb_majoritaire, nb_dpe) AS part_majoritaire,
               CASE WHEN pieces IS NULL THEN {_litteral(STATUT_PIECES_INVALIDES)}
                    WHEN point IS NULL THEN {_litteral(STATUT_SANS_COORDONNEES)}
                    WHEN id_quartier IS NULL THEN {_litteral(STATUT_HORS_QUARTIER)}
                    WHEN batiment_groupe_id IS NULL THEN {_litteral(STATUT_SANS_BATIMENT)}
                    WHEN periode IS NULL THEN {_litteral(STATUT_SANS_PERIODE)}
                    WHEN nb_ex_aequo > 1 THEN {_litteral(STATUT_EPOQUE_INDETERMINEE)}
                    ELSE {_litteral(STATUT_RATTACHEE)} END AS statut
        FROM evaluees
    """


def _creer_vue(client):
    """Ventes rattachées (prix au m² et surface dans les bornes) avec leurs loyers de référence, meublé et non meublé."""
    client.query(f"""
        CREATE OR REPLACE VIEW {_table(VUE_VENTES_LOYER)} AS
        SELECT a.livraison, a.code_departement, a.id_mutation, v.date_mutation, v.valeur_fonciere, v.surface_reelle_bati,
               v.prix_m2, v.type_local,
               SAFE_CAST(SUBSTR(q.code_grand_quartier, 1, 5) AS INT64) - 75100 AS arrondissement,
               a.id_quartier, q.nom_quartier, a.pieces, a.epoque, a.epoque_ambigue, a.periode_heterogene, a.annee_loyer,
               l.meuble, l.loyer_reference, l.loyer_majore, l.loyer_minore,
               SAFE_DIVIDE(l.loyer_majore * v.surface_reelle_bati * 12, v.valeur_fonciere) AS rendement_brut
        FROM {_table(TABLE_RATTACHEMENT)} a
        JOIN {_table(VUE_VENTES_BATIMENT)} v USING (livraison, code_departement, id_mutation)
        JOIN {_table(TABLE_QUARTIERS)} q ON q.id_quartier = a.id_quartier
        LEFT JOIN {_table(TABLE_REFERENCE)} l
          ON l.annee = a.annee_loyer AND l.id_quartier = a.id_quartier AND l.pieces = a.pieces AND l.epoque = a.epoque
        WHERE a.statut = {_litteral(STATUT_RATTACHEE)} AND v.surface_reelle_bati > 0
          AND v.prix_m2 BETWEEN {PRIX_M2_MIN} AND {PRIX_M2_MAX}
    """).result()
    logger.info("Vue %s créée", VUE_VENTES_LOYER)


def rattacher(livraison, departement):
    """Rattachement des ventes du couple (livraison, département) aux quartiers, pièces et époques : table de travail,
    remplacement du couple en une transaction, puis vue. Retourne le nombre de lignes du couple."""
    client = _client()
    l, d = _litteral(livraison), _litteral(departement)
    cluster = ", ".join(CLUSTER)
    _verifier_periodes(client)

    client.query(
        f"CREATE OR REPLACE TABLE {_table(TABLE_RATTACHEMENT_TRAVAIL)} CLUSTER BY {cluster} "
        f"AS {_requete_rattachement(livraison, departement)}"
    ).result()
    nb_travail = client.get_table(f"{GCP_PROJECT_ID}.{BQ_DATASET}.{TABLE_RATTACHEMENT_TRAVAIL}").num_rows
    attendu = next(iter(client.query(
        f"SELECT COUNT(*) AS n FROM {_table(VUE_VENTES_BATIMENT)} WHERE livraison = {l} AND code_departement = {d}"
    ).result()))["n"]
    if attendu == 0:
        raise ValueError(f"Aucune vente de logement pour ({livraison}, {departement}) : DVF Etalab chargé et rattaché ?")
    if nb_travail != attendu:
        raise ValueError(f"{TABLE_RATTACHEMENT_TRAVAIL} : {nb_travail} lignes pour {attendu} ventes (jointure qui duplique des lignes ?)")
    logger.info("Table de travail %s : %d lignes", TABLE_RATTACHEMENT_TRAVAIL, nb_travail)

    client.query(
        f"CREATE TABLE IF NOT EXISTS {_table(TABLE_RATTACHEMENT)} CLUSTER BY {cluster} "
        f"AS SELECT * FROM {_table(TABLE_RATTACHEMENT_TRAVAIL)} WHERE FALSE"
    ).result()
    colonnes = ", ".join(COLONNES_RATTACHEMENT)
    client.query(f"""
        BEGIN
          BEGIN TRANSACTION;
          DELETE FROM {_table(TABLE_RATTACHEMENT)} WHERE livraison = {l} AND code_departement = {d};
          INSERT INTO {_table(TABLE_RATTACHEMENT)} ({colonnes}) SELECT {colonnes} FROM {_table(TABLE_RATTACHEMENT_TRAVAIL)};
          COMMIT TRANSACTION;
        EXCEPTION WHEN ERROR THEN
          ROLLBACK TRANSACTION;
          RAISE;
        END;
    """).result()
    nb = next(iter(client.query(
        f"SELECT COUNT(*) AS n FROM {_table(TABLE_RATTACHEMENT)} WHERE livraison = {l} AND code_departement = {d}"
    ).result()))["n"]
    if nb != nb_travail:
        raise ValueError(f"{TABLE_RATTACHEMENT} : {nb} lignes pour ({livraison}, {departement}) au lieu de {nb_travail}")
    logger.info("Table %s : %d lignes pour (%s, %s)", TABLE_RATTACHEMENT, nb, livraison, departement)
    client.delete_table(f"{GCP_PROJECT_ID}.{BQ_DATASET}.{TABLE_RATTACHEMENT_TRAVAIL}", not_found_ok=True)

    _creer_vue(client)
    return nb


def valider(livraison, departement):
    """Affiche la couverture du rattachement : statuts, marquages d'époque, concordance quartier / arrondissement,
    ventes rattachées sans loyer de référence, ventes de la vue."""
    client = _client()
    l, d = _litteral(livraison), _litteral(departement)
    couple = f"a.livraison = {l} AND a.code_departement = {d}"
    rattachee = _litteral(STATUT_RATTACHEE)

    def lignes(requete):
        return [dict(r) for r in client.query(requete).result()]

    _afficher("Ventes de logement par statut de rattachement", lignes(f"""
        SELECT a.statut, COUNT(*) AS ventes, ROUND(COUNT(*) / SUM(COUNT(*)) OVER () * 100, 1) AS pct
        FROM {_table(TABLE_RATTACHEMENT)} a WHERE {couple} GROUP BY 1 ORDER BY 2 DESC
    """))
    _afficher("Ventes rattachées par époque et marquage", lignes(f"""
        SELECT a.epoque, a.epoque_ambigue, a.periode_heterogene, COUNT(*) AS ventes,
               ROUND(COUNT(*) / SUM(COUNT(*)) OVER () * 100, 1) AS pct
        FROM {_table(TABLE_RATTACHEMENT)} a WHERE {couple} AND a.statut = {rattachee} GROUP BY 1, 2, 3 ORDER BY 1, 2, 3
    """))
    concordance = lignes(f"""
        SELECT COUNTIF(SAFE_CAST(SUBSTR(q.code_grand_quartier, 1, 5) AS INT64) = SAFE_CAST(v.code_commune AS INT64)) AS concordants,
               COUNT(*) AS comparees
        FROM {_table(TABLE_RATTACHEMENT)} a
        JOIN {_table(TABLE_QUARTIERS)} q ON q.id_quartier = a.id_quartier
        JOIN {_table(VUE_VENTES_BATIMENT)} v USING (livraison, code_departement, id_mutation)
        WHERE {couple}
    """)[0]
    if concordance["comparees"]:
        logger.info(
            "Quartier et arrondissement du DVF concordants : %d ventes sur %d (%.1f %%)",
            concordance["concordants"], concordance["comparees"], 100 * concordance["concordants"] / concordance["comparees"],
        )
    sans_loyer = lignes(f"""
        SELECT COUNT(*) AS n FROM {_table(TABLE_RATTACHEMENT)} a
        WHERE {couple} AND a.statut = {rattachee} AND NOT EXISTS (
            SELECT 1 FROM {_table(TABLE_REFERENCE)} l
            WHERE l.annee = a.annee_loyer AND l.id_quartier = a.id_quartier AND l.pieces = a.pieces AND l.epoque = a.epoque
        )
    """)[0]["n"]
    if sans_loyer:
        logger.warning("%d ventes rattachées sans loyer de référence (millésime de l'arrêté absent du jeu ?)", sans_loyer)
    dans_vue = lignes(f"""
        SELECT COUNT(DISTINCT id_mutation) AS ventes, COUNT(*) AS lignes FROM {_table(VUE_VENTES_LOYER)}
        WHERE livraison = {l} AND code_departement = {d}
    """)[0]
    logger.info("Vue %s : %d ventes (%d lignes avec meublé et non meublé)", VUE_VENTES_LOYER, dans_vue["ventes"], dans_vue["lignes"])

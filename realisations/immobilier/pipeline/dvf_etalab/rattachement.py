import logging

import polars as pl
from google.cloud import bigquery

from pipeline.dvf_etalab.config import (
    BDNB_DVF_REPRESENTATIF, BDNB_REL_ADRESSE, BDNB_REL_PARCELLE, BQ_DATASET, CLUSTER, GCP_PROJECT_ID,
    GCP_SA_KEY_PATH, NATURE_VENTE, SEUIL_PRECISION, TABLE_DVF, TABLE_QUALITE, TABLE_RATTACHEMENT,
    TABLE_RATTACHEMENT_TRAVAIL, TYPE_LOCAL_COMMERCIAL, TYPES_LOGEMENT, VUE_VENTES, VUE_VENTES_BATIMENT,
)

logger = logging.getLogger(__name__)

COLONNES_RATTACHEMENT = [
    "livraison", "code_departement", "id_mutation", "id_parcelle", "cle_adresse", "statut_parcelle",
    "statut_adresse", "nb_candidats_parcelle", "nb_candidats_adresse", "batiment_parcelle", "batiment_adresse",
    "batiment_groupe_id", "methode", "confiance", "confirme", "candidats_parcelle", "candidats_adresse",
]
COLONNES_QUALITE = [
    "livraison", "code_departement", "methode", "confirme", "retrouvees", "ok", "erreur", "ambigu",
    "non_candidat", "representatives", "non_retrouvees", "calcule_le",
]


def _client():
    return bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)


def _table(nom):
    return f"`{GCP_PROJECT_ID}.{BQ_DATASET}.{nom}`"


def _litteral(valeur):
    """Texte SQL entre apostrophes (échappées avec un antislash, comme en GoogleSQL)."""
    return "'" + str(valeur).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _booleen(valeur):
    return "CAST(NULL AS BOOL)" if valeur is None else ("TRUE" if valeur else "FALSE")


def _types_logement():
    return ", ".join(_litteral(t) for t in TYPES_LOGEMENT)


def _cle_adresse():
    """Expression SQL de la clé d'adresse au format BAN : commune_codevoie_numero (5 chiffres)[_suffixe].
    NULL si le numéro ou le code voie manquent. Partagée par la table de rattachement et les vues."""
    return """IF(adresse_numero IS NULL OR adresse_code_voie IS NULL, NULL,
              CONCAT(code_commune, '_', LOWER(adresse_code_voie), '_', LPAD(CAST(adresse_numero AS STRING), 5, '0'),
                     IF(IFNULL(adresse_suffixe, '') = '', '', CONCAT('_', LOWER(SUBSTR(adresse_suffixe, 1, 1))))))"""


def _requete_rattachement(livraison, departement):
    l, d = _litteral(livraison), _litteral(departement)
    return f"""
        WITH triplets AS (
            SELECT DISTINCT livraison, code_departement, id_mutation, id_parcelle, {_cle_adresse()} AS cle_adresse
            FROM {_table(TABLE_DVF)}
            WHERE livraison = {l} AND code_departement = {d} AND nature_mutation = {_litteral(NATURE_VENTE)}
        ),
        parcelles AS (
            SELECT parcelle_id,
                   ARRAY_AGG(DISTINCT batiment_groupe_id IGNORE NULLS) AS candidats,
                   COUNTIF(parcelle_principale = 1) AS nb_principal,
                   ARRAY_AGG(IF(parcelle_principale = 1, batiment_groupe_id, NULL) IGNORE NULLS LIMIT 1)[SAFE_OFFSET(0)]
                       AS batiment_principal
            FROM {_table(BDNB_REL_PARCELLE)}
            GROUP BY parcelle_id
        ),
        adresses AS (
            SELECT LOWER(cle_interop_adr) AS cle_adresse, ARRAY_AGG(DISTINCT batiment_groupe_id IGNORE NULLS) AS candidats
            FROM {_table(BDNB_REL_ADRESSE)}
            GROUP BY 1
        ),
        candidats AS (
            SELECT t.livraison, t.code_departement, t.id_mutation, t.id_parcelle, t.cle_adresse,
                   COALESCE(p.candidats, ARRAY<STRING>[]) AS candidats_parcelle,
                   COALESCE(a.candidats, ARRAY<STRING>[]) AS candidats_adresse,
                   p.nb_principal, p.batiment_principal
            FROM triplets t
            LEFT JOIN parcelles p ON p.parcelle_id = t.id_parcelle
            LEFT JOIN adresses a ON a.cle_adresse = t.cle_adresse
        ),
        statuts AS (
            SELECT *,
                   ARRAY_LENGTH(candidats_parcelle) AS nb_candidats_parcelle,
                   ARRAY_LENGTH(candidats_adresse) AS nb_candidats_adresse,
                   CASE WHEN ARRAY_LENGTH(candidats_parcelle) = 0 THEN 'absente'
                        WHEN ARRAY_LENGTH(candidats_parcelle) = 1 THEN 'unique'
                        WHEN nb_principal = 1 THEN 'principale'
                        ELSE 'ambigue' END AS statut_parcelle,
                   CASE WHEN ARRAY_LENGTH(candidats_adresse) = 0 THEN 'absente'
                        WHEN ARRAY_LENGTH(candidats_adresse) = 1 THEN 'unique'
                        ELSE 'ambigue' END AS statut_adresse,
                   ARRAY(SELECT x FROM UNNEST(candidats_parcelle) AS x WHERE x IN UNNEST(candidats_adresse)) AS communs
            FROM candidats
        ),
        propositions AS (
            SELECT *,
                   CASE statut_parcelle WHEN 'unique' THEN candidats_parcelle[SAFE_OFFSET(0)]
                                        WHEN 'principale' THEN batiment_principal END AS batiment_parcelle,
                   IF(statut_adresse = 'unique', candidats_adresse[SAFE_OFFSET(0)], NULL) AS batiment_adresse
            FROM statuts
        ),
        decisions AS (
            SELECT *,
                   CASE WHEN batiment_parcelle IS NOT NULL AND batiment_adresse IS NOT NULL
                             THEN IF(batiment_parcelle = batiment_adresse, 'concordent', 'divergent')
                        WHEN batiment_adresse IS NOT NULL THEN 'adresse seule'
                        WHEN batiment_parcelle IS NOT NULL THEN 'parcelle seule'
                        WHEN ARRAY_LENGTH(communs) = 1 THEN 'croisee'
                        WHEN nb_candidats_parcelle = 0 AND nb_candidats_adresse = 0 THEN 'aucune'
                        ELSE 'ambigue' END AS methode
            FROM propositions
        ),
        retenus AS (
            SELECT *,
                   CASE methode WHEN 'concordent' THEN batiment_parcelle
                                WHEN 'divergent' THEN batiment_adresse
                                WHEN 'adresse seule' THEN batiment_adresse
                                WHEN 'parcelle seule' THEN batiment_parcelle
                                WHEN 'croisee' THEN communs[SAFE_OFFSET(0)] END AS batiment_groupe_id
            FROM decisions
        )
        SELECT livraison, code_departement, id_mutation, id_parcelle, cle_adresse, statut_parcelle, statut_adresse,
               nb_candidats_parcelle, nb_candidats_adresse, batiment_parcelle, batiment_adresse, batiment_groupe_id,
               methode,
               CASE methode WHEN 'concordent' THEN 'haute' WHEN 'divergent' THEN 'a_arbitrer'
                            WHEN 'adresse seule' THEN 'moyenne' WHEN 'parcelle seule' THEN 'moyenne'
                            WHEN 'croisee' THEN 'moyenne' ELSE 'aucune' END AS confiance,
               IF(batiment_groupe_id IS NULL, NULL,
                  batiment_groupe_id IN UNNEST(candidats_parcelle) AND batiment_groupe_id IN UNNEST(candidats_adresse)) AS confirme,
               candidats_parcelle, candidats_adresse
        FROM retenus
    """


def _creer_vues(client):
    """Vues des ventes de logement (règle V1 exacte, doublons conservés) et des ventes rattachées à un bâtiment."""
    client.query(f"""
        CREATE OR REPLACE VIEW {_table(VUE_VENTES)} AS
        WITH lignes AS (
            SELECT livraison, code_departement, id_mutation, id_parcelle, adresse_numero, adresse_suffixe,
                   adresse_code_voie, code_commune, code_postal, date_mutation, valeur_fonciere, surface_reelle_bati,
                   nombre_pieces_principales, type_local,
                   COUNTIF(type_local IN ({_types_logement()}))
                       OVER (PARTITION BY livraison, code_departement, id_mutation) AS nb_logements,
                   LOGICAL_OR(type_local = {_litteral(TYPE_LOCAL_COMMERCIAL)})
                       OVER (PARTITION BY livraison, code_departement, id_mutation) AS a_commercial
            FROM {_table(TABLE_DVF)}
            WHERE nature_mutation = {_litteral(NATURE_VENTE)}
        )
        SELECT livraison, code_departement, id_mutation, id_parcelle, {_cle_adresse()} AS cle_adresse,
               date_mutation, valeur_fonciere, surface_reelle_bati,
               SAFE_DIVIDE(valeur_fonciere, IF(surface_reelle_bati > 0, surface_reelle_bati, NULL)) AS prix_m2,
               nombre_pieces_principales, type_local, code_commune, code_postal
        FROM lignes
        WHERE nb_logements = 1 AND NOT IFNULL(a_commercial, FALSE) AND type_local IN ({_types_logement()})
    """).result()
    client.query(f"""
        CREATE OR REPLACE VIEW {_table(VUE_VENTES_BATIMENT)} AS
        SELECT v.livraison, v.code_departement, v.id_mutation, v.date_mutation, v.valeur_fonciere,
               v.surface_reelle_bati, v.prix_m2, v.nombre_pieces_principales, v.type_local, v.code_commune,
               v.code_postal, r.batiment_groupe_id, r.methode, r.confiance, r.confirme
        FROM {_table(VUE_VENTES)} v
        LEFT JOIN {_table(TABLE_RATTACHEMENT)} r
            ON r.livraison = v.livraison AND r.code_departement = v.code_departement
           AND r.id_mutation = v.id_mutation AND r.id_parcelle = v.id_parcelle
           AND r.cle_adresse IS NOT DISTINCT FROM v.cle_adresse
    """).result()
    logger.info("Vues %s et %s créées", VUE_VENTES, VUE_VENTES_BATIMENT)


def _afficher(titre, lignes):
    print(f"\n== {titre}")
    with pl.Config(tbl_rows=-1, tbl_cols=-1):
        print(pl.DataFrame(lignes, infer_schema_length=None))


def rattacher(livraison, departement):
    """Rattachement des ventes du couple (livraison, département) aux bâtiments BDNB : table de travail, remplacement
    du couple en une transaction, puis vues. Retourne le nombre de lignes du couple."""
    client = _client()
    l, d = _litteral(livraison), _litteral(departement)
    cluster = ", ".join(CLUSTER)

    client.query(
        f"CREATE OR REPLACE TABLE {_table(TABLE_RATTACHEMENT_TRAVAIL)} CLUSTER BY {cluster} "
        f"AS {_requete_rattachement(livraison, departement)}"
    ).result()
    nb_travail = client.get_table(f"{GCP_PROJECT_ID}.{BQ_DATASET}.{TABLE_RATTACHEMENT_TRAVAIL}").num_rows
    if nb_travail == 0:
        raise ValueError(f"Aucune vente à rattacher pour ({livraison}, {departement}) : {TABLE_DVF} chargée ?")
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
    requete = f"SELECT COUNT(*) AS n FROM {_table(TABLE_RATTACHEMENT)} WHERE livraison = {l} AND code_departement = {d}"
    nb = next(iter(client.query(requete).result())).n
    if nb != nb_travail:
        raise ValueError(f"{TABLE_RATTACHEMENT} : {nb} lignes pour ({livraison}, {departement}) au lieu de {nb_travail}")
    logger.info("Table %s : %d lignes pour (%s, %s)", TABLE_RATTACHEMENT, nb, livraison, departement)
    client.delete_table(f"{GCP_PROJECT_ID}.{BQ_DATASET}.{TABLE_RATTACHEMENT_TRAVAIL}", not_found_ok=True)

    _creer_vues(client)
    lignes = [dict(r) for r in client.query(f"""
        SELECT IFNULL(methode, 'non_rattachee') AS methode, COUNT(*) AS ventes,
               ROUND(COUNT(*) / SUM(COUNT(*)) OVER () * 100, 1) AS pct
        FROM {_table(VUE_VENTES_BATIMENT)} WHERE livraison = {l} AND code_departement = {d}
        GROUP BY 1 ORDER BY 2 DESC
    """).result()]
    _afficher("Ventes de logement par méthode de rattachement", lignes)
    logger.info("Ventes de logement du couple : %d", sum(r["ventes"] for r in lignes))
    return nb


def _requete_validation(livraison, departement):
    l, d = _litteral(livraison), _litteral(departement)
    dvf = f"{_table(TABLE_DVF)}"
    return f"""
        WITH periode AS (
            SELECT MIN(date_mutation) AS debut, MAX(date_mutation) AS fin
            FROM {dvf} WHERE livraison = {l} AND code_departement = {d} AND nature_mutation = {_litteral(NATURE_VENTE)}
        ),
        representatives AS (
            SELECT ROW_NUMBER() OVER () AS rep_id, r.batiment_groupe_id AS bat_rep, r.date_mutation, r.valeur_fonciere
            FROM {_table(BDNB_DVF_REPRESENTATIF)} r CROSS JOIN periode p
            WHERE r.date_mutation BETWEEN p.debut AND p.fin
        ),
        mutations AS (
            SELECT DISTINCT id_mutation, date_mutation, valeur_fonciere
            FROM {dvf} WHERE livraison = {l} AND code_departement = {d} AND nature_mutation = {_litteral(NATURE_VENTE)}
        ),
        paires AS (
            SELECT r.rep_id, r.bat_rep, m.id_mutation
            FROM representatives r JOIN mutations m USING (date_mutation, valeur_fonciere)
        ),
        evaluation AS (
            SELECT p.rep_id, a.methode, a.confirme,
                   IFNULL(a.batiment_groupe_id = p.bat_rep, FALSE) AS bon,
                   a.batiment_groupe_id IS NOT NULL AS retenu,
                   p.bat_rep IN UNNEST(ARRAY_CONCAT(a.candidats_parcelle, a.candidats_adresse)) AS candidat
            FROM paires p
            JOIN {_table(TABLE_RATTACHEMENT)} a
              ON a.livraison = {l} AND a.code_departement = {d} AND a.id_mutation = p.id_mutation
        ),
        par_rep AS (
            SELECT rep_id,
                   LOGICAL_OR(bon) AS a_bon, LOGICAL_OR(retenu) AS a_retenu, LOGICAL_OR(candidat) AS a_candidat,
                   ARRAY_AGG(STRUCT(methode, confirme) ORDER BY IF(bon, 0, IF(retenu, 1, 2)) LIMIT 1)[OFFSET(0)] AS choix
            FROM evaluation GROUP BY rep_id
        ),
        classes AS (
            SELECT choix.methode AS methode, choix.confirme AS confirme,
                   CASE WHEN a_bon THEN 'ok' WHEN a_retenu THEN 'erreur' WHEN a_candidat THEN 'ambigu'
                        ELSE 'non_candidat' END AS classe
            FROM par_rep
        ),
        totaux AS (
            SELECT (SELECT COUNT(*) FROM representatives) AS representatives,
                   (SELECT COUNT(DISTINCT rep_id) FROM paires) AS trouvees
        )
        SELECT c.methode, c.confirme, COUNT(*) AS retrouvees,
               COUNTIF(c.classe = 'ok') AS ok, COUNTIF(c.classe = 'erreur') AS erreur,
               COUNTIF(c.classe = 'ambigu') AS ambigu, COUNTIF(c.classe = 'non_candidat') AS non_candidat,
               t.representatives, t.representatives - t.trouvees AS non_retrouvees
        FROM classes c CROSS JOIN totaux t
        GROUP BY c.methode, c.confirme, t.representatives, t.trouvees
        ORDER BY c.methode, c.confirme
    """


def _ecrire_qualite(client, livraison, departement, lignes):
    """Remplace les lignes du couple dans dvf_etalab_qualite, en une transaction."""
    l, d = _litteral(livraison), _litteral(departement)
    client.query(f"""
        CREATE TABLE IF NOT EXISTS {_table(TABLE_QUALITE)} (
            livraison STRING, code_departement STRING, methode STRING, confirme BOOL, retrouvees INT64, ok INT64,
            erreur INT64, ambigu INT64, non_candidat INT64, representatives INT64, non_retrouvees INT64,
            calcule_le TIMESTAMP
        )
    """).result()
    valeurs = ", ".join(
        f"STRUCT({_litteral(r['methode'])} AS methode, {_booleen(r['confirme'])} AS confirme, "
        f"{r['retrouvees']} AS retrouvees, {r['ok']} AS ok, {r['erreur']} AS erreur, {r['ambigu']} AS ambigu, "
        f"{r['non_candidat']} AS non_candidat, {r['representatives']} AS representatives, "
        f"{r['non_retrouvees']} AS non_retrouvees)"
        for r in lignes
    )
    client.query(f"""
        BEGIN
          BEGIN TRANSACTION;
          DELETE FROM {_table(TABLE_QUALITE)} WHERE livraison = {l} AND code_departement = {d};
          INSERT INTO {_table(TABLE_QUALITE)} ({", ".join(COLONNES_QUALITE)})
          SELECT {l}, {d}, q.methode, q.confirme, q.retrouvees, q.ok, q.erreur, q.ambigu, q.non_candidat,
                 q.representatives, q.non_retrouvees, CURRENT_TIMESTAMP()
          FROM UNNEST([{valeurs}]) AS q;
          COMMIT TRANSACTION;
        EXCEPTION WHEN ERROR THEN
          ROLLBACK TRANSACTION;
          RAISE;
        END;
    """).result()


def valider(livraison, departement):
    """Compare le bâtiment retenu à celui des ventes représentatives de la BDNB (même date, même prix).
    Écrit dvf_etalab_qualite et retourne la précision globale (ok / (ok + erreur))."""
    client = _client()
    lignes = [dict(r) for r in client.query(_requete_validation(livraison, departement)).result()]
    if not lignes:
        raise ValueError("Aucune vente représentative retrouvée : rattachement ou période à vérifier")

    ok = sum(r["ok"] for r in lignes)
    erreur = sum(r["erreur"] for r in lignes)
    precision = ok / (ok + erreur) if ok + erreur else None
    affichage = [
        {**r, "precision_pct": round(100 * r["ok"] / (r["ok"] + r["erreur"]), 1) if r["ok"] + r["erreur"] else None}
        for r in lignes
    ]
    _afficher("Validation sur les ventes représentatives, par méthode", affichage)
    logger.info(
        "Représentatives : %d, non retrouvées (date et prix) : %d, retrouvées : %d",
        lignes[0]["representatives"], lignes[0]["non_retrouvees"], sum(r["retrouvees"] for r in lignes),
    )
    if precision is None:
        logger.warning("Aucun rattachement retenu parmi les ventes représentatives")
    else:
        verdict = "OK" if precision >= SEUIL_PRECISION else "INSUFFISANTE"
        logger.info("Précision globale : %.1f %% (seuil %.0f %%) : %s", 100 * precision, 100 * SEUIL_PRECISION, verdict)

    _ecrire_qualite(client, livraison, departement, lignes)
    logger.info("Table %s mise à jour pour (%s, %s)", TABLE_QUALITE, livraison, departement)
    return precision

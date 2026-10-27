import logging

import polars as pl
from google.cloud import bigquery

from pipeline.bdnb_complement.config import (
    ATTENDU_BATIMENTS, ATTENDU_COPRO, ATTENDU_INONDATION, ATTENDU_SANS_ANNEE, BDNB_BATIMENT_GROUPE,
    BDNB_REL_BATIMENT_PARCELLE, BQ_DATASET, EPOQUE_DERNIERE, EPOQUES_BORNES, GCP_PROJECT_ID, GCP_SA_KEY_PATH,
    LIBELLES_COPRO, MODALITES_DEBORDEMENT, ORDRE_INONDATION, ORDRE_PATRIMOINE, PAS_ANNEE_ARRONDIE,
    TABLE_ATTRIBUTS_BATIMENT, TABLE_ATTRIBUTS_PARCELLE, TABLES, TRANCHES_COPRO, VALEURS_BOOLEENNES,
)

logger = logging.getLogger(__name__)


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


def _epoque(colonne):
    """Expression SQL : époque de l'encadrement d'après une année, NULL si l'année est absente."""
    cas = " ".join(f"WHEN {colonne} <= {borne} THEN {_litteral(libelle)}" for borne, libelle in EPOQUES_BORNES)
    return f"CASE WHEN {colonne} IS NULL THEN NULL {cas} ELSE {_litteral(EPOQUE_DERNIERE)} END"


def _taille_copro(colonne):
    """Expression SQL : tranche de taille de copropriété (bornes basses incluses), NULL si le nombre de logements est absent."""
    cas = " ".join(f"WHEN {colonne} < {borne} THEN {_litteral(libelle)}" for borne, libelle in zip(TRANCHES_COPRO, LIBELLES_COPRO))
    return f"CASE WHEN {colonne} IS NULL THEN NULL {cas} ELSE {_litteral(LIBELLES_COPRO[-1])} END"


def _rang(colonne, libelles):
    """Expression SQL : rang d'un libellé dans une liste ordonnée du moins au plus marqué."""
    return "CASE " + " ".join(f"WHEN {colonne} = {_litteral(l)} THEN {i}" for i, l in enumerate(libelles)) + " END"


def _libelle(colonne, libelles):
    """Expression SQL : libellé d'un rang (inverse de _rang)."""
    return "CASE " + " ".join(f"WHEN {colonne} = {i} THEN {_litteral(l)}" for i, l in enumerate(libelles)) + " END"


def _verifier_modalites(client):
    """Arrêt si une colonne de risques ou d'urbanisme contient une modalité imprévue (les libellés en dépendent)."""
    controles = [
        ("bdnb_risques", "alea_debordement", set(MODALITES_DEBORDEMENT)),
        ("bdnb_urbanisme", "monument_historique", VALEURS_BOOLEENNES),
        ("bdnb_urbanisme", "zone_plu_bati_patrimonial", VALEURS_BOLEENNES if False else VALEURS_BOOLEENNES),
    ]
    for table, colonne, attendues in controles:
        trouvees = {
            r["valeur"] for r in _lignes(
                client, f"SELECT DISTINCT CAST({colonne} AS STRING) AS valeur FROM {_table(table)} WHERE {colonne} IS NOT NULL"
            )
        }
        if trouvees - attendues:
            raise ValueError(f"{table}.{colonne} : modalités imprévues {sorted(trouvees - attendues)}")


def construire_batiments():
    """Une ligne par immeuble (bdnb_batiment_groupe) avec les attributs des cinq tables complémentaires.
    Une jointure sans correspondance donne NULL (inconnu), jamais « aucun »."""
    client = _client()
    _verifier_modalites(client)
    debordement = " ".join(f"WHEN alea_debordement = {_litteral(v)} THEN {_litteral(l)}" for v, l in MODALITES_DEBORDEMENT.items())
    client.query(f"""
        CREATE OR REPLACE TABLE {_table(TABLE_ATTRIBUTS_BATIMENT)} CLUSTER BY batiment_groupe_id AS
        WITH source AS (
            SELECT g.batiment_groupe_id,
                   IF(SAFE_CAST(f.annee_construction AS INT64) > 0, SAFE_CAST(f.annee_construction AS INT64), NULL) AS annee,
                   f.usage_niveau_1_txt AS usage_batiment,
                   SAFE_CAST(f.nb_niveau AS INT64) AS nb_niveau,
                   SAFE_CAST(f.nb_log AS INT64) AS nb_log,
                   SAFE_CAST(b.hauteur_mean AS FLOAT64) AS hauteur,
                   c.batiment_groupe_id IS NOT NULL AS copro_rnc,
                   SAFE_CAST(c.nb_log AS INT64) AS nb_log_rnc,
                   c.periode_construction_max AS periode_rnc,
                   k.batiment_groupe_id IS NOT NULL AS a_risques,
                   k.alea_debordement,
                   u.batiment_groupe_id IS NOT NULL AS a_urbanisme,
                   SAFE_CAST(u.monument_historique AS INT64) AS monument_historique,
                   SAFE_CAST(u.zone_plu_bati_patrimonial AS INT64) AS zone_plu
            FROM {_table(BDNB_BATIMENT_GROUPE)} g
            LEFT JOIN {_table('bdnb_ffo_bat')} f ON f.batiment_groupe_id = g.batiment_groupe_id
            LEFT JOIN {_table('bdnb_bdtopo_bat')} b ON b.batiment_groupe_id = g.batiment_groupe_id
            LEFT JOIN {_table('bdnb_rnc')} c ON c.batiment_groupe_id = g.batiment_groupe_id
            LEFT JOIN {_table('bdnb_risques')} k ON k.batiment_groupe_id = g.batiment_groupe_id
            LEFT JOIN {_table('bdnb_urbanisme')} u ON u.batiment_groupe_id = g.batiment_groupe_id
        )
        SELECT batiment_groupe_id,
               annee AS annee_construction,
               IF(annee IS NULL, NULL, MOD(annee, {PAS_ANNEE_ARRONDIE}) = 0) AS annee_arrondie,
               {_epoque("annee")} AS epoque_ff,
               usage_batiment, nb_niveau, nb_log, hauteur,
               copro_rnc,
               {_taille_copro("nb_log_rnc")} AS taille_copro,
               periode_rnc,
               CASE WHEN NOT a_risques THEN NULL {debordement} ELSE {_litteral(ORDRE_INONDATION[0])} END AS inondation,
               CASE WHEN NOT a_urbanisme THEN NULL
                    WHEN monument_historique = 1 THEN {_litteral(ORDRE_PATRIMOINE[2])}
                    WHEN zone_plu = 1 THEN {_litteral(ORDRE_PATRIMOINE[1])}
                    ELSE {_litteral(ORDRE_PATRIMOINE[0])} END AS patrimoine,
               CURRENT_TIMESTAMP() AS date_maj
        FROM source
    """).result()
    nb = client.get_table(f"{GCP_PROJECT_ID}.{BQ_DATASET}.{TABLE_ATTRIBUTS_BATIMENT}").num_rows
    logger.info("Table %s : %d lignes", TABLE_ATTRIBUTS_BATIMENT, nb)
    _valider_batiments(client)
    return nb


def _valider_batiments(client):
    """Compare aux comptages de l'exploration (arrêt au premier écart) et affiche les distributions."""
    table = _table(TABLE_ATTRIBUTS_BATIMENT)
    mesures = _lignes(client, f"""
        SELECT COUNT(*) AS batiments, COUNTIF(annee_construction IS NULL) AS sans_annee, COUNTIF(copro_rnc) AS copro_rnc
        FROM {table}
    """)[0]
    inondation = {r["inondation"]: r["n"] for r in _lignes(client, f"SELECT inondation, COUNT(*) AS n FROM {table} GROUP BY 1")}

    ecarts = []
    if mesures["batiments"] != ATTENDU_BATIMENTS:
        ecarts.append(f"{mesures['batiments']} immeubles au lieu de {ATTENDU_BATIMENTS}")
    if mesures["sans_annee"] != ATTENDU_SANS_ANNEE:
        ecarts.append(f"{mesures['sans_annee']} sans année au lieu de {ATTENDU_SANS_ANNEE}")
    if mesures["copro_rnc"] != ATTENDU_COPRO:
        ecarts.append(f"{mesures['copro_rnc']} copropriétés RNC au lieu de {ATTENDU_COPRO}")
    for libelle, attendu in ATTENDU_INONDATION.items():
        if inondation.get(libelle) != attendu:
            ecarts.append(f"inondation « {libelle} » : {inondation.get(libelle)} au lieu de {attendu}")
    if ecarts:
        raise ValueError(f"{TABLE_ATTRIBUTS_BATIMENT} : " + ", ".join(ecarts))
    logger.info("%s : comptages conformes à l'exploration", TABLE_ATTRIBUTS_BATIMENT)

    for colonne in ("epoque_ff", "annee_arrondie", "usage_batiment", "taille_copro", "inondation", "patrimoine"):
        _afficher(f"{colonne} (immeubles)", _lignes(client, f"""
            SELECT {colonne} AS modalite, COUNT(*) AS immeubles, ROUND(COUNT(*) / SUM(COUNT(*)) OVER () * 100, 1) AS pct
            FROM {table} GROUP BY 1 ORDER BY 1
        """))


def construire_parcelles():
    """Une ligne par parcelle : agrégat des immeubles liés (bdnb_rel_batiment_parcelle) et colonnes Sitadel.
    Les logements ne sont sommés que sur les immeubles dont c'est la parcelle principale (un immeuble peut toucher plusieurs
    parcelles). Jointure complète avec Sitadel : une parcelle sans immeuble mais avec permis est conservée (nb_immeubles = 0)."""
    client = _client()
    cle_sitadel = TABLES["bdnb_parcelle_sitadel"]["cluster"][0]
    client.query(f"""
        CREATE OR REPLACE TABLE {_table(TABLE_ATTRIBUTS_PARCELLE)} CLUSTER BY parcelle_id AS
        WITH lien AS (
            SELECT l.parcelle_id, l.parcelle_principale = 1 AS principale, a.batiment_groupe_id, a.annee_construction,
                   a.nb_niveau, a.nb_log, a.hauteur, a.copro_rnc, a.inondation, a.patrimoine
            FROM {_table(BDNB_REL_BATIMENT_PARCELLE)} l
            JOIN {_table(TABLE_ATTRIBUTS_BATIMENT)} a ON a.batiment_groupe_id = l.batiment_groupe_id
        ),
        parcelles AS (
            SELECT parcelle_id,
                   COUNT(DISTINCT batiment_groupe_id) AS nb_immeubles,
                   COUNTIF(principale) AS nb_immeubles_principaux,
                   MIN(annee_construction) AS annee_min, MAX(annee_construction) AS annee_max,
                   MAX(nb_niveau) AS nb_niveau_max, MAX(hauteur) AS hauteur_max,
                   SUM(IF(principale, nb_log, NULL)) AS nb_log_principaux,
                   LOGICAL_OR(copro_rnc) AS copro_rnc,
                   MAX({_rang("inondation", ORDRE_INONDATION)}) AS rang_inondation,
                   MAX({_rang("patrimoine", ORDRE_PATRIMOINE)}) AS rang_patrimoine
            FROM lien GROUP BY parcelle_id
        ),
        sitadel AS (
            SELECT *, TRUE AS dans_sitadel FROM {_table("bdnb_parcelle_sitadel")}
        )
        SELECT parcelle_id,
               COALESCE(p.nb_immeubles, 0) AS nb_immeubles,
               COALESCE(p.nb_immeubles_principaux, 0) AS nb_immeubles_principaux,
               p.annee_min, p.annee_max, p.nb_niveau_max, p.hauteur_max, p.nb_log_principaux, p.copro_rnc,
               {_libelle("p.rang_inondation", ORDRE_INONDATION)} AS inondation,
               {_libelle("p.rang_patrimoine", ORDRE_PATRIMOINE)} AS patrimoine,
               COALESCE(s.dans_sitadel, FALSE) AS dans_sitadel,
               s.* EXCEPT ({cle_sitadel}, dans_sitadel),
               CURRENT_TIMESTAMP() AS date_maj
        FROM parcelles p
        FULL OUTER JOIN sitadel s USING ({cle_sitadel})
    """).result()
    nb = client.get_table(f"{GCP_PROJECT_ID}.{BQ_DATASET}.{TABLE_ATTRIBUTS_PARCELLE}").num_rows
    logger.info("Table %s : %d lignes", TABLE_ATTRIBUTS_PARCELLE, nb)
    _valider_parcelles(client)
    return nb


def _valider_parcelles(client):
    """Affiche la couverture de la table par parcelle et le nombre de parcelles principales par immeuble."""
    table = _table(TABLE_ATTRIBUTS_PARCELLE)
    _afficher("Parcelles : couverture", _lignes(client, f"""
        SELECT COUNT(*) AS parcelles, COUNTIF(nb_immeubles > 0) AS avec_immeuble, COUNTIF(dans_sitadel) AS dans_sitadel,
               COUNTIF(nb_immeubles = 0 AND dans_sitadel) AS sitadel_sans_immeuble,
               COUNTIF(nb_immeubles > 0 AND nb_immeubles_principaux = 0) AS sans_principal
        FROM {table}
    """))
    _afficher("Immeubles par nombre de parcelles principales", _lignes(client, f"""
        SELECT principales, COUNT(*) AS immeubles
        FROM (
            SELECT g.batiment_groupe_id, COUNTIF(l.parcelle_principale = 1) AS principales
            FROM {_table(BDNB_BATIMENT_GROUPE)} g
            LEFT JOIN {_table(BDNB_REL_BATIMENT_PARCELLE)} l ON l.batiment_groupe_id = g.batiment_groupe_id
            GROUP BY g.batiment_groupe_id
        )
        GROUP BY principales ORDER BY principales
    """))

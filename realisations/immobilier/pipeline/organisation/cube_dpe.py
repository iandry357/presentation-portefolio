import logging

from pipeline.organisation.config import ETIQUETTE_INCONNUE, NIVEAUX_DPE, TABLE_CUBE_DPE, TABLE_DPE_ADEME
from pipeline.organisation.sql import afficher, client, fenetre, lignes, litteral, mois, table, une_ligne

logger = logging.getLogger(__name__)

# Libellés de la dimension « chauffage » (flag_chauffage_electrique de la collecte) ; NULL si l'énergie est absente
CHAUFFAGE_ELECTRIQUE = "électrique"
CHAUFFAGE_AUTRE = "autre"


def _niveau():
    """Expression SQL : niveau du DPE d'après sa méthode d'application, NULL si la méthode est absente."""
    cas = " ".join(f"WHEN {litteral(methode)} THEN {litteral(niveau)}" for methode, niveau in NIVEAUX_DPE.items())
    return f"CASE d.methode_application_dpe {cas} END"


def _verifier_methodes(connexion):
    """Arrêt si la table contient une méthode d'application absente de NIVEAUX_DPE (le niveau en dépend)."""
    connues = ", ".join(litteral(methode) for methode in NIVEAUX_DPE)
    inconnues = lignes(connexion, f"""
        SELECT DISTINCT methode_application_dpe AS methode FROM {table(TABLE_DPE_ADEME)}
        WHERE methode_application_dpe IS NOT NULL AND methode_application_dpe NOT IN ({connues})
    """)
    if inconnues:
        raise ValueError(f"Méthodes d'application absentes de NIVEAUX_DPE : {sorted(r['methode'] for r in inconnues)}")


def _cte(debut, fin):
    """CTE des DPE de la période, avec le niveau, le chauffage et les marqueurs actif (non remplacé) et remplaçant."""
    return f"""
        remplaces AS (
            SELECT DISTINCT numero_dpe_remplace AS numero_dpe FROM {table(TABLE_DPE_ADEME)}
            WHERE numero_dpe_remplace IS NOT NULL
        ),
        dpe AS (
            SELECT d.date_etablissement_dpe, d.arrondissement, d.etiquette_dpe, {_niveau()} AS niveau_dpe, d.type_batiment,
                   d.periode_construction,
                   CASE WHEN d.type_energie_principale_chauffage IS NULL THEN NULL
                        WHEN d.flag_chauffage_electrique THEN {litteral(CHAUFFAGE_ELECTRIQUE)}
                        ELSE {litteral(CHAUFFAGE_AUTRE)} END AS chauffage,
                   r.numero_dpe IS NULL AS actif,
                   d.numero_dpe_remplace IS NOT NULL AS remplacant
            FROM {table(TABLE_DPE_ADEME)} d
            LEFT JOIN remplaces r ON r.numero_dpe = d.numero_dpe
            WHERE {fenetre("d.date_etablissement_dpe", debut, fin)}
        )"""


def construire(debut, fin):
    """Une ligne par cellule (mois, arrondissement, étiquette, niveau, type de bâtiment, période de construction, chauffage,
    actif) avec le nombre de DPE et le nombre de DPE remplaçants. Modalité absente = NULL (« non renseigné » à la lecture).
    Retourne le nombre de cellules."""
    connexion = client()
    _verifier_methodes(connexion)
    cte = _cte(debut, fin)
    connexion.query(f"""
        CREATE OR REPLACE TABLE {table(TABLE_CUBE_DPE)} CLUSTER BY mois, arrondissement AS
        WITH {cte}
        SELECT {mois("date_etablissement_dpe")} AS mois,
               arrondissement,
               IFNULL(etiquette_dpe, {litteral(ETIQUETTE_INCONNUE)}) AS etiquette,
               niveau_dpe,
               type_batiment,
               periode_construction,
               chauffage,
               actif,
               COUNT(*) AS nb_dpe,
               COUNTIF(remplacant) AS nb_remplacants,
               CURRENT_TIMESTAMP() AS date_maj
        FROM dpe
        WHERE arrondissement BETWEEN 1 AND 20
        GROUP BY mois, arrondissement, etiquette, niveau_dpe, type_batiment, periode_construction, chauffage, actif
    """).result()

    nb_cellules = une_ligne(connexion, f"SELECT COUNT(*) AS n FROM {table(TABLE_CUBE_DPE)}")["n"]
    if nb_cellules == 0:
        raise ValueError(f"{TABLE_CUBE_DPE} : aucune ligne, table {TABLE_DPE_ADEME} ou période à vérifier")
    cube = une_ligne(connexion, f"""
        SELECT SUM(nb_dpe) AS dpe, SUM(IF(actif, nb_dpe, 0)) AS actifs, SUM(nb_remplacants) AS remplacants
        FROM {table(TABLE_CUBE_DPE)}
    """)
    attendu = une_ligne(connexion, f"""
        WITH {cte}
        SELECT COUNT(*) AS n FROM dpe WHERE arrondissement BETWEEN 1 AND 20
    """)["n"]
    if cube["dpe"] != attendu:
        raise ValueError(f"{TABLE_CUBE_DPE} : {cube['dpe']} DPE agrégés pour {attendu} dans {TABLE_DPE_ADEME}")
    logger.info(
        "Table %s : %d cellules, %d DPE dont %d actifs et %d remplaçants",
        TABLE_CUBE_DPE, nb_cellules, cube["dpe"], cube["actifs"], cube["remplacants"],
    )
    afficher("DPE actifs par niveau (contrôle)", lignes(connexion, f"""
        SELECT niveau_dpe, SUM(nb_dpe) AS dpe, ROUND(SUM(nb_dpe) / SUM(SUM(nb_dpe)) OVER () * 100, 1) AS pct
        FROM {table(TABLE_CUBE_DPE)} WHERE actif GROUP BY 1 ORDER BY 1
    """))
    afficher("DPE actifs par étiquette (contrôle)", lignes(connexion, f"""
        SELECT etiquette, SUM(nb_dpe) AS dpe, ROUND(SUM(nb_dpe) / SUM(SUM(nb_dpe)) OVER () * 100, 1) AS pct
        FROM {table(TABLE_CUBE_DPE)} WHERE actif GROUP BY 1 ORDER BY 1
    """))
    return nb_cellules

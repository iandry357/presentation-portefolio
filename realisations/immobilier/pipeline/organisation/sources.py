import logging

from google.api_core.exceptions import GoogleAPICallError

from pipeline.organisation.config import (
    BQ_DATASET, GCP_PROJECT_ID, SOURCES, SOURCES_BDNB_REPRISES, TABLE_BDNB_SOURCES, TABLE_PARAMETRES, TABLE_SOURCES,
)
from pipeline.organisation.sql import afficher, client, lignes, litteral, table, une_ligne

logger = logging.getLogger(__name__)


def _texte(valeur):
    return "CAST(NULL AS STRING)" if valeur is None else litteral(valeur)


def _date(valeur):
    return "CAST(NULL AS DATE)" if valeur is None else f"DATE {litteral(valeur)}"


def _entier(valeur):
    return "CAST(NULL AS INT64)" if valeur is None else str(int(valeur))


# Colonnes de la table, dans l'ordre, avec la conversion de chaque valeur en littéral SQL
COLONNES = [
    ("source", _texte), ("editeur", _texte), ("version", _texte), ("publiee", _texte), ("utilisee_par", _texte),
    ("limites", _texte), ("couverture", _texte), ("periode_debut", _date), ("periode_fin", _date),
    ("nb_lignes", _entier), ("chargee_le", _date), ("utilisee_depuis", _date), ("statut", _texte),
]


def _mesurer(connexion, mesure):
    """Période (minimum et maximum de la colonne), nombre de lignes et texte de couverture d'une source mesurable."""
    r = une_ligne(connexion, f"""
        SELECT MIN({mesure['colonne']}) AS debut, MAX({mesure['colonne']}) AS fin, COUNT(*) AS nb
        FROM {table(mesure['table'])}
    """)
    if mesure["type"] == "annee":
        couverture = f"arrêté {r['debut']}" if r["debut"] == r["fin"] else f"arrêtés {r['debut']} à {r['fin']}"
        return {"periode_debut": None, "periode_fin": None, "couverture": couverture, "nb_lignes": r["nb"]}
    return {
        "periode_debut": r["debut"], "periode_fin": r["fin"], "nb_lignes": r["nb"],
        "couverture": f"du {r['debut']} au {r['fin']}",
    }


def _chargee_le(connexion, nom_table):
    """Date de dernière modification de la table (chargement ou reconstruction)."""
    return connexion.get_table(f"{GCP_PROJECT_ID}.{BQ_DATASET}.{nom_table}").modified.date().isoformat()


def _fiche(connexion, fiche, utilisee_depuis):
    ligne = {cle: fiche[cle] for cle in ("source", "editeur", "version", "publiee", "utilisee_par", "limites")}
    ligne.update(
        couverture=None, periode_debut=None, periode_fin=None, nb_lignes=None, chargee_le=None,
        utilisee_depuis=utilisee_depuis if fiche["fenetre"] else None,
        statut="chargée" if fiche["chargee"] else "consultée à la demande",
    )
    try:
        if fiche["mesure"]:
            ligne.update(_mesurer(connexion, fiche["mesure"]))
        if fiche["chargee"]:
            ligne["chargee_le"] = _chargee_le(connexion, fiche["chargee"])
    except GoogleAPICallError as e:
        logger.warning("Source %s non mesurable (table ou colonne absente ?) : %s", fiche["source"], e)
        ligne.update(statut="non chargée", utilisee_depuis=None)
    return ligne


def _reprises(connexion):
    """Fiches des sources décrites par la BDNB (bdnb_sources) : version et couverture reprises telles quelles."""
    existantes = {
        r["source"]: r for r in lignes(connexion, f"SELECT source, millesime, couverture FROM {table(TABLE_BDNB_SOURCES)}")
    }
    resultat = []
    for nom, partie in SOURCES_BDNB_REPRISES:
        if nom not in existantes:
            logger.warning("Source %s absente de %s : fiche ignorée", nom, TABLE_BDNB_SOURCES)
            continue
        resultat.append({
            "source": nom, "editeur": None, "version": existantes[nom]["millesime"], "publiee": None,
            "utilisee_par": partie, "limites": None, "couverture": existantes[nom]["couverture"],
            "periode_debut": None, "periode_fin": None, "nb_lignes": None, "chargee_le": None,
            "utilisee_depuis": None, "statut": "reprise de la BDNB",
        })
    return resultat


def construire():
    """Une ligne par source (fiches de SOURCES, puis sources reprises de la BDNB). Lit org_parametres : à construire après les cubes."""
    connexion = client()
    try:
        utilisee_depuis = une_ligne(connexion, f"SELECT date_debut FROM {table(TABLE_PARAMETRES)}")["date_debut"]
    except GoogleAPICallError as e:
        raise RuntimeError(f"{TABLE_PARAMETRES} absente : lancer d'abord --etape cubes ({e})") from e

    fiches = [_fiche(connexion, fiche, utilisee_depuis) for fiche in SOURCES] + _reprises(connexion)
    structures = ", ".join(
        "STRUCT(" + ", ".join(f"{convertir(fiche[nom])} AS {nom}" for nom, convertir in COLONNES) + ")" for fiche in fiches
    )
    connexion.query(
        f"CREATE OR REPLACE TABLE {table(TABLE_SOURCES)} AS SELECT *, CURRENT_TIMESTAMP() AS date_maj FROM UNNEST([{structures}])"
    ).result()
    nb = une_ligne(connexion, f"SELECT COUNT(*) AS n FROM {table(TABLE_SOURCES)}")["n"]
    if nb != len(fiches):
        raise ValueError(f"{TABLE_SOURCES} : {nb} lignes pour {len(fiches)} fiches")
    logger.info("Table %s : %d sources", TABLE_SOURCES, nb)
    afficher("Sources (contrôle)", lignes(connexion, f"""
        SELECT source, statut, couverture, nb_lignes, chargee_le FROM {table(TABLE_SOURCES)}
    """))
    return nb

import logging

from google.api_core.exceptions import GoogleAPICallError

from pipeline.organisation.config import (
    BDNB_DPE, PRIX_M2_MAX, PRIX_M2_MIN, TABLE_CUBE_CROISE_DPE, TABLE_CUBE_CROISE_VENTES, TABLE_CUBE_DVF, TABLE_CUBE_LOYERS,
    TABLE_DPE_ADEME, TABLE_PARAMETRES, TABLE_QUALITE, TOLERANCE_DEBUT_JOURS, VUE_DVF_BRUT,
)
from pipeline.organisation.sql import afficher, client, fenetre, lignes, litteral, table, une_ligne

logger = logging.getLogger(__name__)

# Indicateurs de qualité de la page Qualité : (partie, indicateur, valeur, unité, commentaire), mesurés dans les tables.


def _pct(partie, total):
    return round(100 * partie / total, 1) if total else None


def _dvf(connexion, p):
    """Ventes de logement de la période : retenues par le cube, et ventes écartées (sans prix, hors bornes, hors arrondissements)."""
    periode = (
        f"livraison = {litteral(p['livraison'])} AND code_departement = {litteral(p['code_departement'])} "
        f"AND {fenetre('date_mutation', p['date_debut'], p['date_fin'])}"
    )
    r = une_ligne(connexion, f"""
        SELECT COUNT(*) AS total,
               COUNTIF(prix_m2 IS NULL) AS sans_prix,
               COUNTIF(prix_m2 NOT BETWEEN {PRIX_M2_MIN} AND {PRIX_M2_MAX}) AS hors_bornes,
               COUNTIF(prix_m2 BETWEEN {PRIX_M2_MIN} AND {PRIX_M2_MAX}
                       AND (arrondissement IS NULL OR arrondissement NOT BETWEEN 1 AND 20)) AS hors_arrondissements
        FROM {table(VUE_DVF_BRUT)} WHERE {periode}
    """)
    cube = une_ligne(connexion, f"""
        SELECT SUM(nb_ventes) AS retenues, SUM(IF(pieces IS NULL, nb_ventes, 0)) AS sans_pieces FROM {table(TABLE_CUBE_DVF)}
    """)
    ecart = r["total"] - cube["retenues"] - r["sans_prix"] - r["hors_bornes"] - r["hors_arrondissements"]
    if ecart:
        logger.warning("DVF : %d ventes de la période ne sont ni retenues ni écartées (comptage à vérifier)", ecart)
    total = r["total"]
    return [
        ("DVF", "Ventes de logement dans la période", total, "ventes", "règle V1 : un seul logement, aucun local commercial"),
        ("DVF", "Ventes retenues dans les analyses", cube["retenues"], "ventes", f"{_pct(cube['retenues'], total)} % des ventes de la période"),
        ("DVF", "Ventes sans prix au m²", r["sans_prix"], "ventes", "surface bâtie absente ou nulle"),
        ("DVF", "Ventes hors bornes de prix", r["hors_bornes"], "ventes", f"prix au m² hors de {PRIX_M2_MIN} à {PRIX_M2_MAX} €"),
        ("DVF", "Ventes hors des 20 arrondissements", r["hors_arrondissements"], "ventes", None),
        ("DVF", "Ventes retenues sans nombre de pièces", cube["sans_pieces"], "ventes", "écartées des analyses par nombre de pièces"),
    ]


def _dpe_ademe(connexion, p):
    """DPE de l'ADEME collectés : remplaçants, sans arrondissement, répartition par méthode."""
    r = une_ligne(connexion, f"""
        SELECT COUNT(*) AS total, COUNTIF(numero_dpe_remplace IS NOT NULL) AS remplacants,
               COUNTIF(arrondissement IS NULL) AS sans_arrondissement
        FROM {table(TABLE_DPE_ADEME)}
    """)
    total = r["total"]
    resultat = [
        ("DPE ADEME", "DPE collectés", total, "DPE", "depuis le début de la collecte"),
        ("DPE ADEME", "DPE remplaçants", r["remplacants"], "DPE", f"{_pct(r['remplacants'], total)} % : ils remplacent un DPE plus ancien, resté dans le jeu"),
        ("DPE ADEME", "DPE sans arrondissement", r["sans_arrondissement"], "DPE", "code INSEE absent ou hors de Paris"),
    ]
    for ligne in lignes(connexion, f"""
        SELECT methode_application_dpe AS methode, COUNT(*) AS n FROM {table(TABLE_DPE_ADEME)} GROUP BY 1 ORDER BY 2 DESC
    """):
        resultat.append((
            "DPE ADEME", f"DPE par méthode : {ligne['methode'] or 'non renseignée'}", ligne["n"], "DPE",
            f"{_pct(ligne['n'], total)} % des DPE collectés",
        ))
    return resultat


def _croise_cubes(connexion, p):
    """Ventes rattachées à un bâtiment et DPE avec typologie, d'après les cubes du Croisé."""
    ventes = une_ligne(connexion, f"""
        SELECT SUM(nb_ventes) AS total, SUM(IF(rattachee, nb_ventes, 0)) AS rattachees FROM {table(TABLE_CUBE_CROISE_VENTES)}
    """)
    dpe = une_ligne(connexion, f"""
        SELECT SUM(nb_dpe) AS total, SUM(IF(pieces IS NOT NULL, nb_dpe, 0)) AS avec_typologie FROM {table(TABLE_CUBE_CROISE_DPE)}
    """)
    return [
        ("Croisé", "Ventes rattachées à un bâtiment", ventes["rattachees"], "ventes", f"{_pct(ventes['rattachees'], ventes['total'])} % des ventes retenues"),
        ("Croisé", "DPE de la BDNB dans la période", dpe["total"], "DPE", "avec arrondissement"),
        ("Croisé", "DPE de la BDNB avec typologie (pièces)", dpe["avec_typologie"], "DPE", f"{_pct(dpe['avec_typologie'], dpe['total'])} % : le nombre de pièces est rarement renseigné"),
    ]


def _croise_dpe_ademe(connexion, p):
    """Comparaison des numéros de DPE : BDNB contre ADEME, sur la période et jusqu'à la date de coupure de la BDNB."""
    r = une_ligne(connexion, f"""
        WITH bdnb AS (
            SELECT identifiant_dpe FROM {table(BDNB_DPE)}
            WHERE {fenetre("date_etablissement_dpe", p["date_debut"], p["date_fin"])}
        ),
        ademe AS (
            SELECT numero_dpe FROM {table(TABLE_DPE_ADEME)}
            WHERE {fenetre("date_etablissement_dpe", p["date_debut"], p["date_fin"])}
              AND date_etablissement_dpe <= (SELECT MAX(date_etablissement_dpe) FROM {table(BDNB_DPE)})
        )
        SELECT (SELECT COUNT(*) FROM bdnb) AS bdnb,
               (SELECT COUNT(*) FROM ademe) AS ademe,
               (SELECT COUNT(*) FROM bdnb b WHERE NOT EXISTS (SELECT 1 FROM ademe a WHERE a.numero_dpe = b.identifiant_dpe)) AS bdnb_seul,
               (SELECT COUNT(*) FROM ademe a WHERE NOT EXISTS (SELECT 1 FROM bdnb b WHERE b.identifiant_dpe = a.numero_dpe)) AS ademe_seul
    """)
    return [
        ("Croisé", "DPE de la BDNB (période, sans condition d'adresse)", r["bdnb"], "DPE", None),
        ("Croisé", "DPE de l'ADEME sur la même période, jusqu'à la coupure de la BDNB", r["ademe"], "DPE", None),
        ("Croisé", "DPE de la BDNB absents de l'ADEME", r["bdnb_seul"], "DPE", f"{_pct(r['bdnb_seul'], r['bdnb'])} % de la BDNB"),
        ("Croisé", "DPE de l'ADEME absents de la BDNB", r["ademe_seul"], "DPE", f"{_pct(r['ademe_seul'], r['ademe'])} % de l'ADEME"),
    ]


def _loyers(connexion, p):
    """Ventes avec loyer de référence, et répartition par année d'arrêté."""
    cube = une_ligne(connexion, f"""
        SELECT SUM(IF(meuble, 0, nb_ventes)) AS ventes FROM {table(TABLE_CUBE_LOYERS)}
    """)
    dvf = une_ligne(connexion, f"SELECT SUM(nb_ventes) AS ventes FROM {table(TABLE_CUBE_DVF)}")["ventes"]
    resultat = [
        ("Loyers", "Ventes avec loyer de référence", cube["ventes"], "ventes", f"{_pct(cube['ventes'], dvf)} % des ventes retenues"),
    ]
    for ligne in lignes(connexion, f"""
        SELECT annee_loyer, SUM(IF(meuble, 0, nb_ventes)) AS ventes FROM {table(TABLE_CUBE_LOYERS)} GROUP BY 1 ORDER BY 1
    """):
        resultat.append((
            "Loyers", f"Ventes par année d'arrêté : {ligne['annee_loyer']}", ligne["ventes"], "ventes",
            "les ventes avant juillet prennent l'arrêté de l'année précédente",
        ))
    return resultat


def _coherence(connexion, p):
    """Écart entre la période paramétrée et le premier jour réellement chargé de la table ADEME."""
    jours = une_ligne(connexion, f"""
        SELECT DATE_DIFF(MIN(date_etablissement_dpe), DATE {litteral(p['date_debut'])}, DAY) AS jours FROM {table(TABLE_DPE_ADEME)}
    """)["jours"]
    commentaire = (
        "cohérent" if jours <= TOLERANCE_DEBUT_JOURS
        else f"la période paramétrée démarre plus de {TOLERANCE_DEBUT_JOURS} jours avant les DPE ADEME chargés : la partie DPE est incomplète"
    )
    return [("Cohérence", "Jours entre le début paramétré et le premier DPE ADEME chargé", jours, "jours", commentaire)]


def _decimal(valeur):
    return "CAST(NULL AS FLOAT64)" if valeur is None else f"CAST({float(valeur)} AS FLOAT64)"


def construire():
    """Une ligne par indicateur. Un groupe dont une table manque (typiquement org_dpe_ademe) est ignoré avec un avertissement.
    À construire après les cubes (lit org_parametres et les cubes)."""
    connexion = client()
    try:
        p = une_ligne(connexion, f"SELECT * FROM {table(TABLE_PARAMETRES)}")
    except GoogleAPICallError as e:
        raise RuntimeError(f"{TABLE_PARAMETRES} absente : lancer d'abord --etape cubes ({e})") from e

    indicateurs = []
    for nom, fonction in (
        ("DVF", _dvf), ("DPE ADEME", _dpe_ademe), ("Croisé (cubes)", _croise_cubes),
        ("Croisé (BDNB contre ADEME)", _croise_dpe_ademe), ("Loyers", _loyers), ("Cohérence", _coherence),
    ):
        try:
            indicateurs += fonction(connexion, p)
        except GoogleAPICallError as e:
            logger.warning("Indicateurs %s ignorés (table ou colonne absente ?) : %s", nom, e)

    if not indicateurs:
        raise RuntimeError("Aucun indicateur calculé")
    structures = ", ".join(
        f"STRUCT({litteral(partie)} AS partie, {litteral(indicateur)} AS indicateur, {_decimal(valeur)} AS valeur, "
        f"{litteral(unite)} AS unite, "
        f"{'CAST(NULL AS STRING)' if commentaire is None else litteral(commentaire)} AS commentaire)"
        for partie, indicateur, valeur, unite, commentaire in indicateurs
    )
    connexion.query(
        f"CREATE OR REPLACE TABLE {table(TABLE_QUALITE)} AS SELECT *, CURRENT_TIMESTAMP() AS date_maj FROM UNNEST([{structures}])"
    ).result()
    nb = une_ligne(connexion, f"SELECT COUNT(*) AS n FROM {table(TABLE_QUALITE)}")["n"]
    if nb != len(indicateurs):
        raise ValueError(f"{TABLE_QUALITE} : {nb} lignes pour {len(indicateurs)} indicateurs")
    logger.info("Table %s : %d indicateurs", TABLE_QUALITE, nb)
    afficher("Qualité (contrôle)", lignes(connexion, f"SELECT partie, indicateur, valeur, unite FROM {table(TABLE_QUALITE)}"))
    return nb

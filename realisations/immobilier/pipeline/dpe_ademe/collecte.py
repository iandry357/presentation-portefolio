import logging
import time
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd
import requests

from pipeline.dpe_ademe.config import (
    CHAMP_DEPARTEMENT, CHAMPS_API, COLONNE_PARTITION, DOSSIER_CACHE, DPE_API, FICHIER_CURSEUR, FICHIER_TERMINE,
    MAX_TENTATIVES, NB_FLUX, PAUSE_TENTATIVE, TAILLE_PAGE, TIMEOUT,
)

logger = logging.getLogger(__name__)

# Collecte par tranches mensuelles de la date d'établissement (COLONNE_PARTITION), en parallèle : chaque tranche a ses pages
# (page_AAAA-MM_NNN.csv), son curseur et son marqueur de fin, nommés par le mois. La première tranche commence à `depuis`,
# la dernière est ouverte (jusqu'à la dernière date).


def _get(url, params=None):
    for tentative in range(1, MAX_TENTATIVES + 1):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            logger.warning("Tentative %d/%d échouée : %s", tentative, MAX_TENTATIVES, e)
            if tentative == MAX_TENTATIVES:
                raise
            time.sleep(PAUSE_TENTATIVE * tentative)


def _qs(departement, debut, fin):
    """Requête de l'API : département et date d'établissement entre debut et fin incluses (fin : '*' = sans borne)."""
    return f"{CHAMP_DEPARTEMENT}:{departement} AND {COLONNE_PARTITION}:[{debut} TO {fin}]"


def _tranches(departement, depuis):
    """Tranches mensuelles de `depuis` au mois courant : (nom AAAA-MM, requête). La dernière est ouverte."""
    debut, aujourdhui = date.fromisoformat(depuis), date.today()
    tranches, annee, mois = [], debut.year, debut.month
    while (annee, mois) <= (aujourdhui.year, aujourdhui.month):
        premier = debut if (annee, mois) == (debut.year, debut.month) else date(annee, mois, 1)
        courant = (annee, mois) == (aujourdhui.year, aujourdhui.month)
        dernier = "*" if courant else date(annee, mois, monthrange(annee, mois)[1]).isoformat()
        tranches.append((f"{annee}-{mois:02d}", _qs(departement, premier.isoformat(), dernier)))
        annee, mois = (annee + 1, 1) if mois == 12 else (annee, mois + 1)
    if not tranches:
        raise ValueError(f"Date de début {depuis} dans le futur")
    return tranches


def _params_base(qs):
    return {"qs": qs, "size": TAILLE_PAGE, "select": ",".join(CHAMPS_API)}


def _total(qs):
    """Nombre de DPE annoncé par l'API pour une requête (requête d'une ligne)."""
    return _get(f"{DPE_API}/lines", {"qs": qs, "size": 1, "select": CHAMPS_API[0]})["total"]


def _ecrire_page(lignes, nom, numero_page):
    pd.DataFrame(lignes).reindex(columns=CHAMPS_API).to_csv(
        DOSSIER_CACHE / f"page_{nom}_{numero_page:03d}.csv", index=False
    )


def _vider_cache():
    """Supprime les pages et les marqueurs de la collecte ; rien d'autre dans le dossier."""
    fichiers = [
        *DOSSIER_CACHE.glob("page_*.csv"),
        *DOSSIER_CACHE.glob(f"*{FICHIER_CURSEUR}"),
        *DOSSIER_CACHE.glob(f"*{FICHIER_TERMINE}"),
    ]
    for fichier in fichiers:
        fichier.unlink(missing_ok=True)


def _collecter_tranche(nom, qs, nb_pages=None, reprendre=False):
    """Collecte une tranche. Retourne (pages, total de la tranche relu à la fin ; None pour un essai).
    nb_pages : essai, les N premières pages seulement, sans curseur ni marqueur."""
    curseur, termine = DOSSIER_CACHE / f"{nom}_{FICHIER_CURSEUR}", DOSSIER_CACHE / f"{nom}_{FICHIER_TERMINE}"
    pages = sorted(DOSSIER_CACHE.glob(f"page_{nom}_*.csv"))

    if reprendre and not nb_pages and termine.exists():
        return len(pages), int(termine.read_text())
    if reprendre and not nb_pages and curseur.exists():
        url, params = curseur.read_text().strip(), None
        numero_page = len(pages)
        logger.info("Tranche %s : reprise après la page %d", nom, numero_page)
    else:
        for page in pages:
            page.unlink()
        url, params = f"{DPE_API}/lines", _params_base(qs)
        numero_page = 0

    while url:
        data = _get(url, params)
        lignes = data["results"]
        if not lignes:
            break
        numero_page += 1
        _ecrire_page(lignes, nom, numero_page)
        url, params = data.get("next"), None
        logger.info("Tranche %s, page %d : %d lignes", nom, numero_page, len(lignes))
        if nb_pages:
            if numero_page >= nb_pages:
                return numero_page, None
        elif url:
            curseur.write_text(url)

    total = _total(qs)
    curseur.unlink(missing_ok=True)
    termine.write_text(str(total))
    logger.info("Tranche %s terminée : %d pages, %d DPE", nom, numero_page, total)
    return numero_page, total


def collecter(departement, depuis, nb_pages=None, reprendre=False):
    """Télécharge dans DOSSIER_CACHE les DPE du département établis depuis `depuis` (un CSV de CHAMPS_API par page).
    Retourne le total collecté (None pour un essai). nb_pages : essai, N pages de la première tranche seulement
    (cache vidé, collecte non marquée terminée). reprendre : continue une collecte interrompue, ou ignore une collecte terminée."""
    DOSSIER_CACHE.mkdir(parents=True, exist_ok=True)
    termine = DOSSIER_CACHE / FICHIER_TERMINE
    if reprendre and not nb_pages and termine.exists():
        logger.info("Collecte déjà terminée, téléchargement ignoré")
        return int(termine.read_text())
    if nb_pages or not reprendre:
        _vider_cache()

    tranches = _tranches(departement, depuis)
    if nb_pages:
        _collecter_tranche(*tranches[0], nb_pages=nb_pages)
        return None

    attendu_au_debut = _total(_qs(departement, depuis, "*"))
    logger.info("%d tranches, %d flux, %d DPE annoncés depuis %s", len(tranches), NB_FLUX, attendu_au_debut, depuis)
    with ThreadPoolExecutor(max_workers=NB_FLUX) as pool:
        resultats = list(pool.map(lambda t: _collecter_tranche(*t, reprendre=reprendre), tranches))
    pages, total = sum(p for p, _ in resultats), sum(t for _, t in resultats)
    if total < attendu_au_debut:
        raise ValueError(f"{total} DPE collectés pour {attendu_au_debut} annoncés au lancement : tranches à vérifier")
    termine.write_text(str(total))
    logger.info("Collecte terminée : %d pages, %d DPE (%+d depuis le lancement)", pages, total, total - attendu_au_debut)
    return total

import logging
import time

import pandas as pd
import requests

from pipeline.config import (
    DPE_API, DPE_CACHE_DIR, DPE_CHAMPS_API, DPE_DEPARTEMENT,
    DPE_MAX_TENTATIVES, DPE_TAILLE_PAGE, DPE_TIMEOUT,
)

logger = logging.getLogger(__name__)

CURSEUR = DPE_CACHE_DIR / "curseur.txt"
TERMINE = DPE_CACHE_DIR / "termine.txt"


def _get(url, params=None):
    for tentative in range(1, DPE_MAX_TENTATIVES + 1):
        try:
            r = requests.get(url, params=params, timeout=DPE_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            logger.warning("Tentative %d/%d échouée : %s", tentative, DPE_MAX_TENTATIVES, e)
            if tentative == DPE_MAX_TENTATIVES:
                raise
            time.sleep(5 * tentative)


def _params_base():
    return {
        "qs": f"code_departement_ban:{DPE_DEPARTEMENT}",
        "size": DPE_TAILLE_PAGE,
        "select": ",".join(DPE_CHAMPS_API),
    }


def _ecrire_page(lignes, numero_page):
    pd.DataFrame(lignes).reindex(columns=DPE_CHAMPS_API).to_csv(
        DPE_CACHE_DIR / f"page_{numero_page:05d}.csv", index=False
    )


def _vider_cache():
    for fichier in DPE_CACHE_DIR.iterdir():
        fichier.unlink()


def _collecter_echantillon(nb_pages):
    """Premières nb_pages pages d'un parcours trié aléatoirement (tri _rand stable : pas de doublons entre pages)."""
    _vider_cache()
    url, params = f"{DPE_API}/lines", {**_params_base(), "sort": "_rand"}
    for numero_page in range(1, nb_pages + 1):
        data = _get(url, params)
        _ecrire_page(data["results"], numero_page)
        logger.info("Page aléatoire %d/%d : %d lignes (total API : %s)",
                    numero_page, nb_pages, len(data["results"]), data.get("total"))
        url, params = data.get("next"), None
        if not url:
            break


def collecter_dpe(echantillon=None, reprendre=False):
    """Télécharge les DPE de Paris dans DPE_CACHE_DIR (un CSV par page).
    echantillon = N : N pages tirées au hasard ; sinon parcours complet par pagination."""
    DPE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if echantillon:
        _collecter_echantillon(echantillon)
        return

    pages_existantes = sorted(DPE_CACHE_DIR.glob("page_*.csv"))
    if reprendre and TERMINE.exists():
        logger.info("Collecte déjà terminée (%d pages en cache), téléchargement ignoré", len(pages_existantes))
        return

    if reprendre and CURSEUR.exists():
        url, params = CURSEUR.read_text().strip(), None
        numero_page = len(pages_existantes)
        logger.info("Reprise après la page %d", numero_page)
    else:
        _vider_cache()
        url, params = f"{DPE_API}/lines", _params_base()
        numero_page = 0

    while url:
        data = _get(url, params)
        lignes = data["results"]
        if not lignes:
            break
        numero_page += 1
        _ecrire_page(lignes, numero_page)
        url, params = data.get("next"), None
        if url:
            CURSEUR.write_text(url)
        logger.info("Page %d : %d lignes (total API : %s)", numero_page, len(lignes), data.get("total"))

    CURSEUR.unlink(missing_ok=True)
    TERMINE.write_text("ok")
    logger.info("Collecte terminée : %d pages en cache", numero_page)

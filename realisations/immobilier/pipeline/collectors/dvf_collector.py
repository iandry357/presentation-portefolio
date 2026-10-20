import logging
import time

import requests

from pipeline.config import DVF_ANNEES, DVF_CACHE_DIR, DVF_MAX_TENTATIVES, DVF_TIMEOUT, DVF_URL

logger = logging.getLogger(__name__)


def _telecharger(url):
    for tentative in range(1, DVF_MAX_TENTATIVES + 1):
        try:
            r = requests.get(url, timeout=DVF_TIMEOUT)
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            logger.warning("Tentative %d/%d échouée : %s", tentative, DVF_MAX_TENTATIVES, e)
            if tentative == DVF_MAX_TENTATIVES:
                raise
            time.sleep(5 * tentative)


def collecter_dvf():
    """Télécharge les fichiers DVF de Paris (un .csv.gz par année) dans DVF_CACHE_DIR. Remplacement complet."""
    DVF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for fichier in DVF_CACHE_DIR.iterdir():
        fichier.unlink()
    for annee in DVF_ANNEES:
        contenu = _telecharger(DVF_URL.format(annee=annee))
        (DVF_CACHE_DIR / f"{annee}.csv.gz").write_bytes(contenu)
        logger.info("DVF %d : %.1f Mo", annee, len(contenu) / 1e6)

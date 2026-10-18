import logging
import time

import requests

logger = logging.getLogger(__name__)

URL_RECHERCHE = "https://recherche-entreprises.api.gouv.fr/search"
PER_PAGE = 5
TIMEOUT_SECONDS = 10
PAUSE_ENTRE_APPELS_SECONDS = 0.25  # 4 requêtes par seconde (limite de l'API : 7 par IP)
NB_TENTATIVES = 3
ATTENTE_DEFAUT_SECONDS = 2


class ErreurAPIEntreprises(Exception):
    """Appel à l'API Recherche d'entreprises impossible après les nouvelles tentatives."""


def _attente(resp: requests.Response | None) -> float:
    """Délai avant nouvelle tentative : Retry-After si fourni et numérique, sinon valeur par défaut."""
    if resp is not None:
        try:
            return float(resp.headers.get("Retry-After", ATTENTE_DEFAUT_SECONDS))
        except ValueError:
            pass
    return ATTENTE_DEFAUT_SECONDS


def rechercher(nom: str) -> list[dict]:
    """Candidats (champs bruts de l'API) pour un nom d'entreprise."""
    for tentative in range(1, NB_TENTATIVES + 1):
        resp = None
        try:
            resp = requests.get(
                URL_RECHERCHE, params={"q": nom, "per_page": PER_PAGE}, timeout=TIMEOUT_SECONDS
            )
        except requests.RequestException as e:
            logger.warning("API entreprises : erreur réseau (tentative %d/%d) : %s", tentative, NB_TENTATIVES, e)
        else:
            if resp.status_code == 200:
                time.sleep(PAUSE_ENTRE_APPELS_SECONDS)
                return resp.json().get("results", [])
            if resp.status_code != 429 and resp.status_code < 500:
                raise ErreurAPIEntreprises(f"HTTP {resp.status_code} pour '{nom}'")
            logger.warning(
                "API entreprises : HTTP %d (tentative %d/%d)", resp.status_code, tentative, NB_TENTATIVES
            )
        time.sleep(_attente(resp))
    raise ErreurAPIEntreprises(f"Échec après {NB_TENTATIVES} tentatives pour '{nom}'")

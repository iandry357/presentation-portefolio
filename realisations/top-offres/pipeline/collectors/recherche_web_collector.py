import logging
import time

from ddgs import DDGS

from pipeline import config

logger = logging.getLogger(__name__)

NB_EXTRAITS = 5
REGION = "fr-fr"
TIMEOUT_SECONDS = 10
NB_TENTATIVES = 2
ATTENTE_ENTRE_TENTATIVES_SECONDS = 10
REQUETES = {
    1: '"{nom}" secteur d\'activité',
    2: "{nom} entreprise activité",
    3: "{nom} société présentation métier",
}


class ErreurRechercheWeb(Exception):
    """Recherche DuckDuckGo impossible (blocage, limite de débit, réseau) après les nouvelles tentatives."""


def construire_requete(nom: str, essai: int) -> str:
    """Essai 1 : nom exact entre guillemets ; essais 2 et 3 : élargissements sans guillemets."""
    return REQUETES[essai].format(nom=nom.replace('"', " ").strip())


def rechercher(nom: str, essai: int) -> list[dict]:
    """Extraits {titre, url, extrait} pour un nom d'entreprise ; liste vide si DuckDuckGo n'a aucun résultat."""
    requete = construire_requete(nom, essai)
    for tentative in range(1, NB_TENTATIVES + 1):
        try:
            resultats = DDGS(timeout=TIMEOUT_SECONDS).text(requete, region=REGION, max_results=NB_EXTRAITS)
        except Exception as e:
            if "no results" in str(e).lower():
                time.sleep(config.PAUSE_RECHERCHE_WEB_SECONDS)
                return []
            logger.warning("Recherche web : erreur (tentative %d/%d) : %s", tentative, NB_TENTATIVES, e)
            if tentative < NB_TENTATIVES:
                time.sleep(ATTENTE_ENTRE_TENTATIVES_SECONDS)
        else:
            time.sleep(config.PAUSE_RECHERCHE_WEB_SECONDS)
            return [
                {"titre": r.get("title", ""), "url": r.get("href", ""), "extrait": r.get("body", "")}
                for r in resultats
            ]
    raise ErreurRechercheWeb(f"Échec après {NB_TENTATIVES} tentatives pour '{requete}'")

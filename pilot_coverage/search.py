"""Recherche web : chaîne Brave -> DuckDuckGo -> Serper derrière search(requete).
Cache disque par requête, compteurs et plafonds persistants (cache/counters.json)."""
import random
import sys
import threading
import time

import requests

import common


class PlafondAtteint(Exception):
    pass


class ErreurFournisseur(Exception):
    def __init__(self, message, limite=False):
        super().__init__(message)
        self.limite = limite  # True = limitation de débit (429)


_STATS_VIDES = {"requetes": 0, "exploitables": 0, "bascules": 0, "erreurs_429": 0, "erreurs": 0}
_avertis = set()
_desactives = set()
_verrou_compteurs = threading.Lock()  # compteurs.json : lecture-modification-écriture
_verrou_cadence = threading.Lock()
_prochain_creneau = {}


def _cadence(nom, pause):
    """Espace les départs de requêtes d'un fournisseur de `pause` secondes, tous threads confondus."""
    with _verrou_cadence:
        creneau = max(time.time(), _prochain_creneau.get(nom, 0))
        _prochain_creneau[nom] = creneau + pause
    attente = creneau - time.time()
    if attente > 0:
        time.sleep(attente)


def _maj_stats(nom, **increments):
    with _verrou_compteurs:
        compteurs = _charger()
        stats = compteurs["fournisseurs"][nom]
        for cle, n in increments.items():
            stats[cle] += n
        common.ecrire_json(common.FICHIER_COMPTEURS, compteurs)


def _charger():
    compteurs = common.lire_json(common.FICHIER_COMPTEURS, {}) or {}
    compteurs.setdefault("total", 0)
    fournisseurs = compteurs.setdefault("fournisseurs", {})
    for nom in common.ORDRE_FOURNISSEURS:
        stats = fournisseurs.setdefault(nom, {})
        for cle, defaut in _STATS_VIDES.items():
            stats.setdefault(cle, defaut)
    return compteurs


def etat_compteurs():
    return _charger()


def _normaliser(items, cle_titre, cle_url, cle_extrait):
    return [
        {"titre": i.get(cle_titre) or "", "url": i.get(cle_url) or "", "extrait": (i.get(cle_extrait) or "")[:300]}
        for i in items or []
    ]


def _brave(requete, cle):
    _cadence("brave", 1.1)  # offre gratuite : 1 requête/s
    try:
        r = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": requete, "count": 10, "country": "fr", "search_lang": "fr"},
            headers={"Accept": "application/json", "X-Subscription-Token": cle, "User-Agent": common.USER_AGENT},
            timeout=common.TIMEOUT_S,
        )
    except requests.RequestException as e:
        raise ErreurFournisseur(str(e))
    if r.status_code == 429:
        raise ErreurFournisseur("HTTP 429", limite=True)
    if r.status_code != 200:
        raise ErreurFournisseur(f"HTTP {r.status_code}")
    return _normaliser(r.json().get("web", {}).get("results", []), "title", "url", "description")


def _duckduckgo(requete):
    _cadence("duckduckgo", random.uniform(*common.PAUSE_DDG_S))
    try:
        from ddgs import DDGS
        items = DDGS().text(requete, region="fr-fr", max_results=10)
    except Exception as e:
        if "no results" in str(e).lower():
            return []
        limite = "ratelimit" in type(e).__name__.lower() or "429" in str(e) or "202" in str(e)
        raise ErreurFournisseur(f"{type(e).__name__}: {e}", limite=limite)
    return _normaliser(items, "title", "href", "body")


def _serper(requete, cle):
    try:
        r = requests.post(
            "https://google.serper.dev/search",
            json={"q": requete, "gl": "fr", "hl": "fr", "num": 10},
            headers={"X-API-KEY": cle, "Content-Type": "application/json", "User-Agent": common.USER_AGENT},
            timeout=common.TIMEOUT_S,
        )
    except requests.RequestException as e:
        raise ErreurFournisseur(str(e))
    if r.status_code == 429:
        raise ErreurFournisseur("HTTP 429", limite=True)
    if r.status_code != 200:
        raise ErreurFournisseur(f"HTTP {r.status_code}")
    return _normaliser(r.json().get("organic", []), "title", "link", "snippet")


# nom -> (fonction, variable d'environnement de la clé ou None)
FOURNISSEURS = {
    "brave": (_brave, "BRAVE_API_KEY"),
    "duckduckgo": (_duckduckgo, None),
    "serper": (_serper, "SERPER_API_KEY"),
}


def search(requete):
    """Retourne {"resultats": [{titre, url, extrait}], "fournisseur": nom ou None, "cache": bool}.
    Lève PlafondAtteint si les 70 requêtes sont consommées."""
    common.creer_dossiers()
    chemin = common.DOSSIER_CACHE_SEARCH / f"{common.cle_cache(requete + common.CACHE_SUFFIXE)}.json"
    en_cache = common.lire_json(chemin)
    if en_cache is not None:
        return {"resultats": en_cache["resultats"], "fournisseur": en_cache["fournisseur"], "cache": True}

    ordre = common.ORDRE_FOURNISSEURS
    for i, nom in enumerate(ordre):
        fonction, var_cle = FOURNISSEURS[nom]
        cle = None
        if var_cle:
            cle = common.cle_api(var_cle)
            if not cle:
                if nom not in _avertis:
                    _avertis.add(nom)
                    print(f"[search] {var_cle} absente : {nom} sauté")
                continue
        if nom in _desactives:
            continue

        with _verrou_compteurs:
            compteurs = _charger()
            if compteurs["total"] >= common.MAX_REQUETES_TOTAL:
                raise PlafondAtteint(f"{common.MAX_REQUETES_TOTAL} requêtes consommées")
            stats = compteurs["fournisseurs"][nom]
            if nom == "serper" and stats["requetes"] >= common.MAX_REQUETES_SERPER:
                continue

            # Comptage avant l'appel : un plantage ne sous-estime jamais la consommation
            compteurs["total"] += 1
            stats["requetes"] += 1
            common.ecrire_json(common.FICHIER_COMPTEURS, compteurs)

        try:
            resultats = fonction(requete, cle) if cle else fonction(requete)
            resultats = [r for r in resultats if r["url"].startswith("http")]
        except ErreurFournisseur as e:
            _maj_stats(nom, **{"erreurs_429" if e.limite else "erreurs": 1})
            if nom == "duckduckgo" and e.limite:
                _desactives.add(nom)  # pas d'insistance après une limitation
            print(f"[search] {nom} échec : {e}")
            resultats = []

        if resultats:
            _maj_stats(nom, exploitables=1)
            common.ecrire_json(chemin, {"requete": requete, "fournisseur": nom, "resultats": resultats})
            return {"resultats": resultats, "fournisseur": nom, "cache": False}

        if i < len(ordre) - 1:
            _maj_stats(nom, bascules=1)

    # Réponse vide : jamais mise en cache (DuckDuckGo peut répondre vide sans erreur quand il limite le débit)
    return {"resultats": [], "fournisseur": None, "cache": False}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit('Usage : python search.py "requête"')
    sortie = search(" ".join(sys.argv[1:]))
    print(f"fournisseur={sortie['fournisseur']} cache={sortie['cache']} résultats={len(sortie['resultats'])}")
    for r in sortie["resultats"][:5]:
        print(f"  - {r['titre']} | {r['url']}")
    c = etat_compteurs()
    print(f"total={c['total']}/{common.MAX_REQUETES_TOTAL}")
    for nom, s in c["fournisseurs"].items():
        print(f"  {nom} : {s}")

"""Récupération polie des pages employeur (robots.txt, pause par domaine, aucun contournement)
et extraction de la description : JobPosting JSON-LD, sinon bloc de texte principal."""
import functools
import gzip
import html as html_lib
import json
import random
import re
import sys
import threading
import time
from datetime import date
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

import common

TAILLE_MAX = 2 * 1024 * 1024
DELAI_MAX_S = 30  # plafond appliqué au Crawl-delay des robots.txt
TAILLE_DESCRIPTION_STOCKEE = 5000
MARQUEURS_BLOCAGE = ["captcha", "just a moment", "attention required", "access denied", "cf-challenge",
                     "verify you are human", "are you a robot"]
BALISES_BRUIT = ["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "iframe"]
MOTS_BLOC_OFFRE = ["job", "offre", "description", "poste", "mission", "vacancy", "career"]
TAILLE_MAX_BLOC = 30000

_robots = {}
_dernier_acces = {}
_delais = {}
_verrous = {}
_verrou_verrous = threading.Lock()


def _verrou(netloc):
    with _verrou_verrous:
        return _verrous.setdefault(netloc, threading.RLock())


def _par_hote(fonction):
    """Un seul thread à la fois par hôte (robots, pause, requête, cache) : la politesse tient en multi-thread.
    Des hôtes différents avancent en parallèle."""
    @functools.wraps(fonction)
    def enveloppe(url, *args, **kwargs):
        with _verrou(urlparse(url).netloc):
            return fonction(url, *args, **kwargs)
    return enveloppe


def _entetes():
    return {
        "User-Agent": common.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
    }


def _attendre(netloc):
    pause = max(random.uniform(*common.PAUSE_DOMAINE_S), _delais.get(netloc) or 0)
    ecart = time.time() - _dernier_acces.get(netloc, 0)
    if ecart < pause:
        time.sleep(pause - ecart)


def _robots_autorise(url):
    parsed = urlparse(url)
    if parsed.netloc not in _robots:
        rp = RobotFileParser()
        _attendre(parsed.netloc)
        try:
            r = requests.get(f"{parsed.scheme}://{parsed.netloc}/robots.txt", headers=_entetes(), timeout=common.TIMEOUT_S)
            if r.status_code >= 500:
                rp.disallow_all = True
            elif r.status_code >= 400:
                rp.allow_all = True
            else:
                rp.parse(r.text.splitlines())
        except requests.RequestException:
            rp.allow_all = True
        _dernier_acces[parsed.netloc] = time.time()
        _robots[parsed.netloc] = rp
        _delais[parsed.netloc] = min(rp.crawl_delay(common.USER_AGENT) or 0, DELAI_MAX_S)
    return _robots[parsed.netloc].can_fetch(common.USER_AGENT, url)


def _alleger(texte):
    """Retire scripts (sauf JSON-LD) et styles avant troncature : le JS inline peut dépasser TAILLE_MAX."""
    texte = re.sub(r"<script(?![^>]*ld\+json)[^>]*>.*?</script>", "", texte, flags=re.S | re.I)
    return re.sub(r"<style[^>]*>.*?</style>", "", texte, flags=re.S | re.I)


def _decoder(r):
    """Sans charset dans l'en-tête, requests suppose ISO-8859-1 (« Ã© ») : on tente l'UTF-8, sinon cp1252."""
    if "charset" in r.headers.get("Content-Type", "").lower():
        return r.text
    try:
        return r.content.decode("utf-8")
    except UnicodeDecodeError:
        return r.content.decode("cp1252", errors="replace")


def _reparer(texte):
    """Pages déjà en cache décodées à tort en ISO-8859-1 : rétablit l'UTF-8 sans retélécharger."""
    if "Ã" not in texte:
        return texte
    try:
        return texte.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texte


@_par_hote
def telecharger(url):
    """Retourne {url, url_finale, statut, http, html}. statut : ok / bloque / robots / non_html / erreur_http / erreur.
    Tout statut sauf 'erreur' (réseau) est mis en cache."""
    chemin = common.DOSSIER_CACHE_PAGES / f"{common.cle_cache(url)}.json"
    en_cache = common.lire_json(chemin)
    if en_cache is not None:
        return en_cache

    if not _robots_autorise(url):
        res = {"url": url, "url_finale": url, "statut": "robots", "http": None, "html": ""}
        common.ecrire_json(chemin, res)
        return res

    netloc = urlparse(url).netloc
    _attendre(netloc)
    try:
        r = requests.get(url, headers=_entetes(), timeout=common.TIMEOUT_S, allow_redirects=True)
    except requests.RequestException as e:
        return {"url": url, "url_finale": url, "statut": "erreur", "http": None, "html": "", "detail": str(e)}
    finally:
        _dernier_acces[netloc] = time.time()

    texte = _alleger(_decoder(r)[:TAILLE_MAX])
    bas = texte[:20000].lower()
    marqueur = any(m in bas for m in MARQUEURS_BLOCAGE) and len(texte) < 30000
    if r.status_code in (401, 403, 429) or (r.status_code == 503 and marqueur) or (r.status_code == 200 and marqueur):
        statut = "bloque"
    elif r.status_code >= 400:
        statut = "erreur_http"
    elif "html" not in r.headers.get("Content-Type", "").lower():
        statut = "non_html"
    else:
        statut = "ok"

    res = {"url": url, "url_finale": r.url, "statut": statut, "http": r.status_code,
           "html": texte if statut == "ok" else ""}
    common.ecrire_json(chemin, res)
    return res


@_par_hote
def sitemaps_declares(url):
    """Sitemaps annoncés par le robots.txt du site de `url` (liste vide si aucun)."""
    _robots_autorise(url)
    return _robots[urlparse(url).netloc].site_maps() or []


def _chemin_texte(url):
    return common.DOSSIER_CACHE_PAGES / f"{common.cle_cache('texte|' + url)}.json"


def date_cache_texte(url):
    """Jour où la ressource texte (sitemap) a été mise en cache, ou None."""
    chemin = _chemin_texte(url)
    return date.fromtimestamp(chemin.stat().st_mtime) if chemin.exists() else None


@_par_hote
def telecharger_texte(url, taille_max=10 * 1024 * 1024, rafraichir=False):
    """Ressource texte non HTML (sitemap, éventuellement .gz). Retourne {url, statut, http, texte}.
    Statuts : ok / robots / erreur_http / erreur. Mêmes règles de politesse que telecharger().
    rafraichir=True ignore le cache (sitemap antérieur à l'offre cherchée) et le réécrit."""
    chemin = _chemin_texte(url)
    en_cache = None if rafraichir else common.lire_json(chemin)
    if en_cache is not None:
        return en_cache

    if not _robots_autorise(url):
        res = {"url": url, "statut": "robots", "http": None, "texte": ""}
        common.ecrire_json(chemin, res)
        return res

    netloc = urlparse(url).netloc
    _attendre(netloc)
    try:
        r = requests.get(url, headers=_entetes(), timeout=common.TIMEOUT_S * 3)
    except requests.RequestException as e:
        return {"url": url, "statut": "erreur", "http": None, "texte": "", "detail": str(e)}
    finally:
        _dernier_acces[netloc] = time.time()

    if r.status_code >= 400:
        res = {"url": url, "statut": "erreur_http", "http": r.status_code, "texte": ""}
    else:
        contenu = r.content
        if contenu[:2] == b"\x1f\x8b":
            try:
                contenu = gzip.decompress(contenu)
            except OSError:
                contenu = b""
        res = {"url": url, "statut": "ok", "http": r.status_code,
               "texte": contenu[:taille_max].decode("utf-8", errors="replace")}
    common.ecrire_json(chemin, res)
    return res


def _espaces(texte):
    return re.sub(r"\s+", " ", texte).strip()


def _html_vers_texte(contenu):
    return _espaces(BeautifulSoup(html_lib.unescape(contenu), "html.parser").get_text(" ", strip=True))


def _noeuds_jsonld(donnees):
    if isinstance(donnees, list):
        for d in donnees:
            yield from _noeuds_jsonld(d)
    elif isinstance(donnees, dict):
        yield donnees
        for v in donnees.values():
            if isinstance(v, (list, dict)):
                yield from _noeuds_jsonld(v)


def _lieu_jsonld(valeur):
    """Texte à plat des adresses d'un jobLocation JSON-LD (dict, liste ou texte)."""
    morceaux = []
    for v in (valeur if isinstance(valeur, list) else [valeur]):
        if isinstance(v, dict):
            adresse = v.get("address", v)
            if isinstance(adresse, dict):
                morceaux += [str(adresse.get(k) or "") for k in ("addressLocality", "postalCode", "addressRegion")]
            elif adresse:
                morceaux.append(str(adresse))
        elif v:
            morceaux.append(str(v))
    return " ".join(m for m in morceaux if m)


def extraire_jobposting(soup):
    """Premier JobPosting JSON-LD : {titre, description (texte), date, lieu}, ou None."""
    for balise in soup.find_all("script", type="application/ld+json"):
        try:
            donnees = json.loads(balise.string or balise.get_text(), strict=False)
        except json.JSONDecodeError:
            continue
        for noeud in _noeuds_jsonld(donnees):
            t = noeud.get("@type")
            if "JobPosting" in (t if isinstance(t, list) else [t]):
                return {
                    "titre": str(noeud.get("title") or noeud.get("name") or ""),
                    "description": _html_vers_texte(str(noeud.get("description") or "")),
                    "date": str(noeud.get("datePosted") or "")[:10],
                    "lieu": _lieu_jsonld(noeud.get("jobLocation")),
                }
    return None


def extraire_texte_principal(soup):
    """Texte du bloc principal de la page (le plus long parmi main/article/blocs 'offre'), sinon du body.
    Modifie le soup (suppression du bruit) : à appeler en dernier."""
    for nom in BALISES_BRUIT:
        for b in soup.find_all(nom):
            b.decompose()
    candidats = soup.find_all(["main", "article"]) + soup.find_all(attrs={"role": "main"})
    for bloc in soup.find_all(["div", "section"]):
        marque = (" ".join(bloc.get("class") or []) + " " + (bloc.get("id") or "")).lower()
        if any(m in marque for m in MOTS_BLOC_OFFRE):
            candidats.append(bloc)
    textes = [t for t in (_espaces(c.get_text(" ", strip=True)) for c in candidats) if len(t) <= TAILLE_MAX_BLOC]
    if textes:
        return max(textes, key=len)
    return _espaces((soup.body or soup).get_text(" ", strip=True))


def score_titre(titre_offre, titre_page):
    """Similarité 0-1 : ratio de séquence, ou 1.0 si l'un des titres normalisés contient l'autre."""
    a, b = common.normaliser(titre_offre), common.normaliser(titre_page)
    if not a or not b:
        return 0.0
    if len(min(a, b, key=len)) >= 8 and (a in b or b in a):
        return 1.0
    return common.similarite_titres(titre_offre, titre_page)


def analyser_page(url, titre_offre):
    page = telecharger(url)
    res = {
        "url": url, "url_finale": page.get("url_finale", url), "statut_page": page["statut"], "http": page.get("http"),
        "jobposting_jsonld": False, "source_description": "", "titre_page": "", "description": "",
        "longueur_description": 0, "score_titre": 0.0, "titre_coherent": False, "date_page": "", "lieu_page": "",
    }
    if page["statut"] != "ok":
        return res

    soup = BeautifulSoup(_reparer(page["html"]), "html.parser")
    jp = extraire_jobposting(soup)
    h1 = soup.find("h1")
    titre_h1 = _espaces(h1.get_text(" ", strip=True)) if h1 else ""
    titre_html = _espaces(soup.title.get_text(" ", strip=True)) if soup.title else ""

    if jp:
        res["jobposting_jsonld"] = True
        res["date_page"], res["lieu_page"] = jp["date"], jp["lieu"]
    if jp and jp["description"]:
        description, res["source_description"] = jp["description"], "jsonld"
        titre_page = jp["titre"] or titre_h1 or titre_html
    else:
        description, res["source_description"] = extraire_texte_principal(soup), "html"
        titre_page = (jp["titre"] if jp else "") or titre_h1 or titre_html

    res["titre_page"] = titre_page
    res["longueur_description"] = len(description)
    res["description"] = description[:TAILLE_DESCRIPTION_STOCKEE]
    res["score_titre"] = round(max(score_titre(titre_offre, titre_page), score_titre(titre_offre, titre_html)), 3)
    res["titre_coherent"] = res["score_titre"] >= common.SEUIL_TITRE
    return res


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit('Usage : python fetch.py <url> "<titre de l\'offre>"')
    common.creer_dossiers()
    a = analyser_page(sys.argv[1], sys.argv[2])
    for cle, valeur in a.items():
        if cle != "description":
            print(f"{cle} : {valeur}")
    print(f"description (début) : {a['description'][:300]}")

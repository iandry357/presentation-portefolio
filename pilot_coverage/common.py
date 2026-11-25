"""Configuration et utilitaires communs du pilote de couverture (jetable, lecture seule)."""
import hashlib
import json
import os
import re
import threading
import time
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse



def _charger_env(chemin):
    """Charge pilot_coverage/.env dans os.environ, sans écraser une variable déjà définie."""
    try:
        lignes = Path(chemin).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        nom, valeur = ligne.split("=", 1)
        os.environ.setdefault(nom.strip(), valeur.strip().strip('"').strip("'"))


_charger_env(Path(__file__).resolve().parent / ".env")

# --- Paramètres configurables ---
NB_OFFRES = 2000
JOURS_MAX = 1  # défaut de --jours (00_inspect_schema.py, exporter.py) : offres publiées depuis N jours, 0 = pas de filtre
UNE_PAR_ENTREPRISE = False  # True : une seule offre par entreprise (ancien échantillonnage)
MAX_REQUETES_TOTAL = 1500
MAX_REQUETES_SERPER = 20
ORDRE_FOURNISSEURS = ["brave", "duckduckgo", "serper"]
PAUSE_DDG_S = (2.0, 3.0)
PAUSE_DOMAINE_S = (1.0, 2.0)
TIMEOUT_S = 10
USER_AGENT = "Mozilla/5.0 (compatible; PilotCoverage/0.1; pilote personnel)"
MIN_DESCRIPTION = 400
SEUIL_TITRE = 0.6

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
TABLE_PRINCIPALE = "top_offres.mart_top_du_jour"
TABLE_REPLI = "emploi_marche.stg_offres"
TABLE_ENTREPRISES = "top_offres.entreprises_ref"
MAX_OCTETS_REQUETE = 1024 ** 3  # 1 Go

# --- Chemins ---
RACINE = Path(__file__).resolve().parent
DOSSIER_INPUT = RACINE / "input"
DOSSIER_OUTPUT = RACINE / "output"
DOSSIER_CACHE_SEARCH = RACINE / "cache" / "search"
DOSSIER_CACHE_PAGES = RACINE / "cache" / "pages"
DOSSIER_CACHE_OFFRES = RACINE / "cache" / "offers"
FICHIER_ECHANTILLON = DOSSIER_INPUT / "offers_sample.csv"
FICHIER_COMPTEURS = RACINE / "cache" / "counters.json"
FICHIER_RESULTATS = DOSSIER_OUTPUT / "results.csv"
FICHIER_RESUME = DOSSIER_OUTPUT / "summary.md"
FICHIER_JOURNAL = DOSSIER_OUTPUT / "executions.log"

# --- Listes de domaines (correspondance par sous-chaîne sur le nom d'hôte) ---
BLOCKLIST_AGREGATEURS = [
    "linkedin", "indeed", "glassdoor", "hellowork", "apec", "francetravail", "pole-emploi",
    "free-work", "jobijoba", "jobleads", "welcometothejungle", "monster", "talent.com", "jooble",
    "adzuna", "cadremploi", "meteojob", "regionsjob",
    # réseaux sociaux
    "facebook", "instagram", "twitter", "x.com", "youtube", "tiktok", "pinterest", "reddit",
    "wikipedia", "viadeo",
]
ATS_CONNUS = {
    "greenhouse": "greenhouse.io",
    "lever": "lever.co",
    "ashby": "ashbyhq.com",
    "smartrecruiters": "smartrecruiters.com",
    "recruitee": "recruitee.com",
    "personio": "personio.",
    "workable": "workable.com",
    "teamtailor": "teamtailor.com",
}
_SLD_COMPOSES = {"co", "com", "org", "net", "gouv", "gov", "ac"}


def cle_api(nom):
    """Valeur d'une variable d'environnement, ou None si absente ou vide."""
    valeur = os.environ.get(nom, "").strip()
    return valeur or None


def creer_dossiers():
    for d in (DOSSIER_INPUT, DOSSIER_OUTPUT, DOSSIER_CACHE_SEARCH, DOSSIER_CACHE_PAGES, DOSSIER_CACHE_OFFRES):
        d.mkdir(parents=True, exist_ok=True)


def chrono(debut):
    """Temps écoulé depuis `debut` (time.perf_counter()), au format [mm:ss]."""
    s = int(time.perf_counter() - debut)
    return f"[{s // 60:02d}:{s % 60:02d}]"


def journaliser(script, debut, **infos):
    """Ajoute une ligne au journal des exécutions (output/executions.log) : date, script, durée, paramètres, résumé."""
    details = " ".join(f"{k}={v}" for k, v in infos.items())
    ligne = f"{datetime.now():%Y-%m-%d %H:%M:%S} | {script} | {time.perf_counter() - debut:.0f} s | {details}"
    DOSSIER_OUTPUT.mkdir(parents=True, exist_ok=True)
    with open(FICHIER_JOURNAL, "a", encoding="utf-8") as f:
        f.write(ligne + "\n")
    print(f"\nJournal -> {FICHIER_JOURNAL}\n  {ligne}")


def cle_cache(texte):
    return hashlib.sha1(texte.encode("utf-8")).hexdigest()[:16]


def lire_json(chemin, defaut=None):
    try:
        return json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return defaut


def ecrire_json(chemin, donnees):
    """Écriture atomique : une interruption ne laisse jamais un fichier tronqué."""
    chemin = Path(chemin)
    tmp = chemin.with_suffix(chemin.suffix + f".{threading.get_ident()}.tmp")  # un fichier temporaire par thread
    tmp.write_text(json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, chemin)


def normaliser(texte):
    texte = unicodedata.normalize("NFKD", texte or "")
    texte = "".join(c for c in texte if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", texte).strip()


def similarite_titres(a, b):
    return SequenceMatcher(None, normaliser(a), normaliser(b)).ratio()


def hote(url):
    h = (urlparse(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def domaine_racine(url_ou_hote):
    """Domaine enregistrable approximatif (sans liste des suffixes publics)."""
    h = hote(url_ou_hote) if "/" in url_ou_hote else url_ou_hote.lower()
    labels = h.split(".")
    if len(labels) >= 3 and labels[-2] in _SLD_COMPOSES and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def est_agregateur(url_ou_hote):
    h = hote(url_ou_hote) if "/" in url_ou_hote else url_ou_hote.lower()
    return any(jeton in h for jeton in BLOCKLIST_AGREGATEURS)


def ats_detecte(url_ou_hote):
    """Nom de l'ATS connu correspondant à l'hôte, ou chaîne vide."""
    h = hote(url_ou_hote) if "/" in url_ou_hote else url_ou_hote.lower()
    for nom, motif in ATS_CONNUS.items():
        if motif in h:
            return nom
    return ""


def appartient_au_domaine(url, domaine):
    h = hote(url)
    return h == domaine or h.endswith("." + domaine)


CACHE_SUFFIXE = ""


def choisir_fournisseurs(liste):
    """Restreint ou réordonne les fournisseurs (ex. 'duckduckgo,brave'). Le cache est alors séparé de la configuration par défaut."""
    global ORDRE_FOURNISSEURS, CACHE_SUFFIXE
    noms = [n.strip() for n in liste.split(",") if n.strip()]
    inconnus = [n for n in noms if n not in ("brave", "duckduckgo", "serper")]
    if inconnus or not noms:
        raise SystemExit(f"Fournisseur inconnu ou liste vide : {inconnus or liste}")
    ORDRE_FOURNISSEURS = noms
    CACHE_SUFFIXE = "|" + ",".join(noms)

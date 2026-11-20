"""Domaine employeur sans moteur de recherche payant : Wikidata, puis domaine deviné et validé par le titre de la page.
Cible les entreprises dont l'étape A est vide dans le cache. Écrit output/domaines_alternatifs.csv ;
--injecter complète ensuite le cache pour que sitemap_check.py les traite."""
import argparse
import csv
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup

import common
import fetch

# --- Paramètres configurables ---
NB_THREADS = 6
TLDS = ["com", "fr", "ai", "io"]
PREFIXES_CARRIERES = ["careers", "jobs", "recrutement", "carrieres", "emploi", "talent", "join"]
MAX_SLUGS = 3
MIN_SLUG = 3
LONGUEUR_NOM_MAX = 40  # au-delà, le nom est un texte d'agrégateur et non une entreprise
PAUSE_WIKIDATA_S = 0.4
MOTS_FORME = {"sa", "sas", "sarl", "se", "inc", "ltd", "llc", "gmbh", "group", "groupe", "france", "cdi",
              "h", "f", "fh", "hf"}
MOTS_GENERIQUES_NOM = {"consulting", "technologies", "technology", "solutions", "services", "software", "systems",
                       "digital", "factory", "studio", "paris", "engineering", "conseil", "sourcing", "enterprise"}
METHODES_INJECTABLES = {"wikidata", "devine"}
# Homonymes repérés à la relecture du CSV (domaine deviné appartenant à une autre société)
EXCLUSIONS_MANUELLES = {"Ametra Engineering", "JEMS", "Mistral", "Lydia", "Ortec Services",
                        "CERBA HEALTHCARE GESTION", "Modjo", "Foodles"}
API_WIKIDATA = "https://www.wikidata.org/w/api.php"
DOSSIER_CACHE_WIKIDATA = common.RACINE / "cache" / "wikidata"
DOSSIER_CACHE_DOMAINES = common.RACINE / "cache" / "domaines"  # à vider après un changement des règles de devinage
FICHIER_SORTIE = common.DOSSIER_OUTPUT / "domaines_alternatifs.csv"

_verrou_wikidata = threading.Lock()
_prochain_wikidata = [0.0]


def est_alternatif(offre):
    return str(offre.get("domaine_confiance", "")).startswith("alternatif")


def charger_cibles():
    """[(offre, [chemins de cache])] pour les entreprises de l'échantillon dont aucune version n'a d'URLs d'étape A."""
    with open(common.FICHIER_ECHANTILLON, newline="", encoding="utf-8") as f:
        ids = {r["id_unique"] for r in csv.DictReader(f)}
    versions_par_id = {}
    for chemin in sorted(common.DOSSIER_CACHE_OFFRES.glob("*.json")):
        o = common.lire_json(chemin)
        if o and o["id_unique"] in ids:
            versions_par_id.setdefault(o["id_unique"], []).append((chemin, o))
    cibles = []
    for versions in versions_par_id.values():
        if any(o.get("urls_etape_A") and not est_alternatif(o) for _, o in versions):
            continue  # étape A réelle ; les domaines déjà injectés sont rejoués, donc rectifiables
        offre = versions[0][1]
        if offre["type_annonceur"] == "intermediaire":
            continue
        cibles.append((offre, [chemin for chemin, _ in versions]))
    return cibles


def jetons_nom(nom):
    return [t for t in common.normaliser(nom).split() if t not in MOTS_FORME]


def slugs(jetons):
    candidats = []
    if jetons:
        candidats += ["".join(jetons), "-".join(jetons)]
        if len(jetons[0]) >= 4 and all(t in MOTS_GENERIQUES_NOM for t in jetons[1:]):
            candidats.append(jetons[0])  # le premier mot seul n'est fiable que si le reste est générique (sinon « cabinet », « golden »)
    uniques = []
    for s in candidats:
        if len(s) >= MIN_SLUG and s not in uniques:
            uniques.append(s)
    return uniques[:MAX_SLUGS]


def titre_et_site(html):
    soup = BeautifulSoup(html, "html.parser")
    morceaux = [soup.title.get_text(" ", strip=True) if soup.title else ""]
    for meta in soup.find_all("meta", attrs={"property": "og:site_name"}):
        morceaux.append(meta.get("content") or "")
    return " ".join(m for m in morceaux if m)


def valider(hote, jetons):
    """('ok' | 'bloque' | '', url finale, titre) : le titre de l'accueil doit contenir le nom de l'entreprise."""
    res = fetch.telecharger(f"https://{hote}/")
    if res["statut"] == "bloque":
        return "bloque", res["url_finale"], ""
    if res["statut"] != "ok":
        return "", res["url_finale"], ""
    titre = titre_et_site(res["html"])
    plat = common.normaliser(titre).replace(" ", "")
    if "for sale" in titre.lower() or plat == common.normaliser(hote).replace(" ", ""):
        return "", res["url_finale"], titre  # domaine parqué ou page vide : le titre n'est que le nom de domaine
    nom_complet, premier = "".join(jetons), jetons[0]
    if nom_complet in plat or (len(premier) >= 4 and premier in plat):
        return "ok", res["url_finale"], titre
    return "", res["url_finale"], titre


def deviner(jetons):
    bloque = None
    for slug in slugs(jetons):
        for tld in TLDS:
            hote = f"{slug}.{tld}"
            etat, url_finale, titre = valider(hote, jetons)
            if etat == "ok":
                return {"domaine": common.domaine_racine(url_finale), "methode": "devine", "preuve": titre[:120]}
            if etat == "bloque" and bloque is None:
                bloque = {"domaine": common.domaine_racine(hote), "methode": "devine_bloque",
                          "preuve": "accueil refusé (HTTP), titre non vérifié"}
    return bloque


def _appel_wikidata(params):
    with _verrou_wikidata:
        creneau = max(time.time(), _prochain_wikidata[0])
        _prochain_wikidata[0] = creneau + PAUSE_WIKIDATA_S
    attente = creneau - time.time()
    if attente > 0:
        time.sleep(attente)
    r = requests.get(API_WIKIDATA, params={**params, "format": "json"},
                     headers={"User-Agent": common.USER_AGENT}, timeout=common.TIMEOUT_S)
    r.raise_for_status()
    return r.json()


def candidats_wikidata(nom):
    """Entités Wikidata portant un site officiel (P856) pour ce nom, avec cache disque. None en cas d'erreur réseau."""
    chemin = DOSSIER_CACHE_WIKIDATA / f"{common.cle_cache(nom)}.json"
    en_cache = common.lire_json(chemin)
    if en_cache is not None:
        return en_cache["candidats"]
    try:
        trouves = _appel_wikidata({"action": "wbsearchentities", "search": nom, "language": "fr", "uselang": "fr",
                                   "type": "item", "limit": 5}).get("search", [])
        ids = [e["id"] for e in trouves]
        entites = {}
        if ids:
            entites = _appel_wikidata({"action": "wbgetentities", "ids": "|".join(ids), "props": "claims|labels|descriptions",
                                       "languages": "fr|en"}).get("entities", {})
    except (requests.RequestException, ValueError):
        return None  # pas de cache sur erreur : rejouable
    candidats = []
    for i in ids:
        e = entites.get(i, {})
        sites = [c["mainsnak"]["datavalue"]["value"] for c in e.get("claims", {}).get("P856", [])
                 if c.get("mainsnak", {}).get("datavalue")]
        if not sites:
            continue
        label = (e.get("labels", {}).get("fr") or e.get("labels", {}).get("en") or {}).get("value", "")
        desc = (e.get("descriptions", {}).get("fr") or e.get("descriptions", {}).get("en") or {}).get("value", "")
        candidats.append({"id": i, "label": label, "description": desc, "site": sites[0]})
    common.ecrire_json(chemin, {"candidats": candidats})
    return candidats


def wikidata(nom, jetons):
    candidats = candidats_wikidata(nom)
    if not candidats:
        return None
    cibles = {"".join(jetons), common.normaliser(nom).replace(" ", "")}
    for c in candidats:
        if common.normaliser(c["label"]).replace(" ", "") in cibles:
            return {"domaine": common.domaine_racine(c["site"]), "methode": "wikidata",
                    "preuve": f"{c['label']} ({c['description']}) {c['id']}"}
    c = candidats[0]
    return {"domaine": common.domaine_racine(c["site"]), "methode": "wikidata_libelle_different",
            "preuve": f"{c['label']} ({c['description']}) {c['id']}"}


def hotes_carrieres(domaine):
    """Sous-domaines carrières usuels qui répondent (page d'accueil téléchargeable ou refusée, pas d'erreur réseau)."""
    hotes = [f"{p}.{domaine}" for p in PREFIXES_CARRIERES]
    with ThreadPoolExecutor(max_workers=len(hotes)) as pool:  # hôtes distincts : sans effet sur la politesse
        statuts = list(pool.map(lambda h: fetch.telecharger(f"https://{h}/")["statut"], hotes))
    return [h for h, s in zip(hotes, statuts) if s in ("ok", "bloque")]


def resoudre(offre):
    nom = offre["entreprise_nom"]
    ligne = {"entreprise": nom, "titre": offre["titre"], "methode": "", "domaine": "", "preuve": "",
             "hotes_carrieres": [], "injectable": False}
    jetons = jetons_nom(nom)
    if len(nom) > LONGUEUR_NOM_MAX or not jetons:
        ligne["methode"] = "nom_inexploitable"
        return ligne
    if nom in EXCLUSIONS_MANUELLES:
        ligne["methode"] = "exclu_manuel"
        return ligne
    # Résultat par entreprise mis en cache, échecs compris : les domaines inexistants (erreurs DNS) ne sont pas
    # mis en cache par fetch et seraient sinon re-testés à chaque run et pour chaque offre de l'entreprise
    chemin = DOSSIER_CACHE_DOMAINES / f"{common.cle_cache(nom)}.json"
    resultat = common.lire_json(chemin)
    if resultat is None:
        resultat = {"methode": "", "domaine": "", "preuve": "", "hotes_carrieres": [], "injectable": False}
        trouve = wikidata(nom, jetons)
        if not trouve or trouve["methode"] != "wikidata":
            trouve = deviner(jetons) or trouve  # un domaine deviné et validé vaut mieux qu'un libellé Wikidata différent
        if trouve:
            resultat.update(trouve)
            resultat["injectable"] = trouve["methode"] in METHODES_INJECTABLES
            if resultat["injectable"]:
                resultat["hotes_carrieres"] = hotes_carrieres(trouve["domaine"])
        common.ecrire_json(chemin, resultat)
    ligne.update(resultat)
    return ligne


def injecter(ligne, chemins):
    """Écrit les URLs trouvées dans le cache des offres, comme si l'étape A les avait renvoyées."""
    urls = [f"https://{h}/" for h in ligne["hotes_carrieres"]] + [f"https://{ligne['domaine']}/"]
    for chemin in chemins:
        o = common.lire_json(chemin)
        o.update({"urls_etape_A": urls, "domaine_employeur": ligne["domaine"],
                  "domaine_confiance": "alternatif:" + ligne["methode"]})
        if o.get("cause_echec") == "domaine_non_identifie":
            o.update({"statut": "etape_A_seule", "cause_echec": ""})
        common.ecrire_json(chemin, o)


def retirer(chemins):
    """Annule une injection précédente devenue invalide (domaine rejeté ou exclu depuis)."""
    for chemin in chemins:
        o = common.lire_json(chemin)
        if est_alternatif(o):
            o.update({"urls_etape_A": [], "domaine_employeur": "", "domaine_confiance": "",
                      "statut": "introuvable", "cause_echec": "domaine_non_identifie"})
            common.ecrire_json(chemin, o)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=None, help="ne traiter que les N premières entreprises")
    parser.add_argument("--threads", type=int, default=NB_THREADS)
    parser.add_argument("--injecter", action="store_true",
                        help="compléter le cache (domaines wikidata / devine) pour que sitemap_check les traite")
    args = parser.parse_args()

    common.creer_dossiers()
    DOSSIER_CACHE_WIKIDATA.mkdir(parents=True, exist_ok=True)
    DOSSIER_CACHE_DOMAINES.mkdir(parents=True, exist_ok=True)
    if not common.FICHIER_ECHANTILLON.exists():
        sys.exit("input/offers_sample.csv absent : lancer d'abord 00_inspect_schema.py")
    cibles = charger_cibles()
    if args.n:
        cibles = cibles[: args.n]
    print(f"{len(cibles)} entreprises sans domaine (étape A vide)")

    debut = time.perf_counter()
    lignes = []
    with ThreadPoolExecutor(max_workers=max(1, args.threads)) as pool:
        for i, ((offre, chemins), ligne) in enumerate(zip(cibles, pool.map(lambda c: resoudre(c[0]), cibles)), 1):
            lignes.append(ligne)
            print(f"{common.chrono(debut)} [{i}/{len(cibles)}] {ligne['entreprise']} -> {ligne['methode'] or 'rien'} {ligne['domaine']}")
            if ligne["preuve"]:
                print(f"      preuve : {ligne['preuve']}")
            if ligne["hotes_carrieres"]:
                print(f"      carrières : {' '.join(ligne['hotes_carrieres'])}")
            if args.injecter:
                if ligne["injectable"]:
                    injecter(ligne, chemins)
                else:
                    retirer(chemins)

    if lignes:
        with open(FICHIER_SORTIE, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(lignes[0].keys()))
            w.writeheader()
            for l in lignes:
                w.writerow({**l, "hotes_carrieres": " ".join(l["hotes_carrieres"])})
    print(f"\n{len(lignes)} entreprises -> {FICHIER_SORTIE}")
    print("Méthodes :", dict(Counter(l["methode"] or "rien" for l in lignes)))
    injectables = sum(1 for l in lignes if l["injectable"])
    print(f"Domaines injectables (wikidata ou deviné validé) : {injectables}"
          + ("  [injectés dans le cache]" if args.injecter else "  [relancer avec --injecter pour les utiliser]"))
    common.journaliser("domaine_alternatif", debut, entreprises=len(lignes), threads=args.threads, injecter=args.injecter,
                       injectables=injectables, methodes=dict(Counter(l["methode"] or "rien" for l in lignes)))


if __name__ == "__main__":
    main()

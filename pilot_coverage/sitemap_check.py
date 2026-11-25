"""Mesure : pour chaque entreprise déjà identifiée (cache/offers/), le site employeur publie-t-il un sitemap
listant des pages d'offres, et l'offre d'origine y figure-t-elle ? Aucune requête de recherche : on réutilise urls_etape_A."""
import argparse
import csv
import functools
import html as html_lib
import os
import re
import threading
import time
from collections import Counter
from datetime import date
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from urllib.parse import urlparse

import common
import fetch
from run_pilot import est_page_offre, statut_de_analyse

# --- Paramètres configurables ---
NB_THREADS = 8  # entreprises en parallèle ; la politesse reste appliquée par hôte (voir fetch._par_hote)
MAX_HOTES = 3
BUDGET_HOTE_S = 180  # au-delà, l'analyse d'un hôte s'arrête (cause hote_trop_lent si aucune URL trouvée)
PERIODE_SUIVI_S = 60  # affichage des offres en cours de traitement
HOTES_EXCLUS = {"goldengoose.com"}  # homonymes repérés (suffixe d'hôte) : Golden Bees != Golden Goose
MOTS_GENERIQUES = {"groupe", "group", "services", "service", "technology", "technologies", "software",
                   "solutions", "consulting", "conseil", "france", "sourcing", "company"}
MAX_SITEMAPS = 12
MAX_SOUS_SITEMAPS = 5
SEUIL_COUVERTURE = 0.8
CHEMINS_USUELS = ["/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml", "/wp-sitemap.xml",
                  "/fr/sitemap.xml", "/en/sitemap.xml"]
MOTS_IGNORES = {"h", "f", "hf", "fh", "m", "mf", "fm", "w", "d", "x", "cdi", "cdd", "confirme", "experimente"}
RE_FRANCE = re.compile(r"[-_/]fr[-_/.]|france", re.I)  # sitemaps français explorés en premier
MAX_DESAMBIGUISATION = 5  # pages candidates téléchargées quand plusieurs URLs portent le titre
MOTS_LIEU_IGNORES = {"france", "cedex", "region", "departement", "ile"}
FICHIER_GROUPES = common.DOSSIER_OUTPUT / "groupes.csv"
RE_SITEMAP_OFFRES = re.compile(r"job|offre|annonce|poste|career|carri|emploi|vacanc|position|recrut", re.I)
RE_CARRIERES = re.compile(r"recrut|career|carri|job|emploi|talent|rejoin|join|annonce", re.I)
FICHIER_SORTIE = common.DOSSIER_OUTPUT / "sitemap_check.csv"


def charger_offres():
    """Une offre par id_unique, en préférant la version dont l'étape A a des URLs."""
    with open(common.FICHIER_ECHANTILLON, newline="", encoding="utf-8") as f:
        echantillon = {r["id_unique"]: r for r in csv.DictReader(f)}  # uniquement l'échantillon courant
    offres = {}
    for chemin in sorted(common.DOSSIER_CACHE_OFFRES.glob("*.json")):
        o = common.lire_json(chemin)
        if not o or o["id_unique"] not in echantillon:
            continue
        precedent = offres.get(o["id_unique"])
        if precedent is None or (not precedent.get("urls_etape_A") and o.get("urls_etape_A")):
            offres[o["id_unique"]] = o
    # Colonnes de l'échantillon absentes du cache (localisation, date, groupe_doublon)
    return [{**echantillon[i], **o} for i, o in offres.items()]


def hotes_candidats(offre):
    """Hôtes non agrégateurs (étapes A et B) dont le nom ressemble à celui de l'entreprise, pages carrières d'abord."""
    nom = common.normaliser(offre["entreprise_nom"])
    compact = nom.replace(" ", "")
    mots = [m for m in nom.split() if len(m) >= 4 and m not in MOTS_GENERIQUES]
    urls = list(offre.get("urls_etape_A", [])) + [c["url"] for c in offre.get("candidats", [])]
    alternatif = str(offre.get("domaine_confiance", "")).startswith("alternatif")  # domaine déjà validé par domaine_alternatif.py
    trouves = []
    for url in urls:
        if common.est_agregateur(url) and not alternatif:
            continue
        h = common.hote(url)
        if any(h == e or h.endswith("." + e) for e in HOTES_EXCLUS):
            continue
        plat = h.replace("-", "").replace(".", "")
        if not alternatif and not ((compact and compact in plat) or any(m in plat for m in mots)):
            continue
        trouves.append((0 if RE_CARRIERES.search(url) else 1, h))
    hotes = []
    for _, h in sorted(trouves, key=lambda x: x[0]):
        if h not in hotes:
            hotes.append(h)
    return hotes[:MAX_HOTES]


def extraire_locs(texte):
    locs = re.findall(r"<loc>\s*(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?\s*</loc>", texte, re.S)
    return [html_lib.unescape(loc) for loc in locs]


_hotes_analyses = {}
_verrous_hotes = {}
_verrou_verrous = threading.Lock()


def decouvrir_urls(hote, rafraichir=False):
    """Un hôte n'est analysé qu'une fois par run (et au plus une fois rafraîchi), même quand plusieurs threads
    le demandent en même temps : le premier fait le travail, les suivants attendent son résultat."""
    cle = (hote, rafraichir)
    with _verrou_verrous:
        verrou = _verrous_hotes.setdefault(cle, threading.Lock())
    with verrou:
        if cle not in _hotes_analyses:
            _hotes_analyses[cle] = _decouvrir_urls(hote, rafraichir)
        return _hotes_analyses[cle]


def _decouvrir_urls(hote, rafraichir):
    """Retourne (sitemaps utilisés, URLs d'offres trouvées, diagnostic {valides, essais, trop_lent}) pour un hôte.
    S'arrête après BUDGET_HOTE_S (une requête en cours va au bout de son délai)."""
    limite = time.perf_counter() + BUDGET_HOTE_S
    trop_lent = False
    base = f"https://{hote}"
    declares = fetch.sitemaps_declares(base + "/")
    essais = [f"robots:{len(declares)}"]
    sitemaps = list(declares)
    if not sitemaps:
        for chemin in CHEMINS_USUELS:
            if time.perf_counter() > limite:
                trop_lent = True
                break
            res = fetch.telecharger_texte(base + chemin, rafraichir=rafraichir)
            essais.append(f"{chemin}:{res['http'] or res['statut']}")
            if res["statut"] == "ok" and ("<urlset" in res["texte"] or "<sitemapindex" in res["texte"]):
                sitemaps = [base + chemin]
                break

    urls, utilises, vus, valides = [], [], set(), 0
    a_traiter = sorted(sitemaps, key=lambda u: 0 if RE_FRANCE.search(u) else 1)
    while a_traiter and len(vus) < MAX_SITEMAPS:
        if time.perf_counter() > limite:
            trop_lent = True
            break
        url_sm = a_traiter.pop(0)
        if url_sm in vus:
            continue
        vus.add(url_sm)
        res = fetch.telecharger_texte(url_sm, rafraichir=rafraichir)
        if res["statut"] != "ok":
            continue
        valides += 1
        locs = extraire_locs(res["texte"])
        if "<sitemapindex" in res["texte"]:
            sous = [loc for loc in locs if RE_SITEMAP_OFFRES.search(loc)] or locs  # index sans nom évocateur : on explore quand même
            a_traiter.extend(sorted(sous, key=lambda u: 0 if RE_FRANCE.search(u) else 1)[:MAX_SOUS_SITEMAPS])
        else:
            offres = [loc for loc in locs if est_page_offre(loc)]
            if offres:
                urls.extend(offres)
                utilises.append(url_sm)
    if trop_lent:
        essais.append(f"budget_{BUDGET_HOTE_S}s_depasse")
    return utilises, urls, {"valides": valides, "essais": essais, "trop_lent": trop_lent}


def sitemap_perime(utilises, date_publication):
    """Vrai si un sitemap utilisé a été mis en cache au plus tard le jour de l'offre : il peut ne pas la contenir."""
    try:
        jour = date.fromisoformat(date_publication[:10])
    except ValueError:
        return False
    return any((fetch.date_cache_texte(u) or date.min) <= jour for u in utilises)


_en_cours = {}  # id_unique -> [entreprise, étape, début] : offres en cours, affichées toutes les PERIODE_SUIVI_S
_verrou_suivi = threading.Lock()


def _etape(offre, texte):
    with _verrou_suivi:
        if offre["id_unique"] in _en_cours:
            _en_cours[offre["id_unique"]][1] = texte


def traiter_suivi(offre, verifier):
    with _verrou_suivi:
        _en_cours[offre["id_unique"]] = [offre["entreprise_nom"], "démarrage", time.perf_counter()]
    try:
        return traiter(offre, verifier)
    finally:
        with _verrou_suivi:
            _en_cours.pop(offre["id_unique"], None)


def afficher_en_cours(debut):
    with _verrou_suivi:
        items = sorted(_en_cours.values(), key=lambda x: x[2])
    maintenant = time.perf_counter()
    print(f"{common.chrono(debut)} --- en cours ({len(items)}) ---")
    for entreprise, etape, t0 in items:
        print(f"      {entreprise} | {etape} | depuis {int(maintenant - t0)} s")


def jetons(texte):
    return {j for j in common.normaliser(texte).split() if j not in MOTS_IGNORES}


@functools.lru_cache(maxsize=None)  # une URL de sitemap est comparée à toutes les offres de l'entreprise
def jetons_slug(url):
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    return frozenset(jetons(re.sub(r"^\d+[-_]", "", slug)))


def classer_urls(titre, urls):
    """[(couverture, jaccard, url)] triés : part des mots du titre présents dans le slug, puis Jaccard."""
    mots = jetons(titre)
    if len(mots) < 2:
        return []
    classes = []
    for url in set(urls):
        slug = jetons_slug(url)
        inter = len(mots & slug)
        classes.append((inter / len(mots), inter / len(mots | slug), url))
    return sorted(classes, key=lambda x: (-x[0], -x[1]))


def score_lieu(localisation, texte):
    """Mots du lieu de l'offre retrouvés dans `texte` ; un département (2 chiffres) vaut pour un code postal."""
    attendus = {t for t in common.normaliser(localisation).split()
                if (len(t) >= 3 or t.isdigit()) and t not in MOTS_LIEU_IGNORES}
    presents = set(common.normaliser(texte).split())
    return sum(1 for t in attendus
               if t in presents or (len(t) == 2 and t.isdigit()
                                    and any(len(p) == 5 and p.isdigit() and p.startswith(t) for p in presents)))


def ecart_jours(date_page, date_offre):
    try:
        return abs((date.fromisoformat(date_page[:10]) - date.fromisoformat(date_offre[:10])).days)
    except ValueError:
        return 999


def empreinte(description):
    return common.cle_cache(common.normaliser(description)) if description else ""


def traiter(offre, verifier):
    ligne = {
        "id_unique": offre["id_unique"], "entreprise": offre["entreprise_nom"], "titre": offre["titre"],
        "source": offre["source"], "date_publication": offre.get("date_publication", ""),
        "localisation": offre.get("localisation_libelle", ""), "groupe_doublon": offre.get("groupe_doublon", ""),
        "candidats": "",
        "hotes": "", "essais": "", "sitemap_url": "", "nb_urls_offres": 0, "meilleure_couverture": 0.0,
        "meilleure_url": "", "nb_candidats": 0, "desambiguisation": "", "retrouvee": False, "cause": "",
        "verif_statut": "", "verif_cause": "", "jsonld": "", "longueur": "", "titre_page": "", "lieu_page": "",
        "date_page": "", "empreinte": "", "rafraichi": False, "duree_sitemaps_s": 0.0, "duree_verif_s": 0.0,
    }
    if not offre.get("urls_etape_A"):
        ligne["cause"] = "etape_A_vide"
        return ligne
    hotes = hotes_candidats(offre)
    ligne["hotes"] = " ".join(hotes)
    if not hotes:
        ligne["cause"] = "aucun_hote_employeur"
        return ligne

    debut = time.perf_counter()
    urls, utilises, sitemap_vu, trop_lent, essais = [], [], False, False, []
    for h in hotes:
        _etape(offre, f"sitemaps {h}")
        utilises, urls, diag = decouvrir_urls(h)
        sitemap_vu = sitemap_vu or diag["valides"] > 0
        trop_lent = trop_lent or diag["trop_lent"]
        essais.append(f"{h} [{' '.join(diag['essais'])}]")
        if urls:
            break
    if not urls:
        ligne["essais"] = " | ".join(essais)
        ligne["duree_sitemaps_s"] = round(time.perf_counter() - debut, 1)
        ligne["cause"] = ("hote_trop_lent" if trop_lent
                          else "sitemap_sans_urls_offres" if sitemap_vu else "sitemap_introuvable")
        return ligne

    classes = classer_urls(offre["titre"], urls)
    candidats = [c for c in classes if c[0] >= SEUIL_COUVERTURE]
    if not candidats and sitemap_perime(utilises, ligne["date_publication"]):
        # Sitemap en cache antérieur à l'offre : on le relit une fois (par hôte et par run) avant de conclure
        _etape(offre, f"rafraîchissement {h}")
        utilises2, urls2, diag2 = decouvrir_urls(h, rafraichir=True)
        ligne["rafraichi"] = True
        essais.append(f"{h} rafraichi [{' '.join(diag2['essais'])}]")
        if urls2:
            utilises, urls = utilises2, urls2
            classes = classer_urls(offre["titre"], urls)
            candidats = [c for c in classes if c[0] >= SEUIL_COUVERTURE]
    ligne["essais"] = " | ".join(essais)
    ligne["duree_sitemaps_s"] = round(time.perf_counter() - debut, 1)
    ligne["sitemap_url"] = " ".join(utilises)
    ligne["nb_urls_offres"] = len(set(urls))
    if classes:
        ligne["meilleure_couverture"], ligne["meilleure_url"] = round(classes[0][0], 2), classes[0][2]
    ligne["nb_candidats"] = len(candidats)
    if not candidats:
        ligne["cause"] = "titre_non_present"
        return ligne
    ligne["retrouvee"] = True

    # Plusieurs URLs portent le titre : la ville de l'offre dans l'URL départage déjà souvent, sans téléchargement
    loc = ligne["localisation"]
    lieu_url = lambda c: score_lieu(loc, urlparse(c[2]).path.replace("-", " ").replace("_", " "))
    if len(candidats) > 1:
        candidats.sort(key=lambda c: (-lieu_url(c), -c[0], -c[1]))
        if lieu_url(candidats[0]) > lieu_url(candidats[1]):
            ligne["desambiguisation"] = "lieu_url"
            candidats = candidats[:1]
    ligne["meilleure_url"] = candidats[0][2]
    ligne["candidats"] = " ".join(c[2] for c in candidats[:MAX_DESAMBIGUISATION])  # départagés ensuite par regrouper.py
    if not verifier:
        return ligne

    # Seul le premier candidat est téléchargé ici ; le départage se fait après coup, sur les pages déjà en cache
    debut = time.perf_counter()
    _etape(offre, f"page {candidats[0][2]}")
    analyse = fetch.analyser_page(candidats[0][2], offre["titre"])
    statut, cause = statut_de_analyse(analyse, candidats[0][0])
    ligne.update({"verif_statut": statut, "verif_cause": cause,
                  "jsonld": analyse["jobposting_jsonld"], "longueur": analyse["longueur_description"],
                  "titre_page": analyse["titre_page"], "lieu_page": analyse["lieu_page"], "date_page": analyse["date_page"],
                  "duree_verif_s": round(time.perf_counter() - debut, 1)})
    if statut == "description_disponible":
        ligne["empreinte"] = empreinte(analyse["description"])
    return ligne


def afficher_ligne(i, total, ligne, debut):
    resultat = "RETROUVÉE" if ligne["retrouvee"] else ligne["cause"]
    print(f"{common.chrono(debut)} [{i}/{total}] {ligne['entreprise']} | {ligne['titre'][:45]} -> {resultat}"
          f"{' (sitemap rafraîchi)' if ligne['rafraichi'] else ''}")
    print(f"      hôtes : {ligne['hotes'] or '-'} | sitemap : {ligne['sitemap_url'] or '-'} | URLs d'offres : {ligne['nb_urls_offres']}")
    if ligne["essais"]:
        print(f"      essais : {ligne['essais']}")
    if ligne["meilleure_url"]:
        print(f"      meilleure : {ligne['meilleure_couverture']} ({ligne['nb_candidats']} ≥ {SEUIL_COUVERTURE}) {ligne['meilleure_url']}")
    if ligne["desambiguisation"]:
        print(f"      désambiguïsation : {ligne['desambiguisation']} ({ligne['nb_candidats']} candidats) | lieu offre « {ligne['localisation']} » | lieu page « {ligne['lieu_page']} »")
    if ligne["verif_statut"]:
        print(f"      vérif : {ligne['verif_statut']} {ligne['verif_cause']} | JSON-LD {ligne['jsonld']} | {ligne['longueur']} car.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=None, help="ne traiter que les N premières entreprises")
    parser.add_argument("--verifier", action="store_true", help="télécharger la page retenue et la classer")
    parser.add_argument("--threads", type=int, default=NB_THREADS, help="entreprises traitées en parallèle (1 = séquentiel)")
    args = parser.parse_args()

    common.creer_dossiers()
    offres = charger_offres()
    if args.n:
        offres = offres[: args.n]

    debut = time.perf_counter()
    print(f"{len(offres)} offres à traiter ({args.threads} threads)")
    lignes, interrompu = [], False
    pool = ThreadPoolExecutor(max_workers=max(1, args.threads))
    # Affichage dans l'ordre d'achèvement ; attente par tranches de 5 s pour que Ctrl+C soit pris en compte sous Windows
    futurs = {pool.submit(traiter_suivi, o, args.verifier): rang for rang, o in enumerate(offres)}
    en_attente, dernier_suivi = set(futurs), time.perf_counter()
    try:
        while en_attente:
            faits, en_attente = wait(en_attente, timeout=5, return_when=FIRST_COMPLETED)
            for futur in faits:
                ligne = futur.result()
                ligne["_rang"] = futurs[futur]
                lignes.append(ligne)
                afficher_ligne(len(lignes), len(offres), ligne, debut)
            if en_attente and time.perf_counter() - dernier_suivi >= PERIODE_SUIVI_S:
                afficher_en_cours(debut)
                dernier_suivi = time.perf_counter()
        pool.shutdown()
    except KeyboardInterrupt:
        interrompu = True
        print(f"\nInterruption : écriture des {len(lignes)} offres déjà traitées.")
        pool.shutdown(wait=False, cancel_futures=True)
    if not lignes:
        os._exit(1)

    lignes.sort(key=lambda l: l.pop("_rang"))  # le CSV garde l'ordre de l'échantillon
    with open(FICHIER_SORTIE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0].keys()))
        w.writeheader()
        w.writerows(lignes)

    print(f"\n{len(lignes)} offres -> {FICHIER_SORTIE}")
    print("Sitemap avec URLs d'offres :", sum(1 for l in lignes if l["nb_urls_offres"] > 0))
    print("Offre retrouvée dans le sitemap :", sum(1 for l in lignes if l["retrouvee"]))
    print("Causes :", dict(Counter(l["cause"] or "retrouvee" for l in lignes)))
    print("Vérification (premier candidat) :", dict(Counter(l["verif_statut"] for l in lignes if l["verif_statut"])))
    a_departager = sum(1 for l in lignes if len(l["candidats"].split()) > 1)
    print(f"Offres à plusieurs candidats (départagées par regrouper.py) : {a_departager}")

    # Cumuls par offre : leur rapport à la durée réelle mesure le gain du multi-thread
    common.journaliser("sitemap_check", debut, offres=len(lignes), threads=args.threads, verifier=args.verifier,
                       interrompu=interrompu, rafraichies=sum(1 for l in lignes if l["rafraichi"]),
                       retrouvees=sum(1 for l in lignes if l["retrouvee"]),
                       descriptions=sum(1 for l in lignes if l["verif_statut"] == "description_disponible"),
                       a_departager=a_departager, cumul_sitemaps_s=round(sum(l["duree_sitemaps_s"] for l in lignes)),
                       cumul_verif_s=round(sum(l["duree_verif_s"] for l in lignes)),
                       causes=dict(Counter(l["cause"] or "retrouvee" for l in lignes)))
    if interrompu:
        os._exit(1)  # les threads encore en vol ne bloquent pas la sortie ; run_all.bat s'arrête


if __name__ == "__main__":
    main()

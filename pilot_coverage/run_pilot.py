"""Pilote : pour chaque offre de input/offers_sample.csv, retrouve la description sur le site de l'employeur.
Un fichier JSON par offre est écrit dès qu'elle est traitée (cache/offers/) : relance sans perte ni dépense inutile."""
import argparse
import csv
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
import re
import time

import common
import fetch
from search import PlafondAtteint, etat_compteurs, search

NB_THREADS = 6  # offres en parallèle ; les recherches restent cadencées par fournisseur (voir search._cadence)
SEUIL_CANDIDAT = 0.25
NB_CANDIDATS_TESTES = 3
RANG_STATUT = {"description_disponible": 0, "page_sans_description": 1, "bloque": 2, "introuvable": 3}


def perimetre(url):
    """Périmètre du 'site:' : domaine racine, ou hôte + premier segment pour un ATS (ex. jobs.lever.co/acme)."""
    if common.ats_detecte(url):
        segments = [s for s in urlparse(url).path.split("/") if s]
        return common.hote(url) + ("/" + segments[0] if segments else "")
    return common.domaine_racine(common.hote(url))


def dans_perimetre(url, scope):
    if "/" in scope:
        hote_scope, _, chemin = scope.partition("/")
        return common.hote(url) == hote_scope and urlparse(url).path.lstrip("/").startswith(chemin)
    return common.appartient_au_domaine(url, scope)


def choisir_domaine(entreprise, resultats):
    """Premier résultat non agrégateur dont l'hôte ressemble au nom de l'entreprise, sinon le premier non agrégateur."""
    nom = common.normaliser(entreprise)
    compact = nom.replace(" ", "")
    premier_mot = nom.split(" ")[0] if nom else ""
    candidats = [r for r in resultats if not common.est_agregateur(r["url"])]
    for r in candidats:
        h = common.hote(r["url"]).replace("-", "").replace(".", "")
        if (compact and compact in h) or (len(premier_mot) >= 4 and premier_mot in h):
            return perimetre(r["url"]), "nom_dans_hote"
    if candidats:
        return perimetre(candidats[0]["url"]), "premier_resultat"
    return None, ""


def score_candidat(titre_offre, resultat):
    slug = urlparse(resultat["url"]).path.rstrip("/").split("/")[-1].replace("-", " ").replace("_", " ")
    return max(fetch.score_titre(titre_offre, resultat["titre"]), fetch.score_titre(titre_offre, slug))


def est_page_offre(url):
    """Indice que l'URL est une page d'offre (et non une formation, un listing ou une page de services)."""
    chemin = urlparse(url).path
    return bool(common.ats_detecte(url)) or bool(re.search(
        r"/(job|jobs|offre|offres|offer|offers|emploi|emplois|poste|postes|position|positions|vacancy|vacancies|"
        r"annonce|annonces|recrutement|career|careers|carriere|carrieres)(/|$)", chemin, re.I))


def statut_de_analyse(a, score_cand):
    sp = a["statut_page"]
    if sp in ("bloque", "robots"):
        return "bloque", sp
    if sp != "ok":
        return "introuvable", f"page_inaccessible_{sp}"
    if not (a["jobposting_jsonld"] or est_page_offre(a["url_finale"])):
        return "introuvable", "page_non_offre"  # formation, témoignage, listing ou page de services
    if a["longueur_description"] > common.MIN_DESCRIPTION and a["titre_coherent"]:
        return "description_disponible", ""
    if max(a["score_titre"], score_cand) < common.SEUIL_TITRE:
        return "introuvable", "titre_incoherent"  # la page n'est pas l'offre cherchée
    if a["longueur_description"] < 50:
        return "page_sans_description", "description_vide_ou_js"
    if a["longueur_description"] <= common.MIN_DESCRIPTION:
        return "page_sans_description", "description_courte"
    return "page_sans_description", "titre_page_different"



def _compter(consommees, sortie):
    if not sortie["cache"] and sortie["fournisseur"]:
        consommees[sortie["fournisseur"]] += 1


def traiter_offre(offre, etape_a_seule=False):
    res = {
        "id_unique": offre["id_unique"], "titre": offre["titre"], "entreprise_nom": offre["entreprise_nom"],
        "source": offre["source"], "liste": offre["liste"], "type_annonceur": offre["type_annonceur"],
        "url_offre": offre["url_offre"], "statut_page": "", "http": None, 
        "statut": "", "cause_echec": "", "domaine_employeur": "", "domaine_confiance": "", "url_retenue": "",
        "fournisseur_etape_A": "", "fournisseur_etape_B": "", "jobposting_jsonld": False, "ats_detecte": "",
        "longueur_description": 0, "score_titre": 0.0, "source_description": "", "titre_page": "",
        "extrait_description": "", "requetes": {},
    }
    consommees = Counter()

    def terminer(statut, cause=""):
        res["statut"], res["cause_echec"] = statut, cause
        res["requetes"] = dict(consommees)  # approximatif par offre ; les totaux exacts sont dans cache/counters.json
        return res

    if offre["type_annonceur"] == "intermediaire":
        return terminer("intermediaire")

    # Étape A : domaine employeur
    sortie_a = search(f"{offre['entreprise_nom']} site officiel carrières")
    _compter(consommees, sortie_a)
    res["fournisseur_etape_A"] = sortie_a["fournisseur"] or ""
    res["urls_etape_A"] = [r["url"] for r in sortie_a["resultats"][:5]]
    scope, confiance = choisir_domaine(offre["entreprise_nom"], sortie_a["resultats"])
    if not scope:
        return terminer("introuvable", "domaine_non_identifie")
    res["domaine_employeur"], res["domaine_confiance"] = scope, confiance
    res["ats_detecte"] = common.ats_detecte(scope)
    if etape_a_seule:
        return terminer("etape_A_seule")

    # Étape B : pages candidates dans le domaine (ou un ATS connu)
    sortie_b = search(f"site:{scope} {offre['titre']}")
    _compter(consommees, sortie_b)
    res["fournisseur_etape_B"] = sortie_b["fournisseur"] or ""
    candidats = [
        r for r in sortie_b["resultats"]
        if not common.est_agregateur(r["url"]) and (dans_perimetre(r["url"], scope) or common.ats_detecte(r["url"]))
    ]
    if not candidats:
        return terminer("introuvable", "aucun_resultat_dans_le_domaine")
    classes = sorted(((score_candidat(offre["titre"], r), r) for r in candidats), key=lambda x: -x[0])
    res["candidats"] = [{"url": r["url"], "titre": r["titre"], "score": round(s, 3)} for s, r in classes[:5]]
    classes = [(s, r) for s, r in classes if s >= SEUIL_CANDIDAT][:NB_CANDIDATS_TESTES]
    if not classes:
        return terminer("introuvable", "aucun_candidat_proche")

    # Récupération : on s'arrête au premier candidat qui donne une description disponible
    retenu = None
    for score, r in classes:
        analyse = fetch.analyser_page(r["url"], offre["titre"])
        statut, cause = statut_de_analyse(analyse, score)
        if retenu is None or RANG_STATUT[statut] < RANG_STATUT[retenu[0]]:
            retenu = (statut, cause, analyse)
        if statut == "description_disponible":
            break

    statut, cause, a = retenu
    res["url_retenue"] = a["url_finale"]
    res["statut_page"], res["http"] = a["statut_page"], a["http"]
    res["jobposting_jsonld"] = a["jobposting_jsonld"]
    res["ats_detecte"] = common.ats_detecte(a["url_finale"]) or res["ats_detecte"]
    res["longueur_description"] = a["longueur_description"]
    res["score_titre"] = a["score_titre"]
    res["source_description"] = a["source_description"]
    res["titre_page"] = a["titre_page"]
    res["extrait_description"] = a["description"][:500]
    return terminer(statut, cause)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=None, help="ne traiter que les N premières offres")
    parser.add_argument("--fournisseurs", default=None, help="ex. duckduckgo ou duckduckgo,brave (défaut : brave,duckduckgo,serper)")
    parser.add_argument("--etape-a-seule", action="store_true", help="ne cherche que le domaine employeur (étape A), saute l'étape B")
    parser.add_argument("--threads", type=int, default=NB_THREADS, help="offres traitées en parallèle (1 = séquentiel)")
    args = parser.parse_args()
    if args.fournisseurs:
        common.choisir_fournisseurs(args.fournisseurs)
    print("Fournisseurs :", ", ".join(common.ORDRE_FOURNISSEURS))

    common.creer_dossiers()
    if not common.FICHIER_ECHANTILLON.exists():
        sys.exit("input/offers_sample.csv absent : lancer d'abord 00_inspect_schema.py")
    with open(common.FICHIER_ECHANTILLON, newline="", encoding="utf-8") as f:
        offres = list(csv.DictReader(f))
    if args.n:
        offres = offres[: args.n]

    def traiter_avec_cache(offre):
        chemin = common.DOSSIER_CACHE_OFFRES / f"{common.cle_cache(offre['id_unique'] + common.CACHE_SUFFIXE + ('|A' if args.etape_a_seule else ''))}.json"
        res = common.lire_json(chemin)
        if res is not None:
            return res, "déjà traité"
        try:
            res = traiter_offre(offre, args.etape_a_seule)
        except PlafondAtteint as e:
            return None, str(e)
        common.ecrire_json(chemin, res)
        return res, "traité"

    debut = time.perf_counter()
    resultats = []
    with ThreadPoolExecutor(max_workers=max(1, args.threads)) as pool:
        # map conserve l'ordre : l'affichage suit l'échantillon, avec un léger décalage
        sortie = pool.map(traiter_avec_cache, offres)
        for i, (res, etat) in enumerate(sortie, 1):
            if res is None:
                print(f"\nPLAFOND ATTEINT ({etat}) : arrêt. Reste à faire : {len(offres) - len(resultats)} offres.")
                break
            resultats.append(res)
            afficher_offre(i, len(offres), res, etat, debut)

    print("\nStatuts :", dict(Counter(r["statut"] for r in resultats)))
    c = etat_compteurs()
    print(f"Requêtes de recherche : {c['total']}/{common.MAX_REQUETES_TOTAL}")
    for nom, s in c["fournisseurs"].items():
        print(f"  {nom} : {s['requetes']} (exploitables {s['exploitables']}, 429 {s['erreurs_429']}, erreurs {s['erreurs']})")
    common.journaliser("run_pilot", debut, offres=len(resultats), threads=args.threads, etape_a_seule=args.etape_a_seule,
                       fournisseurs=",".join(common.ORDRE_FOURNISSEURS), requetes_total=c["total"],
                       statuts=dict(Counter(r["statut"] for r in resultats)))


def afficher_offre(i, total, res, etat, debut):
    cause = f" ({res['cause_echec']})" if res["cause_echec"] else ""
    print(f"{common.chrono(debut)} [{i}/{total}] {etat} | {res['entreprise_nom']} | {res['titre'][:50]} -> {res['statut']}{cause}")
    print(f"      offre : {res.get('url_offre', '')}")
    print(f"      domaine : {res['domaine_employeur'] or '-'} ({res['domaine_confiance'] or '-'})")
    for u in res.get("urls_etape_A", [])[:3]:
        print(f"      A  {u}")
    for c in res.get("candidats", [])[:3]:
        print(f"      B  {c['score']:.2f}  {c['url']}  « {c['titre'][:60]} »")
    if res["url_retenue"]:
        print(f"      retenue : {res['url_retenue']}")
        print(f"      page : « {res['titre_page']} » | HTTP {res['http']} ({res['statut_page']}) | {res['longueur_description']} car. | JSON-LD {res['jobposting_jsonld']} | score titre {res['score_titre']}")
        print(f"      début : {res['extrait_description'][:300]}")


if __name__ == "__main__":
    main()

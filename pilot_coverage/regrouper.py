"""Étape après sitemap_check.py : départage les offres à plusieurs candidats, puis regroupe les descriptions
(descr => titre1, titre2, ...). Travaille sur les pages déjà en cache ; --telecharger récupère les candidats manquants.
Écrit output/sitemap_final.csv et output/groupes.csv."""
import argparse
import csv
import time
from collections import Counter

import common
import fetch
from run_pilot import statut_de_analyse
from sitemap_check import FICHIER_GROUPES, FICHIER_SORTIE, ecart_jours, empreinte, score_lieu

FICHIER_FINAL = common.DOSSIER_OUTPUT / "sitemap_final.csv"


def en_cache(url):
    return (common.DOSSIER_CACHE_PAGES / f"{common.cle_cache(url)}.json").exists()


def a_departager(ligne):
    return len(ligne["candidats"].split()) > 1 and ligne["desambiguisation"] != "lieu_url" and ligne["verif_statut"]


def departager(ligne, telecharger):
    """Choisit, parmi les candidats, la page dont le lieu (jobLocation) puis la date (datePosted) collent à l'offre."""
    urls = [u for u in ligne["candidats"].split() if telecharger or en_cache(u)]
    analyses = [a for a in (fetch.analyser_page(u, ligne["titre"]) for u in urls) if a["statut_page"] == "ok"]
    if len(analyses) < 2:
        ligne["desambiguisation"] = "non_tranche"  # autres candidats absents du cache : relancer avec --telecharger
        return
    note = lambda a: (score_lieu(ligne["localisation"], a["lieu_page"]), -ecart_jours(a["date_page"], ligne["date_publication"]))
    analyses.sort(key=note, reverse=True)  # tri stable : l'ordre du sitemap départage les égalités
    if len({empreinte(a["description"]) for a in analyses if a["description"]}) <= 1:
        ligne["desambiguisation"] = "meme_description"  # peu importe la page : le texte est identique
    elif note(analyses[0]) > note(analyses[1]):
        ligne["desambiguisation"] = "page"
    else:
        ligne["desambiguisation"] = "ambigu"
        ligne["retrouvee"], ligne["cause"] = "False", "ambigu"  # ne compte pas comme une réussite
    appliquer(ligne, analyses[0])


def appliquer(ligne, a):
    statut, cause = statut_de_analyse(a, float(ligne["meilleure_couverture"] or 0))
    ligne.update({"meilleure_url": a["url"], "verif_statut": statut, "verif_cause": cause,
                  "jsonld": a["jobposting_jsonld"], "longueur": a["longueur_description"], "titre_page": a["titre_page"],
                  "lieu_page": a["lieu_page"], "date_page": a["date_page"], "source_description": a["source_description"],
                  "empreinte": empreinte(a["description"]) if statut == "description_disponible" else ""})


def reanalyser(ligne):
    """Relit depuis le cache la page retenue par sitemap_check.py : titres réparés (encodage) et source de la
    description (jsonld / html), sans relancer sitemap_check."""
    if en_cache(ligne["meilleure_url"]):
        appliquer(ligne, fetch.analyser_page(ligne["meilleure_url"], ligne["titre"]))


def cle_groupe(l):
    """Description JSON-LD : l'empreinte suffit. Description extraite du HTML (repli) : elle peut être un gabarit
    commun à toutes les pages carrières, on n'y regroupe que des pages au même titre."""
    if l["source_description"] == "jsonld":
        return l["empreinte"]
    return f"{l['empreinte']}|{common.normaliser(l['titre_page'])}"


def regrouper(lignes):
    """Une ligne par description distincte : descr => titres des alertes qui y mènent."""
    groupes = {}
    for l in lignes:
        if l["verif_statut"] != "description_disponible" or not l["empreinte"] or l["cause"] == "ambigu":
            continue
        g = groupes.setdefault(cle_groupe(l), {"empreinte": l["empreinte"], "source_description": l["source_description"],
                                               "titre_officiel": l["titre_page"], "longueur": l["longueur"],
                                               "urls": set(), "titres": set(), "sources": set(),
                                               "entreprises": set(), "groupes_doublon": set(), "nb_offres": 0})
        g["nb_offres"] += 1
        g["urls"].add(l["meilleure_url"])
        g["titres"].add(l["titre"])
        g["sources"].add(l["source"])
        g["entreprises"].add(l["entreprise"])
        if l["groupe_doublon"]:
            g["groupes_doublon"].add(l["groupe_doublon"])
    lignes_groupes = [
        {"empreinte": g["empreinte"], "source_description": g["source_description"],
         "titre_officiel": g["titre_officiel"], "nb_offres": g["nb_offres"], "nb_titres": len(g["titres"]),
         "titres": " || ".join(sorted(g["titres"])), "nb_groupes_doublon": len(g["groupes_doublon"]),
         "entreprises": " | ".join(sorted(g["entreprises"])), "sources": " ".join(sorted(g["sources"])),
         "urls": " ".join(sorted(g["urls"])), "longueur": g["longueur"]}
        for g in groupes.values()
    ]
    return sorted(lignes_groupes, key=lambda g: (-g["nb_titres"], -g["nb_offres"]))


def ecrire_csv(chemin, lignes):
    if lignes:
        with open(chemin, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(lignes[0].keys()))
            w.writeheader()
            w.writerows(lignes)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--telecharger", action="store_true",
                        help="télécharger les candidats absents du cache (sinon : départage sur les seules pages déjà vues)")
    args = parser.parse_args()

    debut = time.perf_counter()
    with open(FICHIER_SORTIE, newline="", encoding="utf-8") as f:
        lignes = list(csv.DictReader(f))
    for l in lignes:
        l.setdefault("source_description", "")  # colonne identique sur toutes les lignes du CSV final
    cibles = [l for l in lignes if a_departager(l)]
    print(f"{len(lignes)} offres lues ({FICHIER_SORTIE.name}), {len(cibles)} à départager")

    for l in lignes:
        if l["verif_statut"] and not a_departager(l):
            reanalyser(l)
    for i, l in enumerate(cibles, 1):
        departager(l, args.telecharger)
        print(f"{common.chrono(debut)} [{i}/{len(cibles)}] {l['entreprise']} | {l['titre'][:45]} -> {l['desambiguisation']}"
              f" | lieu offre « {l['localisation']} » | lieu page « {l['lieu_page']} »")
    ecrire_csv(FICHIER_FINAL, lignes)

    groupes = regrouper(lignes)
    ecrire_csv(FICHIER_GROUPES, groupes)
    desambiguisation = dict(Counter(l["desambiguisation"] for l in cibles))
    print(f"\nDésambiguïsation : {desambiguisation}")
    print(f"Offres retrouvées (hors ambiguës) : {sum(1 for l in lignes if l['retrouvee'] == 'True')} -> {FICHIER_FINAL}")
    print(f"Descriptions distinctes : {len(groupes)} -> {FICHIER_GROUPES}")
    print("  avec plusieurs titres :", sum(1 for g in groupes if g["nb_titres"] > 1))
    print("  réunissant plusieurs groupe_doublon du mart :", sum(1 for g in groupes if g["nb_groupes_doublon"] > 1))
    for g in [g for g in groupes if g["nb_titres"] > 1][:5]:
        print(f"  « {g['titre_officiel'][:60]} » <= {g['titres'][:150]}")

    common.journaliser("regrouper", debut, offres=len(lignes), a_departager=len(cibles), telecharger=args.telecharger,
                       desambiguisation=desambiguisation,
                       retrouvees=sum(1 for l in lignes if l["retrouvee"] == "True"),
                       descriptions=sum(1 for l in lignes if l["verif_statut"] == "description_disponible"),
                       groupes=len(groupes), groupes_multi_titres=sum(1 for g in groupes if g["nb_titres"] > 1))


if __name__ == "__main__":
    main()

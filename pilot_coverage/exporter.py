"""Après regrouper.py : un dossier par entreprise de l'échantillon, rangé dans avec_description/ ou sans_description/.
Chaque dossier contient entreprise.txt (infos locales, bilan, offres datées) et un .txt par description distincte,
préfixé par la date de l'offre. Lit uniquement les CSV et le cache : aucun téléchargement.
Le dossier output/entreprises/ est vidé puis régénéré à chaque lancement."""
import argparse
import csv
import re
import shutil
import textwrap
import time
from collections import Counter, defaultdict

import common
import fetch
from regrouper import FICHIER_FINAL, cle_groupe, en_cache
from sitemap_check import charger_offres

# --- Paramètres configurables ---
DOSSIER_EXPORT = common.DOSSIER_OUTPUT / "entreprises"
DOSSIER_AVEC = DOSSIER_EXPORT / "avec_description"
DOSSIER_SANS = DOSSIER_EXPORT / "sans_description"
LONGUEUR_NOM_ENTREPRISE = 40  # chemins Windows limités à 260 caractères
LONGUEUR_NOM_OFFRE = 60
LARGEUR_TEXTE = 100

fetch.TAILLE_DESCRIPTION_STOCKEE = 10 ** 8  # texte complet ici (5 000 caractères ailleurs)


def slug(texte, longueur):
    return re.sub(r"[^a-z0-9]+", "-", common.normaliser(texte)).strip("-")[:longueur].strip("-") or "sans-titre"


def jour(valeur):
    return (valeur or "")[:10] or "date-inconnue"


def charger():
    """Lignes de sitemap_final.csv complétées des infos locales : types (échantillon), origine du domaine (cache)."""
    with open(FICHIER_FINAL, newline="", encoding="utf-8") as f:
        lignes = list(csv.DictReader(f))
    with open(common.FICHIER_ECHANTILLON, newline="", encoding="utf-8") as f:
        echantillon = {r["id_unique"]: r for r in csv.DictReader(f)}
    caches = {o["id_unique"]: o for o in charger_offres()}
    for l in lignes:
        e, o = echantillon.get(l["id_unique"], {}), caches.get(l["id_unique"], {})
        l["type_annonceur"] = e.get("type_annonceur", "")
        l["type_entreprise"] = e.get("type_entreprise", "")
        l["domaine_confiance"] = str(o.get("domaine_confiance") or "")
    return lignes


def a_description(l):
    return l["verif_statut"] == "description_disponible" and l["empreinte"] and l["cause"] != "ambigu"


def resultat(l):
    return "description" if l.get("_fichier") else (l["cause"] or l["verif_statut"] or "retrouvee")


def ecrire_offre(dossier, membres, noms_pris):
    """Un fichier par description distincte, nommé <date la plus récente>_<titre de la page>.txt."""
    ref = max(membres, key=lambda l: jour(l["date_publication"]))
    dates = sorted({jour(l["date_publication"]) for l in membres}, reverse=True)
    nom = f"{dates[0]}_{slug(ref['titre_page'] or ref['titre'], LONGUEUR_NOM_OFFRE)}"
    if nom in noms_pris:
        nom += "_" + ref["empreinte"][:6]
    noms_pris.add(nom)

    url = ref["meilleure_url"]
    description = fetch.analyser_page(url, ref["titre"])["description"] if en_cache(url) else "(page absente du cache)"
    unique = lambda cle: " | ".join(sorted({l[cle] for l in membres if l.get(cle)})) or "-"
    entete = [
        f"DATE DE L'OFFRE : {dates[0]}" + (f"  (alertes : {', '.join(dates)})" if len(dates) > 1 else ""),
        f"Date sur la page : {ref['date_page'] or '-'}",
        f"TITRE : {ref['titre_page'] or ref['titre']}",
        f"Titres des alertes : {' || '.join(sorted({l['titre'] for l in membres}))}",
        f"Entreprise : {unique('entreprise')}",
        f"Lieu (alerte) : {unique('localisation')}  |  lieu (page) : {ref['lieu_page'] or '-'}",
        f"Sources : {unique('source')}",
        f"URL : {unique('meilleure_url')}",
        f"Description : {ref['source_description'] or '-'}, {len(description)} caractères",
    ]
    texte = "\n".join(entete) + "\n" + "-" * LARGEUR_TEXTE + "\n" + textwrap.fill(description, LARGEUR_TEXTE) + "\n"
    (dossier / f"{nom}.txt").write_text(texte, encoding="utf-8")
    for l in membres:
        l["_fichier"] = f"{nom}.txt"


def ecrire_fiche(dossier, lignes, nb_descriptions, jours):
    unique = lambda cle: " | ".join(sorted({l[cle] for l in lignes if l.get(cle)})) or "-"
    retrouvees = sum(1 for l in lignes if l["retrouvee"] == "True")
    texte = [
        f"ENTREPRISE : {unique('entreprise')}",
        f"Type d'annonceur : {unique('type_annonceur')}",
        f"Type d'entreprise : {unique('type_entreprise')}",
        f"Origine du domaine : {unique('domaine_confiance')}",
        f"Hôtes analysés : {unique('hotes')}",
        f"Sitemap(s) : {unique('sitemap_url')}",
        "",
        f"BILAN ({jours or 'toutes les'} jours) : {len(lignes)} offres, {retrouvees} retrouvées, "
        f"{nb_descriptions} descriptions distinctes",
        f"Résultats : {dict(Counter(resultat(l) for l in lignes))}",
        "",
        "OFFRES (plus récentes d'abord) : date | titre | lieu | source | résultat",
    ]
    for l in sorted(lignes, key=lambda l: jour(l["date_publication"]), reverse=True):
        texte.append(f"{jour(l['date_publication'])} | {l['titre']} | {l['localisation'] or '-'} | {l['source']} | "
                     f"{resultat(l)}" + (f" -> {l['_fichier']}" if l.get("_fichier") else ""))
    (dossier / "entreprise.txt").write_text("\n".join(texte) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jours", type=int, default=common.JOURS_MAX,
                        help="période de l'échantillon, reportée dans le bilan des fiches (même valeur que 00_inspect_schema.py)")
    args = parser.parse_args()
    debut = time.perf_counter()
    lignes = charger()
    par_entreprise = defaultdict(list)
    for l in lignes:
        par_entreprise[slug(l["entreprise"], LONGUEUR_NOM_ENTREPRISE)].append(l)

    shutil.rmtree(DOSSIER_EXPORT, ignore_errors=True)
    nb_avec = nb_fichiers = 0
    for cle, lignes_ent in sorted(par_entreprise.items()):
        groupes = defaultdict(list)
        for l in lignes_ent:
            if a_description(l):
                groupes[cle_groupe(l)].append(l)
        dossier = (DOSSIER_AVEC if groupes else DOSSIER_SANS) / cle
        dossier.mkdir(parents=True, exist_ok=True)
        noms_pris = set()
        for membres in groupes.values():
            ecrire_offre(dossier, membres, noms_pris)
        ecrire_fiche(dossier, lignes_ent, len(groupes), args.jours)
        nb_avec += bool(groupes)
        nb_fichiers += len(groupes)
        if groupes:
            print(f"{common.chrono(debut)} {cle} : {len(groupes)} description(s)")

    print(f"\n{len(par_entreprise)} entreprises -> {DOSSIER_EXPORT}")
    print(f"  avec description : {nb_avec} ({nb_fichiers} fichiers d'offres) -> {DOSSIER_AVEC}")
    print(f"  sans description : {len(par_entreprise) - nb_avec} -> {DOSSIER_SANS}")
    common.journaliser("exporter", debut, jours=args.jours, entreprises=len(par_entreprise), avec_description=nb_avec,
                       sans_description=len(par_entreprise) - nb_avec, fichiers_offres=nb_fichiers)


if __name__ == "__main__":
    main()

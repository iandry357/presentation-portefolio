"""Compare deux lots archivés (output/lots/<lot>/) : pour chaque offre du lot --apres, est-elle déjà vue,
republiée (même description ou même titre chez la même entreprise, sous un nouvel identifiant) ou nouvelle ?
Lit uniquement sitemap_final.csv des deux lots (toutes les offres y figurent). Écrit comparaison.csv dans le lot --apres."""
import argparse
import csv
import time
from collections import Counter, defaultdict
from pathlib import Path

import common
from sitemap_check import jetons

# --- Paramètres configurables ---
DOSSIER_LOTS = common.DOSSIER_OUTPUT / "lots"
NOM_SOURCE = "sitemap_final.csv"
NOM_SORTIE = "comparaison.csv"
MAX_LIGNES_AFFICHEES = 40


def lire_lot(dossier):
    with open(Path(dossier) / NOM_SOURCE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def deux_derniers_lots():
    lots = sorted(d for d in DOSSIER_LOTS.iterdir() if (d / NOM_SOURCE).exists())
    if len(lots) < 2:
        raise SystemExit(f"Moins de deux lots avec {NOM_SOURCE} dans {DOSSIER_LOTS}")
    return lots[-2], lots[-1]


def entreprise(l):
    return common.normaliser(l["entreprise"])


def titre(l):
    return " ".join(sorted(jetons(l["titre"])))  # sans H/F, CDI, ordre des mots indifférent


def a_description(l):
    return l["verif_statut"] == "description_disponible" and l["empreinte"] and l["cause"] != "ambigu"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--avant", help="dossier du lot de référence (défaut : avant-dernier lot)")
    parser.add_argument("--apres", help="dossier du lot comparé (défaut : dernier lot)")
    args = parser.parse_args()
    debut = time.perf_counter()

    defaut_avant, defaut_apres = (None, None) if args.avant and args.apres else deux_derniers_lots()
    dossier_avant, dossier_apres = Path(args.avant or defaut_avant), Path(args.apres or defaut_apres)
    avant, apres = lire_lot(dossier_avant), lire_lot(dossier_apres)
    print(f"Avant : {dossier_avant.name} ({len(avant)} offres) | après : {dossier_apres.name} ({len(apres)} offres)")

    par_id = {l["id_unique"]: l for l in avant}
    par_empreinte = {l["empreinte"]: l for l in avant if a_description(l)}
    par_titre = {(entreprise(l), titre(l)): l for l in avant}
    entreprises_avant = {entreprise(l) for l in avant}
    date_max_avant = max((l["date_publication"][:10] for l in avant if l["date_publication"]), default="")

    sortie = []
    for l in apres:
        if l["id_unique"] in par_id:
            statut, ref = "deja_vue", par_id[l["id_unique"]]
        elif a_description(l) and l["empreinte"] in par_empreinte:
            statut, ref = "republiee_meme_description", par_empreinte[l["empreinte"]]
        elif (entreprise(l), titre(l)) in par_titre:
            statut, ref = "republiee_meme_titre", par_titre[(entreprise(l), titre(l))]
        else:
            statut, ref = "nouvelle", {}
        sortie.append({
            "statut": statut, "entreprise": l["entreprise"], "titre": l["titre"],
            "date_publication": l["date_publication"][:10], "description": "oui" if a_description(l) else "",
            "entreprise_nouvelle": entreprise(l) not in entreprises_avant,
            "id_unique": l["id_unique"], "id_avant": ref.get("id_unique", ""), "titre_avant": ref.get("titre", ""),
            "date_avant": ref.get("date_publication", "")[:10], "source": l["source"], "source_avant": ref.get("source", ""),
        })

    with open(dossier_apres / NOM_SORTIE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(sortie[0].keys()))
        w.writeheader()
        w.writerows(sortie)

    statuts = Counter(s["statut"] for s in sortie)
    print(f"\nOffres du lot après : {dict(statuts)}")
    deja = [s for s in sortie if s["statut"] == "deja_vue"]
    print(f"  déjà vues datées au plus tard du {date_max_avant} (période commune aux deux lots) : "
          f"{sum(1 for s in deja if s['date_publication'] <= date_max_avant)}/{len(deja)}")

    ent_apres = defaultdict(list)
    for s in sortie:
        ent_apres[common.normaliser(s["entreprise"])].append(s)
    nouvelles_ent = [e for e, ss in ent_apres.items() if ss[0]["entreprise_nouvelle"]]
    print(f"Entreprises du lot après : {len(ent_apres)} | nouvelles : {len(nouvelles_ent)} | "
          f"déjà vues : {len(ent_apres) - len(nouvelles_ent)}")

    republiees = sorted((s for s in sortie if s["statut"].startswith("republiee")),
                        key=lambda s: (s["entreprise"].lower(), s["titre"]))
    print(f"\nRepubliées sous un nouvel identifiant ({len(republiees)}) : entreprise | titre | date avant -> après | règle")
    for s in republiees[:MAX_LIGNES_AFFICHEES]:
        regle = "description" if s["statut"] == "republiee_meme_description" else "titre"
        print(f"  {s['entreprise']} | {s['titre'][:60]} | {s['date_avant']} -> {s['date_publication']} | {regle}")
    if len(republiees) > MAX_LIGNES_AFFICHEES:
        print(f"  ... {len(republiees) - MAX_LIGNES_AFFICHEES} autres dans {NOM_SORTIE}")

    nouvelles_desc = [s for s in sortie if s["statut"] == "nouvelle" and s["description"]]
    print(f"\nNouvelles offres avec description ({len(nouvelles_desc)}) :")
    for s in sorted(nouvelles_desc, key=lambda s: s["entreprise"].lower())[:MAX_LIGNES_AFFICHEES]:
        print(f"  {s['date_publication']} | {s['entreprise']}{' (nouvelle entreprise)' if s['entreprise_nouvelle'] else ''}"
              f" | {s['titre'][:60]}")

    print(f"\nDétail -> {dossier_apres / NOM_SORTIE}")
    common.journaliser("comparer_lots", debut, avant=dossier_avant.name, apres=dossier_apres.name,
                       statuts=dict(statuts), entreprises_nouvelles=len(nouvelles_ent),
                       entreprises_deja_vues=len(ent_apres) - len(nouvelles_ent))


if __name__ == "__main__":
    main()

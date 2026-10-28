"""Exploration : champs de l'API ADEME dpe03existant et volumes de Paris, pour choisir les champs à collecter.
Lecture seule. Depuis realisations/immobilier, venv-explore activé :
    python scripts/explore_dpe_champs.py > pipeline/data/bdnb/rapports/dpe_champs.txt
"""
import sys

import requests

# ── Paramètres ──────────────────────────────────────────────
DPE_API = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant"
CHAMP_DEPARTEMENT = "code_departement_ban"
DEPARTEMENT = "75"
CHAMP_DATE = "date_etablissement_dpe"
DATE_DEBUT = "2025-05-01"
LARGEUR_LIBELLE = 90
TIMEOUT = 60
CHAMPS_ACTUELS = [  # DPE_CHAMPS_API de pipeline/config.py (marqués d'une étoile)
    "numero_dpe", "numero_dpe_remplace", "date_etablissement_dpe", "date_reception_dpe",
    "modele_dpe", "version_dpe", "methode_application_dpe", "etiquette_dpe", "etiquette_ges",
    "conso_5_usages_par_m2_ep", "type_energie_principale_chauffage", "type_batiment",
    "periode_construction", "annee_construction", "surface_habitable_logement",
    "numero_etage_appartement", "adresse_ban", "identifiant_ban", "code_postal_ban",
    "code_insee_ban", "nom_commune_ban", "code_departement_ban",
    "coordonnee_cartographique_x_ban", "coordonnee_cartographique_y_ban",
]


def get(chemin, **params):
    r = requests.get(f"{DPE_API}/{chemin}", params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def total(qs):
    return get("lines", qs=qs, size=1, select=CHAMP_DATE)["total"]


def extreme(qs, tri):
    resultats = get("lines", qs=qs, size=1, sort=tri, select=CHAMP_DATE)["results"]
    return resultats[0][CHAMP_DATE] if resultats else None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    paris = f"{CHAMP_DEPARTEMENT}:{DEPARTEMENT}"

    print("== Volumes (département", DEPARTEMENT, ")")
    print("tous les DPE                 :", total(paris))
    print(f"depuis {DATE_DEBUT}          :", total(f"{paris} AND {CHAMP_DATE}:[{DATE_DEBUT} TO *]"))
    print("avec numero_dpe_remplace      :", total(f"{paris} AND _exists_:numero_dpe_remplace"))
    print("première date d'établissement :", extreme(paris, CHAMP_DATE))
    print("dernière date d'établissement :", extreme(paris, f"-{CHAMP_DATE}"))

    champs = get("schema")
    print(f"\n== Champs de l'API ({len(champs)}) ; * = déjà collecté par la V1")
    for champ in champs:
        marque = "*" if champ["key"] in CHAMPS_ACTUELS else " "
        libelle = (champ.get("title") or champ.get("x-originalName") or "")[:LARGEUR_LIBELLE]
        print(f"{marque} {champ['key']} | {champ.get('type', '')} | {libelle}")


if __name__ == "__main__":
    main()

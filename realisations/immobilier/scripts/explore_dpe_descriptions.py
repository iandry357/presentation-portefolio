"""Exploration : description et valeurs possibles des champs DPE collectés (schéma de l'API ADEME dpe03existant).
Lecture seule. Depuis realisations/immobilier, venv-explore activé :
    python scripts/explore_dpe_descriptions.py > pipeline/data/bdnb/rapports/dpe_descriptions.txt
"""
import sys

import requests

from pipeline.dpe_ademe.config import CHAMPS_API, DPE_API

# ── Paramètres ──────────────────────────────────────────────
TIMEOUT = 60
NB_VALEURS_MAX = 12          # valeurs possibles affichées par champ


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    r = requests.get(f"{DPE_API}/schema", timeout=TIMEOUT)
    r.raise_for_status()
    schema = {champ["key"]: champ for champ in r.json()}

    sans_description = 0
    for nom in CHAMPS_API:
        champ = schema.get(nom)
        if champ is None:
            print(f"{nom} | ABSENT DU SCHÉMA")
            continue
        description = (champ.get("description") or "").strip()
        sans_description += not description
        valeurs = champ.get("enum") or []
        suite = f" | valeurs : {valeurs[:NB_VALEURS_MAX]}" if valeurs else ""
        print(f"{nom} | {champ.get('type', '')} | {description or '(pas de description)'}{suite}")
    print(f"\n{len(CHAMPS_API)} champs, {sans_description} sans description")


if __name__ == "__main__":
    main()

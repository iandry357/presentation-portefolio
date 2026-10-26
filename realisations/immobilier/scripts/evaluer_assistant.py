"""Contrôle de l'assistant bailleur (R4) : questions du jeu envoyées à la route POST /immobilier/assistant/chat du backend lancé,
puis vérification automatique de chaque réponse. À relancer après tout changement de prompt, de modèle ou de corpus.

Usage : python scripts\\evaluer_assistant.py [--detail] [--sortie] [--id 1 --id 5]
Prérequis : backend démarré (docker-compose up -d backend, depuis backend/), port 8000.
--detail : réponse et sources de chaque cas. --sortie : résultat complet dans pipeline/data/referentiel/rapports.
Un cas contrôle : refus attendu ou non ; « doit_contenir » (chaque élément est un texte, ou une liste de variantes dont une suffit) ;
« ne_doit_pas_contenir » ; « sources_attendues » (au moins une référence citée contient l'un des textes). Comparaison sans casse,
sans accents ni espaces. Chaque question part sans cookie : la limite de débit par visiteur ne s'applique pas.
"""
import argparse
import json
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import requests

# --- Paramètres ---
URL = "http://localhost:8000/immobilier/assistant/chat"
TIMEOUT = 120
PAUSE_SEC = 1  # entre deux questions
RACINE = Path(__file__).resolve().parent.parent  # realisations/immobilier
FICHIER_JEU = Path(__file__).resolve().parent / "jeu_assistant_referentiel.json"
DOSSIER_RAPPORTS = RACINE / "pipeline" / "data" / "referentiel" / "rapports"


def normaliser(texte):
    decompose = unicodedata.normalize("NFD", texte.lower())
    sans_accents = "".join(c for c in decompose if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", "", sans_accents)


def interroger(cas):
    corps = {"question": cas["question"], "historique": cas.get("historique", [])}
    debut = time.perf_counter()
    r = requests.post(URL, json=corps, timeout=TIMEOUT)
    duree = time.perf_counter() - debut
    r.raise_for_status()
    return r.json(), duree


def controler(cas, reponse):
    """Liste des écarts entre la réponse et ce que le cas exige (vide = conforme)."""
    erreurs = []
    if reponse["refus"] != cas["refus"]:
        erreurs.append(f"refus = {reponse['refus']} au lieu de {cas['refus']}")
    if cas["refus"]:
        if reponse["sources"]:
            erreurs.append("refus accompagné de sources")
        return erreurs
    if not reponse["sources"]:
        erreurs.append("aucune source")
    texte = normaliser(reponse["reponse"])
    for attendu in cas.get("doit_contenir", []):
        variantes = [attendu] if isinstance(attendu, str) else attendu
        if not any(normaliser(v) in texte for v in variantes):
            erreurs.append("absent : " + " | ".join(variantes))
    for interdit in cas.get("ne_doit_pas_contenir", []):
        if normaliser(interdit) in texte:
            erreurs.append(f"présent alors qu'interdit : {interdit}")
    attendues = cas.get("sources_attendues", [])
    if attendues:
        references = [normaliser(s["reference"]) for s in reponse["sources"]]
        if not any(normaliser(a) in ref for a in attendues for ref in references):
            erreurs.append("aucune source parmi : " + " | ".join(attendues))
    return erreurs


def main():
    parser = argparse.ArgumentParser(description="Contrôle de l'assistant bailleur.")
    parser.add_argument("--detail", action="store_true", help="réponse et sources de chaque cas")
    parser.add_argument("--sortie", action="store_true", help="écrit le résultat complet dans pipeline/data/referentiel/rapports")
    parser.add_argument("--id", type=int, action="append", help="ne lancer que ce cas (répétable)")
    args = parser.parse_args()

    jeu = json.loads(FICHIER_JEU.read_text(encoding="utf-8"))
    cas_a_lancer = [c for c in jeu["cas"] if not args.id or c["id"] in args.id]
    resultats = []
    for i, cas in enumerate(cas_a_lancer):
        if i:
            time.sleep(PAUSE_SEC)
        try:
            reponse, duree = interroger(cas)
            erreurs = controler(cas, reponse)
            mots = len(reponse["reponse"].split())
            print(f"{'OK' if not erreurs else 'KO'}  Q{cas['id']:<3}{cas['question'][:62]:<64}{duree:5.1f} s  {mots:4d} mots  {reponse.get('modele')}")
        except requests.exceptions.RequestException as e:
            reponse, duree, erreurs = None, None, [f"appel en échec : {e}"]
            print(f"KO  Q{cas['id']:<3}{cas['question'][:62]}")
        for e in erreurs:
            print(f"      - {e}")
        if args.detail and reponse:
            print("\n" + reponse["reponse"])
            for n, s in enumerate(reponse["sources"], 1):
                print(f"  [{n}] {s['reference']} ({s['statut']}, version du {s['date_version']}) {s['url']}")
            print()
        resultats.append({"cas": cas, "reponse": reponse, "duree_s": duree and round(duree, 1), "erreurs": erreurs})

    conformes = sum(1 for r in resultats if not r["erreurs"])
    print(f"\n{conformes}/{len(resultats)} cas conformes (jeu du {jeu['version']})")

    if args.sortie:
        DOSSIER_RAPPORTS.mkdir(parents=True, exist_ok=True)
        chemin = DOSSIER_RAPPORTS / f"{datetime.now():%Y%m%d_%H%M%S}_assistant.json"
        chemin.write_text(json.dumps({"jeu": jeu["version"], "conformes": conformes, "total": len(resultats), "resultats": resultats},
                                     ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Résultat écrit : {chemin}")


if __name__ == "__main__":
    main()

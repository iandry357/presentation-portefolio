"""Évaluation de la recherche du référentiel bailleur (R3, backlog 40) : succès au top 3 et au top 5 de trois stratégies
(vecteurs seuls, BM25 seul, fusion RRF), sans puis avec filtre de thème, sur scripts/jeu_evaluation_referentiel.json.
Lecture seule : chunks.json local (BM25), vecteurs dans ChromaDB OVH ou en mémoire, questions embeddées par l'API Mistral. Aucune écriture distante.

Usage : python scripts\\evaluer_recherche.py [--detail] [--sortie] [--vecteurs chroma|mistral]
--detail : top 5 de chaque stratégie pour chaque question. --sortie : résultat complet dans pipeline/data/referentiel/rapports.
Un attendu est un identifiant de chunk (métadonnée « identifiant ») ; une étoile finale signifie « préfixe » (BOFiP).
Succès à k : au moins un attendu dans les k premiers chunks. Rappel à 5 : part des attendus retrouvés dans les 5 premiers.
Les questions « hors_corpus » sont exclues des mesures ; leur meilleur score est affiché.
"""
import argparse
import hashlib
import json
import os
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import chromadb
import numpy as np
import requests
from chromadb.config import Settings
from dotenv import load_dotenv
from rank_bm25 import BM25Okapi

# --- Paramètres ---
RACINE = Path(__file__).resolve().parent.parent  # realisations/immobilier
ENV = RACINE / "pipeline" / ".env"
DOSSIER_REF = RACINE / "pipeline" / "data" / "referentiel"
FICHIER_CHUNKS = DOSSIER_REF / "corpus" / "chunks.json"
FICHIER_JEU = Path(__file__).resolve().parent / "jeu_evaluation_referentiel.json"
DOSSIER_RAPPORTS = DOSSIER_REF / "rapports"
COLLECTION = "referentiel_immobilier"
VARIABLES = ("CHROMA_HOST", "CHROMA_USER", "CHROMA_PASSWORD", "MISTRAL_API_KEY")
TIMEOUT = 120
TOPS = (3, 5, 8)
NB_CANDIDATS = 50  # profondeur lue dans chaque liste : fusion et rang du premier attendu
RRF_K = 60
MISTRAL_URL = "https://api.mistral.ai/v1/embeddings"
MISTRAL_MODELE = "mistral-embed"
MISTRAL_LOT = 8  # textes par requête : la limite de tokens par requête n'est pas documentée (16 384 en 2024 d'après un cookbook)
MISTRAL_ESSAIS = 5  # tentatives après une limite de débit (429), pause de 1 s, 2 s, 4 s...
FICHIER_CACHE_MISTRAL = DOSSIER_REF / "corpus" / "embeddings_mistral.json"

STRATEGIES = {"vecteurs": "Vecteurs", "bm25": "BM25", "rrf": "Fusion RRF", "union": "Union"}
MOTS_VIDES = {  # sans accents, comme les jetons
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "au", "aux", "en", "ce", "que", "qui", "pour", "par", "sur",
    "dans", "est", "sont", "ou", "il", "je", "mon", "ma", "puis", "dois", "quel", "quelle", "quels", "quelles", "comment",
    "combien", "qu",
}


def tokeniser(texte):
    decompose = unicodedata.normalize("NFD", texte.lower())
    sans_accents = "".join(c for c in decompose if unicodedata.category(c) != "Mn")
    return [m for m in re.findall(r"\w+", sans_accents) if len(m) > 1 and m not in MOTS_VIDES]


def client_chroma():
    return chromadb.HttpClient(
        host=os.getenv("CHROMA_HOST"), port=int(os.getenv("CHROMA_PORT", "8000")),
        settings=Settings(
            chroma_client_auth_provider="chromadb.auth.basic_authn.BasicAuthClientProvider",
            chroma_client_auth_credentials=f"{os.getenv('CHROMA_USER')}:{os.getenv('CHROMA_PASSWORD')}",
            anonymized_telemetry=False,
        ),
    )


def rechercher_vecteurs(collection, vecteur, themes):
    """Distance cosinus (plus petite = plus proche)."""
    where = {"theme": {"$in": themes}} if themes else None
    r = collection.query(query_embeddings=[vecteur], n_results=NB_CANDIDATS, where=where, include=["distances"])
    return list(zip(r["ids"][0], r["distances"][0]))

def embedder_mistral(textes):
    """Vecteurs mistral-embed par lots de MISTRAL_LOT textes ; nouvelle tentative après une limite de débit (429)."""
    entetes = {"Authorization": f"Bearer {os.getenv('MISTRAL_API_KEY')}"}
    vecteurs = []
    for i in range(0, len(textes), MISTRAL_LOT):
        for essai in range(MISTRAL_ESSAIS):
            r = requests.post(MISTRAL_URL, headers=entetes, json={"model": MISTRAL_MODELE, "input": textes[i:i + MISTRAL_LOT]}, timeout=TIMEOUT)
            if r.status_code != 429:
                break
            time.sleep(2 ** essai)
        r.raise_for_status()
        vecteurs.extend(d["embedding"] for d in sorted(r.json()["data"], key=lambda d: d["index"]))
        print(f"Mistral : {len(vecteurs)}/{len(textes)} textes")
    if len(vecteurs) != len(textes):
        raise ValueError(f"{len(vecteurs)} vecteurs reçus pour {len(textes)} textes")
    return vecteurs


def vecteurs_chunks_mistral(chunks):
    """Vecteurs des chunks : calculés une fois, relus du cache tant que le corpus et le modèle ne changent pas."""
    empreinte = hashlib.sha256("".join(c["document"] for c in chunks).encode("utf-8")).hexdigest()
    if FICHIER_CACHE_MISTRAL.exists():
        cache = json.loads(FICHIER_CACHE_MISTRAL.read_text(encoding="utf-8"))
        if cache["empreinte"] == empreinte and cache["modele"] == MISTRAL_MODELE:
            return np.array(cache["vecteurs"])
    vecteurs = embedder_mistral([c["document"] for c in chunks])
    FICHIER_CACHE_MISTRAL.write_text(json.dumps({"modele": MISTRAL_MODELE, "empreinte": empreinte, "vecteurs": vecteurs}), encoding="utf-8")
    return np.array(vecteurs)


def rechercher_vecteurs_memoire(matrice, chunks, vecteur, themes):
    """Distance cosinus (1 - cosinus) sur les vecteurs en mémoire ; même format que rechercher_vecteurs."""
    v = np.array(vecteur)
    distances = 1 - (matrice @ v) / (np.linalg.norm(matrice, axis=1) * np.linalg.norm(v))
    classes = [int(i) for i in np.argsort(distances)]
    if themes:
        classes = [i for i in classes if chunks[i]["metadata"]["theme"] in themes]
    return [(chunks[i]["id"], float(distances[i])) for i in classes[:NB_CANDIDATS]]


def rechercher_bm25(bm25, chunks, question, themes):
    """Score BM25 (plus grand = meilleur) ; le filtre de thème s'applique après le calcul, l'IDF reste celui du corpus entier."""
    scores = bm25.get_scores(tokeniser(question))
    classes = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)
    if themes:
        classes = [i for i in classes if chunks[i]["metadata"]["theme"] in themes]
    return [(chunks[i]["id"], float(scores[i])) for i in classes[:NB_CANDIDATS]]


def fusionner(*listes):
    """Reciprocal Rank Fusion : somme de 1 / (RRF_K + rang) sur les listes."""
    scores = {}
    for liste in listes:
        for rang, (id_chunk, _) in enumerate(liste, 1):
            scores[id_chunk] = scores.get(id_chunk, 0) + 1 / (RRF_K + rang)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:NB_CANDIDATS]


def entrelacer(*listes):
    """Union : alterne les listes (rang 1 de chacune, puis rang 2, etc.) sans doublon ; les 8 premiers valent ≈ 4 de chaque liste."""
    vus, union = set(), []
    for rang in range(max(len(liste) for liste in listes)):
        for liste in listes:
            if rang < len(liste) and liste[rang][0] not in vus:
                vus.add(liste[rang][0])
                union.append(liste[rang])
    return union[:NB_CANDIDATS]


def correspond(attendu, identifiant):
    return identifiant.startswith(attendu[:-1]) if attendu.endswith("*") else identifiant == attendu


def evaluer(resultats, attendus, par_id):
    """Renvoie (rang du premier attendu retrouvé ou None, rappel à TOPS[-1])."""
    identifiants = [par_id[id_chunk]["metadata"]["identifiant"] for id_chunk, _ in resultats]
    rang = next((r for r, ident in enumerate(identifiants, 1) if any(correspond(a, ident) for a in attendus)), None)
    top = identifiants[:TOPS[-1]]
    rappel = sum(1 for a in attendus if any(correspond(a, ident) for ident in top)) / len(attendus)
    return rang, rappel


def afficher_detail(question, cles, resultats, par_id):
    print(f"\nQ{question['id']} : {question['question']}  (attendus : {', '.join(question['attendus']) or 'aucun'})")
    for cle in cles:
        filtre, strategie = cle
        print(f"  {STRATEGIES[strategie]} {'avec' if filtre else 'sans'} filtre")
        for rang, (id_chunk, score) in enumerate(resultats[cle][:TOPS[-1]], 1):
            m = par_id[id_chunk]["metadata"]
            print(f"    {rang}. {score:.3f}  {m['identifiant']}  {m['theme']}  {m['reference']}")


def main():
    parser = argparse.ArgumentParser(description="Évaluation de la recherche du référentiel bailleur.")
    parser.add_argument("--vecteurs", choices=("chroma", "mistral"), default="chroma", help="recherche vectorielle : ChromaDB OVH (défaut, chemin de production) ou vecteurs en mémoire (cache local)")
    parser.add_argument("--detail", action="store_true", help="top 5 de chaque stratégie pour chaque question")
    parser.add_argument("--sortie", action="store_true", help="écrit le résultat complet dans pipeline/data/referentiel/rapports")
    args = parser.parse_args()

    load_dotenv(ENV)
    variables = ("MISTRAL_API_KEY",) if args.vecteurs == "mistral" else VARIABLES
    manquantes = [nom for nom in variables if not os.getenv(nom)]
    if manquantes:
        raise SystemExit("Variables à définir dans pipeline/.env : " + ", ".join(manquantes))

    chunks = json.loads(FICHIER_CHUNKS.read_text(encoding="utf-8"))["chunks"]
    jeu = json.loads(FICHIER_JEU.read_text(encoding="utf-8"))
    par_id = {c["id"]: c for c in chunks}
    bm25 = BM25Okapi([tokeniser(c["document"]) for c in chunks])

    vecteurs_questions = dict(zip((q["id"] for q in jeu["questions"]), embedder_mistral([q["question"] for q in jeu["questions"]])))
    if args.vecteurs == "mistral":
        matrice = vecteurs_chunks_mistral(chunks)
    else:
        collection = client_chroma().get_collection(COLLECTION)
        if collection.count() != len(chunks):
            print(f"Attention : {collection.count()} chunks dans ChromaDB, {len(chunks)} dans chunks.json")

    cles_toutes = [(filtre, strategie) for filtre in (False, True) for strategie in STRATEGIES]
    resultats = {}  # id de question -> {(filtre, strategie): [(id de chunk, score)]}
    for q in jeu["questions"]:
        vecteur = vecteurs_questions[q["id"]]
        resultats[q["id"]] = {}
        for filtre in (False, True):
            themes = q["themes"] if filtre else []
            if filtre and not themes:
                continue
            liste_v = (rechercher_vecteurs_memoire(matrice, chunks, vecteur, themes) if args.vecteurs == "mistral"
                       else rechercher_vecteurs(collection, vecteur, themes))
            liste_b = rechercher_bm25(bm25, chunks, q["question"], themes)
            for strategie, liste in (("vecteurs", liste_v), ("bm25", liste_b), ("rrf", fusionner(liste_v, liste_b)),
                                     ("union", entrelacer(liste_b, liste_v))):
                resultats[q["id"]][(filtre, strategie)] = liste

    questions = [q for q in jeu["questions"] if not q.get("hors_corpus")]
    mesures = {cle: [evaluer(resultats[q["id"]][cle], q["attendus"], par_id) for q in questions] for cle in cles_toutes}

    print(f"\nSynthèse ({len(questions)} questions, jeu du {jeu['version']})")
    print(f"{'Filtre':<8}{'Stratégie':<14}" + "".join(f"succès@{t:<4}" for t in TOPS) + f"rappel@{TOPS[-1]}")
    synthese = {}
    for cle in cles_toutes:
        filtre, strategie = cle
        succes = [sum(1 for rang, _ in mesures[cle] if rang and rang <= t) for t in TOPS]
        rappel = sum(r for _, r in mesures[cle]) / len(questions)
        synthese[f"{'avec' if filtre else 'sans'}_filtre/{strategie}"] = {
            **{f"succes_{t}": s for t, s in zip(TOPS, succes)}, f"rappel_{TOPS[-1]}": round(rappel, 3), "questions": len(questions),
        }
        print(f"{'avec' if filtre else 'sans':<8}{STRATEGIES[strategie]:<14}"
              + "".join(f"{s}/{len(questions):<9}" for s in succes) + f"{rappel:.2f}")

    print(f"\nRang du premier attendu (- : absent du top {NB_CANDIDATS})")
    print(f"{'Q':<4}" + "".join(f"{'avec' if f else 'sans'}:{STRATEGIES[s]:<14}" for f, s in cles_toutes))
    for i, q in enumerate(questions):
        print(f"{q['id']:<4}" + "".join(f"{str(mesures[cle][i][0] or '-'):<19}" for cle in cles_toutes))

    for q in jeu["questions"]:
        if q.get("hors_corpus"):
            r = resultats[q["id"]]
            print(f"\nQ{q['id']} hors corpus : meilleure distance {r[(False, 'vecteurs')][0][1]:.3f}, "
                  f"meilleur score BM25 {r[(False, 'bm25')][0][1]:.2f} ({q['question']})")

    if args.detail:
        for q in jeu["questions"]:
            afficher_detail(q, list(resultats[q["id"]]), resultats[q["id"]], par_id)

    if args.sortie:
        DOSSIER_RAPPORTS.mkdir(parents=True, exist_ok=True)
        chemin = DOSSIER_RAPPORTS / f"{datetime.now():%Y%m%d_%H%M%S}_evaluation_{args.vecteurs}.json"
        questions_sortie = {}
        for q in jeu["questions"]:
            questions_sortie[str(q["id"])] = {
                f"{'avec' if f else 'sans'}_filtre/{s}": [
                    {"rang": r, "id": id_chunk, "identifiant": par_id[id_chunk]["metadata"]["identifiant"],
                     "reference": par_id[id_chunk]["metadata"]["reference"], "score": round(score, 4)}
                    for r, (id_chunk, score) in enumerate(liste[:TOPS[-1]], 1)
                ] for (f, s), liste in resultats[q["id"]].items()
            }
        chemin.write_text(json.dumps({"jeu": jeu["version"], "vecteurs": args.vecteurs, "synthese": synthese, "questions": questions_sortie},
                                     ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nRésultat écrit : {chemin}")


if __name__ == "__main__":
    main()

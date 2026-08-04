"""
diagnostic_grief_frequencies.py — MVP Banque de France / diagnostic ponctuel

Script à usage unique (pas un artefact du pipeline principal) : recompte la
fréquence brute de TOUS les concept_final classés GRIEF sur l'ensemble du
corpus éligible (mêmes exclusions structurelles que dataset.py — motif vide,
2014-04, décision sans aucun GRIEF — mais SANS le seuil >=5 de sélection des
catégories retenues).

Objectif : disposer des vrais volumes avant de décider d'éventuels
regroupements de catégories rares, plutôt que de regrouper à l'aveugle sur
la seule base des libellés.

Usage :
  python diagnostic_grief_frequencies.py
"""

import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

# --------------------------------------------------------------------------
# Configuration (identique à dataset.py)
# --------------------------------------------------------------------------

PROJECT_ID = "gen-lang-client-0989575872"
DATASET_ID = "banque_de_france_veille"
TABLE_ID = "articles_bruts"

BASE_DIR = Path(__file__).resolve().parent
SA_KEY_PATH = BASE_DIR.parents[1] / "gcp_sa_banque.json"
TAXONOMY_PATH = BASE_DIR / "exploration_taxonomy" / "taxonomy_mapping.json"

EXCLUDED_DECISIONS = {"2014-04"}


# --------------------------------------------------------------------------
# Fonctions reprises telles quelles de dataset.py (mêmes règles de normalisation)
# --------------------------------------------------------------------------

def normalize_segment(text: str) -> str:
    text = text.replace("\u2019", "'")
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def load_taxonomy_mapping(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        entries = json.load(f)
    mapping = {}
    for entry in entries:
        key = normalize_segment(entry["segment"])
        mapping[key] = (entry["concept_final"], entry["categorie"])
    return mapping


def fetch_acpr_chunks() -> pd.DataFrame:
    credentials = service_account.Credentials.from_service_account_file(str(SA_KEY_PATH))
    client = bigquery.Client(project=PROJECT_ID, credentials=credentials)

    query = f"""
        SELECT id, content, metadata
        FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`
        WHERE source = 'acpr_decision'
    """
    rows = list(client.query(query).result())

    records = []
    for row in rows:
        meta = row["metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta)
        records.append({
            "decision_number": meta.get("decision_number"),
            "chunk_index": meta.get("chunk_index"),
            "content": row["content"] or "",
            "motif": meta.get("motif"),
        })
    return pd.DataFrame(records)


def reconstruct_decisions(df: pd.DataFrame) -> pd.DataFrame:
    decisions = []
    for decision_number, group in df.groupby("decision_number"):
        group_sorted = group.sort_values("chunk_index")
        motif = group_sorted["motif"].iloc[0]
        decisions.append({"decision_number": decision_number, "motif": motif})
    return pd.DataFrame(decisions)


def extract_grief_labels(motif: str, mapping: dict) -> list:
    if not motif or not motif.strip():
        return []
    labels = []
    for raw_segment in motif.split(";"):
        segment = normalize_segment(raw_segment)
        if not segment or segment not in mapping:
            continue
        concept_final, categorie = mapping[segment]
        if categorie == "GRIEF":
            labels.append(concept_final)
    return list(dict.fromkeys(labels))


# --------------------------------------------------------------------------
# Diagnostic
# --------------------------------------------------------------------------

def main():
    mapping = load_taxonomy_mapping(TAXONOMY_PATH)
    raw_chunks = fetch_acpr_chunks()
    decisions = reconstruct_decisions(raw_chunks)

    # Exclusions structurelles (identiques à dataset.py), SANS le seuil >=5
    decisions = decisions[~decisions["decision_number"].isin(EXCLUDED_DECISIONS)].copy()
    decisions = decisions[decisions["motif"].notna() & (decisions["motif"].str.strip() != "")].copy()

    decisions["grief_labels"] = decisions["motif"].map(lambda m: extract_grief_labels(m, mapping))
    decisions = decisions[decisions["grief_labels"].map(len) > 0].copy()

    n_eligible = len(decisions)
    print(f"\nDécisions éligibles (après exclusions structurelles, sans seuil) : {n_eligible}\n")

    # Comptage : nombre de décisions DISTINCTES par concept (pas d'occurrences)
    counter = Counter()
    for labels in decisions["grief_labels"]:
        counter.update(set(labels))

    print(f"{'Concept GRIEF':<70} | {'Nb décisions':>12} | {'% du corpus':>10}")
    print("-" * 98)
    for concept, count in counter.most_common():
        pct = 100 * count / n_eligible
        print(f"{concept:<70} | {count:>12} | {pct:>9.1f}%")

    print(f"\nTotal de concepts GRIEF distincts observés : {len(counter)}")


if __name__ == "__main__":
    main()
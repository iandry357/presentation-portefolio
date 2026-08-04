"""
diagnostic_group_overlap.py — MVP Banque de France / diagnostic ponctuel

Calcule, pour les regroupements de concepts GRIEF proposés, le nombre réel
de décisions distinctes par groupe (en évitant le double comptage d'une
décision portant plusieurs concepts d'un même groupe), ainsi que le
chevauchement entre groupes (une décision peut légitimement appartenir à
plusieurs groupes à la fois — c'est acceptable en multi-label, ce diagnostic
sert juste à quantifier ce chevauchement avant de figer les groupes).

Usage :
  python diagnostic_group_overlap.py
"""

import json
import re
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

# Regroupements proposés, à valider avec les volumes réels ci-dessous
GROUPS = {
    "protection de la clientèle": {
        "devoir de conseil",
        "information des assurés",
        "protection des fonds collectés",
        "respect de la réglementation assurantielle",
    },
    "déshérence et gestion des contrats": {
        "contrats en déshérence",
        "lutte contre la déshérence",
        "contrats d'assurance-vie non réclamés",
        "contrats d'assurance-vie non réglés",
        "modification de contrats d'assurance",
    },
    "gouvernance et maîtrise des risques": {
        "gouvernance",
        "contrôle des opérations et procédures internes",
        "risque",
    },
}


# --------------------------------------------------------------------------
# Fonctions reprises telles quelles de dataset.py
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
# Diagnostic de chevauchement
# --------------------------------------------------------------------------

def main():
    mapping = load_taxonomy_mapping(TAXONOMY_PATH)
    raw_chunks = fetch_acpr_chunks()
    decisions = reconstruct_decisions(raw_chunks)

    decisions = decisions[~decisions["decision_number"].isin(EXCLUDED_DECISIONS)].copy()
    decisions = decisions[decisions["motif"].notna() & (decisions["motif"].str.strip() != "")].copy()
    decisions["grief_labels"] = decisions["motif"].map(lambda m: extract_grief_labels(m, mapping))
    decisions = decisions[decisions["grief_labels"].map(len) > 0].copy()

    n_eligible = len(decisions)
    print(f"\nDécisions éligibles : {n_eligible}\n")

    # Ensemble de decision_number par groupe (une décision compte une seule
    # fois par groupe, même si plusieurs concepts du groupe sont présents)
    group_decision_sets = {}
    for group_name, concepts in GROUPS.items():
        matching = decisions[decisions["grief_labels"].map(
            lambda labels: bool(set(labels) & concepts)
        )]
        group_decision_sets[group_name] = set(matching["decision_number"])

    print(f"{'Groupe':<45} | {'Nb décisions distinctes':>24} | {'% du corpus':>10}")
    print("-" * 85)
    for group_name, decision_set in group_decision_sets.items():
        count = len(decision_set)
        pct = 100 * count / n_eligible
        print(f"{group_name:<45} | {count:>24} | {pct:>9.1f}%")

    # Chevauchement pairwise entre groupes
    print("\nChevauchement entre groupes (décisions présentes dans les deux) :")
    print("-" * 85)
    group_names = list(group_decision_sets.keys())
    for i in range(len(group_names)):
        for j in range(i + 1, len(group_names)):
            g1, g2 = group_names[i], group_names[j]
            overlap = group_decision_sets[g1] & group_decision_sets[g2]
            print(f"  {g1} ∩ {g2} : {len(overlap)} décision(s) -> {sorted(overlap)}")


if __name__ == "__main__":
    main()
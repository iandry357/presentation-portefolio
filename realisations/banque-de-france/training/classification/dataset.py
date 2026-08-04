"""
dataset.py — MVP Banque de France / classification multi-label

Construit le dataset d'entraînement pour la classification des griefs de
sanction ACPR à partir des chunks stockés dans BigQuery (table
`articles_bruts`, source = 'acpr_decision'), en appliquant le mapping de
taxonomie figé (`taxonomy_mapping.json`).

Sorties :
  - training/classification/data/train/foldXX_train.csv
  - training/classification/data/train/foldXX_test.csv
  - training/classification/data/train/foldXX_weights.json
  - training/classification/data/demo/demo.csv

Usage :
  python dataset.py
"""

import json
import logging
import re
from pathlib import Path

import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from sklearn.model_selection import KFold

try:
    from iterstrat.ml_stratifiers import MultilabelStratifiedKFold
    HAS_ITERSTRAT = True
except ImportError:
    HAS_ITERSTRAT = False

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("dataset")

# --------------------------------------------------------------------------
# Configuration (paramètres ajustables)
# --------------------------------------------------------------------------

PROJECT_ID = "gen-lang-client-0989575872"
DATASET_ID = "banque_de_france_veille"
TABLE_ID = "articles_bruts"

BASE_DIR = Path(__file__).resolve().parent
SA_KEY_PATH = BASE_DIR.parents[1] / "gcp_sa_banque.json"
TAXONOMY_PATH = BASE_DIR / "exploration_taxonomy" / "taxonomy_mapping.json"

DATA_DIR = BASE_DIR / "data"
TRAIN_DIR = DATA_DIR / "train"
DEMO_DIR = DATA_DIR / "demo"

N_FOLDS = 5
RANDOM_STATE = 42

EXCLUDED_DECISIONS = {"2014-04"}  # non-lieu (abandon des poursuites)

OTHER_LABEL = "Autre"

# Taxonomie de regroupement sémantique, validée par diagnostic de volumes
# (voir diagnostic_grief_frequencies.py / diagnostic_group_overlap.py).
# Tout concept_final absent de ce mapping tombe dans OTHER_LABEL.
MACRO_CATEGORY_MAPPING = {
    "lutte contre le blanchiment et le financement du terrorisme":
        "lutte contre le blanchiment et le financement du terrorisme",

    "devoir de conseil": "protection de la clientèle",
    "information des assurés": "protection de la clientèle",
    "protection des fonds collectés": "protection de la clientèle",
    "respect de la réglementation assurantielle": "protection de la clientèle",

    "contrats en déshérence": "déshérence et gestion des contrats",
    "lutte contre la déshérence": "déshérence et gestion des contrats",
    "contrats d'assurance-vie non réclamés": "déshérence et gestion des contrats",
    "contrats d'assurance-vie non réglés": "déshérence et gestion des contrats",
    "modification de contrats d'assurance": "déshérence et gestion des contrats",

    "gouvernance": "gouvernance et maîtrise des risques",
    "contrôle des opérations et procédures internes": "gouvernance et maîtrise des risques",
    "risque": "gouvernance et maîtrise des risques",
}

RETAINED_CATEGORIES = sorted(set(MACRO_CATEGORY_MAPPING.values()))


# --------------------------------------------------------------------------
# Étape 1 — Chargement du mapping de taxonomie
# --------------------------------------------------------------------------

def normalize_segment(text: str) -> str:
    """Normalise un segment de motif pour la recherche dans le mapping :
    minuscules, apostrophes typographiques -> droites, espaces superflus."""
    text = text.replace("\u2019", "'")  # ' -> '
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def load_taxonomy_mapping(path: Path) -> dict:
    """Charge taxonomy_mapping.json et construit un dict
    segment_normalisé -> (concept_final, categorie)."""
    with open(path, "r", encoding="utf-8") as f:
        entries = json.load(f)

    mapping = {}
    for entry in entries:
        key = normalize_segment(entry["segment"])
        mapping[key] = (entry["concept_final"], entry["categorie"])

    logger.info("Taxonomie chargée : %d segments mappés", len(mapping))
    return mapping


# --------------------------------------------------------------------------
# Étape 2 — Extraction BigQuery
# --------------------------------------------------------------------------

def fetch_acpr_chunks() -> pd.DataFrame:
    """Récupère tous les chunks de décisions ACPR depuis BigQuery et
    extrait decision_number, chunk_index, motif depuis le champ metadata."""
    credentials = service_account.Credentials.from_service_account_file(str(SA_KEY_PATH))
    client = bigquery.Client(project=PROJECT_ID, credentials=credentials)

    query = f"""
        SELECT id, content, metadata
        FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`
        WHERE source = 'acpr_decision'
    """
    rows = list(client.query(query).result())
    logger.info("BigQuery : %d chunks récupérés (source=acpr_decision)", len(rows))

    records = []
    for row in rows:
        meta = row["metadata"]
        # Sécurité : gérer le cas où metadata arriverait déjà en dict (vu chez Sanofi)
        if isinstance(meta, str):
            meta = json.loads(meta)

        records.append({
            "decision_number": meta.get("decision_number"),
            "chunk_index": meta.get("chunk_index"),
            "content": row["content"] or "",
            "motif": meta.get("motif"),
        })

    df = pd.DataFrame(records)
    return df


# --------------------------------------------------------------------------
# Étape 3 — Reconstruction des décisions
# --------------------------------------------------------------------------

def reconstruct_decisions(df: pd.DataFrame) -> pd.DataFrame:
    """Regroupe les chunks par decision_number, trie par chunk_index,
    reconstruit le texte complet et retient un seul motif par décision
    (validé identique sur tous les chunks d'une même décision)."""
    decisions = []
    for decision_number, group in df.groupby("decision_number"):
        group_sorted = group.sort_values("chunk_index")
        text = "\n".join(group_sorted["content"].tolist())
        motif = group_sorted["motif"].iloc[0]

        decisions.append({
            "decision_number": decision_number,
            "text": text,
            "motif": motif,
        })

    result = pd.DataFrame(decisions)
    logger.info("Décisions reconstruites : %d", len(result))
    return result


# --------------------------------------------------------------------------
# Étape 4 & 5 — Découpage du motif, mapping, filtrage GRIEF
# --------------------------------------------------------------------------

def extract_grief_labels(motif: str, mapping: dict, decision_number: str) -> list:
    """Découpe le motif brut sur ';', normalise chaque segment, et retourne
    la liste des concept_final classés GRIEF. Logue un avertissement pour
    tout segment absent du mapping."""
    if not motif or not motif.strip():
        return []

    labels = []
    for raw_segment in motif.split(";"):
        segment = normalize_segment(raw_segment)
        if not segment:
            continue

        if segment not in mapping:
            logger.warning(
                "Segment inconnu du mapping (décision %s) : '%s'",
                decision_number, segment,
            )
            continue

        concept_final, categorie = mapping[segment]
        if categorie == "GRIEF":
            labels.append(concept_final)

    return list(dict.fromkeys(labels))  # dédoublonnage en préservant l'ordre


# --------------------------------------------------------------------------
# Étape 6 — Exclusions
# --------------------------------------------------------------------------

def apply_exclusions(decisions: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """Exclut : décisions dans EXCLUDED_DECISIONS, motif vide/null,
    et décisions dont aucun segment n'est classé GRIEF après mapping."""
    n_total = len(decisions)

    decisions = decisions[~decisions["decision_number"].isin(EXCLUDED_DECISIONS)].copy()
    n_after_manual_exclusion = len(decisions)

    decisions = decisions[decisions["motif"].notna() & (decisions["motif"].str.strip() != "")].copy()
    n_after_empty_motif = len(decisions)

    decisions["grief_labels"] = decisions.apply(
        lambda row: extract_grief_labels(row["motif"], mapping, row["decision_number"]),
        axis=1,
    )
    decisions = decisions[decisions["grief_labels"].map(len) > 0].copy()
    n_final = len(decisions)

    logger.info(
        "Exclusions : %d décisions initiales -> %d (exclusion manuelle) -> "
        "%d (motif non vide) -> %d (au moins un GRIEF)",
        n_total, n_after_manual_exclusion, n_after_empty_motif, n_final,
    )
    return decisions



# --------------------------------------------------------------------------
# Étape 7 — Vectorisation multi-label
# --------------------------------------------------------------------------

def build_multilabel_vectors(decisions: pd.DataFrame, retained_categories: list) -> pd.DataFrame:
    """Construit une colonne binaire par catégorie retenue + 'Autre'. Chaque
    concept_final brut est d'abord traduit vers sa macro-catégorie via
    MACRO_CATEGORY_MAPPING ; un concept non mappé bascule dans 'Autre'."""
    all_categories = retained_categories + [OTHER_LABEL]

    def assign_row(labels):
        row = {cat: 0 for cat in all_categories}
        for label in labels:
            macro_category = MACRO_CATEGORY_MAPPING.get(label)
            if macro_category is not None:
                row[macro_category] = 1
            else:
                row[OTHER_LABEL] = 1
        return row

    label_rows = decisions["grief_labels"].map(assign_row)
    for category in all_categories:
        decisions[category] = label_rows.map(lambda r: r[category])

    return decisions

# --------------------------------------------------------------------------
# Étape 8 — Extraction du jeu de démo
# --------------------------------------------------------------------------

def extract_demo_set(decisions: pd.DataFrame, demo_categories: list) -> tuple:
    """Sélectionne une décision par catégorie parmi demo_categories
    (sans exiger de pureté), retire ces décisions du pool restant."""
    decisions_sorted = decisions.sort_values("decision_number")
    demo_indices = []

    for category in demo_categories:
        candidates = decisions_sorted[
            (decisions_sorted[category] == 1)
            & (~decisions_sorted.index.isin(demo_indices))
        ]
        if candidates.empty:
            logger.warning("Aucune décision disponible pour la démo de catégorie '%s'", category)
            continue
        demo_indices.append(candidates.index[0])

    demo_df = decisions.loc[demo_indices].copy()
    pool_df = decisions.drop(index=demo_indices).copy()

    logger.info(
        "Jeu de démo : %d décisions extraites (sur %d catégories visées) ; pool restant : %d",
        len(demo_df), len(demo_categories), len(pool_df),
    )
    return demo_df, pool_df


# --------------------------------------------------------------------------
# Étape 9 — Construction des K-Fold
# --------------------------------------------------------------------------

def build_folds(pool_df: pd.DataFrame, retained_categories: list):
    """Génère les indices train/test pour N_FOLDS folds. Utilise
    MultilabelStratifiedKFold (package iterative-stratification) si
    disponible, sinon un KFold simple avec avertissement explicite."""
    X = pool_df.index.to_numpy()
    y = pool_df[retained_categories].to_numpy()
    if HAS_ITERSTRAT:
        splitter = MultilabelStratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)
        splits = list(splitter.split(X, y))
        logger.info("K-Fold stratifié multi-label (iterstrat), %d folds", N_FOLDS)
    else:
        logger.warning(
            "Package 'iterative-stratification' absent — repli sur KFold simple "
            "(pas de stratification par label, à documenter comme limite du POC)."
        )
        splitter = KFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)
        splits = list(splitter.split(X))

    return splits


# --------------------------------------------------------------------------
# Étape 10 — Pondération de la perte (recalculée par fold)
# --------------------------------------------------------------------------

def compute_class_weights(train_df: pd.DataFrame, retained_categories: list) -> dict:
    """Calcule un poids positif/négatif par catégorie retenue, à partir de
    la fréquence inverse observée dans le train du fold courant."""
    n = len(train_df)
    weights = {}
    for category in retained_categories:
        n_pos = int(train_df[category].sum())
        n_neg = n - n_pos
        weights[category] = {
            "n_pos": n_pos,
            "n_neg": n_neg,
            "weight_pos": round(n / (2 * n_pos), 4) if n_pos > 0 else None,
            "weight_neg": round(n / (2 * n_neg), 4) if n_neg > 0 else None,
        }
    return weights


# --------------------------------------------------------------------------
# Étape 11 — Sérialisation
# --------------------------------------------------------------------------
def export_csv(df: pd.DataFrame, path: Path, all_categories: list):
    columns = ["decision_number", "text"] + all_categories
    df[columns].to_csv(path, index=False, encoding="utf-8")
    logger.info("Écrit : %s (%d lignes)", path, len(df))


def main():
    TRAIN_DIR.mkdir(parents=True, exist_ok=True)
    DEMO_DIR.mkdir(parents=True, exist_ok=True)

    mapping = load_taxonomy_mapping(TAXONOMY_PATH)

    raw_chunks = fetch_acpr_chunks()
    decisions = reconstruct_decisions(raw_chunks)
    decisions = apply_exclusions(decisions, mapping)

    all_categories = RETAINED_CATEGORIES + [OTHER_LABEL]
    demo_categories = RETAINED_CATEGORIES  # une décision par catégorie, sur les 4

    decisions = build_multilabel_vectors(decisions, RETAINED_CATEGORIES)

    demo_df, pool_df = extract_demo_set(decisions, demo_categories)
    export_csv(demo_df, DEMO_DIR / "demo.csv", all_categories)
    export_csv(pool_df, TRAIN_DIR / "full_pool.csv", all_categories)

    pool_df = pool_df.reset_index(drop=True)
    splits = build_folds(pool_df, RETAINED_CATEGORIES)

    for fold_idx, (train_idx, test_idx) in enumerate(splits, start=1):
        train_df = pool_df.iloc[train_idx].copy()
        test_df = pool_df.iloc[test_idx].copy()

        fold_label = f"{fold_idx:02d}"
        export_csv(train_df, TRAIN_DIR / f"fold{fold_label}_train.csv", all_categories)
        export_csv(test_df, TRAIN_DIR / f"fold{fold_label}_test.csv", all_categories)

        weights = compute_class_weights(train_df, RETAINED_CATEGORIES)
        weights_path = TRAIN_DIR / f"fold{fold_label}_weights.json"
        with open(weights_path, "w", encoding="utf-8") as f:
            json.dump(weights, f, ensure_ascii=False, indent=2)
        logger.info("Écrit : %s", weights_path)

    logger.info("Terminé.")


if __name__ == "__main__":
    main()
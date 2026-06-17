"""
ner/dataset.py
Préparation du dataset NER pour fine-tuning CamemBERT.
Sources : FUNSD + MAPA + FiNER (HuggingFace)
Cible   : 5 entités SG Assurances en schéma BIO
Sortie  : data/ner_datasets/ au format HuggingFace DatasetDict

Lancer depuis training/ :
    python ner/dataset.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from datasets import load_dataset, DatasetDict, Dataset
from transformers import CamembertTokenizerFast
import json

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------
BASE       = Path(__file__).parent.parent          # training/
OUTPUT_DIR = BASE / "data" / "ner_datasets"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
MODEL_NAME = "camembert-base"
MAX_LENGTH = 512

# Schéma BIO final — 5 entités métier SG + Outside
LABEL_LIST = [
    "O",
    "B-NUMERO_POLICE", "I-NUMERO_POLICE",
    "B-NOM_ASSURE",    "I-NOM_ASSURE",
    "B-MONTANT",       "I-MONTANT",
    "B-DATE",          "I-DATE",
    "B-ADRESSE",       "I-ADRESSE",
]
LABEL2ID = {l: i for i, l in enumerate(LABEL_LIST)}
ID2LABEL = {i: l for l, i in LABEL2ID.items()}


# ---------------------------------------------------------------------------
# Tables de correspondance par source
# ---------------------------------------------------------------------------

# FUNSD : formulaires scannés — labels orientés layout
# On récupère DATE et ADRESSE (QUESTION/ANSWER portent parfois des adresses)
FUNSD_MAP = {
    "B-HEADER":   "O",
    "I-HEADER":   "O",
    "B-QUESTION": "O",
    "I-QUESTION": "O",
    "B-ANSWER":   "O",          # trop générique → O
    "I-ANSWER":   "O",
    "O":          "O",
}

# MAPA : NER juridique/administratif multilingue
# Sous-ensemble FR — labels MAPA officiels
MAPA_MAP = {
    "B-PERSON":       "B-NOM_ASSURE",
    "I-PERSON":       "I-NOM_ASSURE",
    "B-ADDRESS":      "B-ADRESSE",
    "I-ADDRESS":      "I-ADRESSE",
    "B-DATE":         "B-DATE",
    "I-DATE":         "I-DATE",
    "B-AMOUNT":       "B-MONTANT",
    "I-AMOUNT":       "I-MONTANT",
    "B-ORGANISATION": "O",
    "I-ORGANISATION": "O",
    "B-TIME":         "O",
    "I-TIME":         "O",
    "O":              "O",
}

# FiNER : NER financier — montants et identifiants
# FINER_MAP = {
#     "B-MONEY":    "B-MONTANT",
#     "I-MONEY":    "I-MONTANT",
#     "B-CARDINAL": "B-NUMERO_POLICE",   # numéros/codes financiers
#     "I-CARDINAL": "I-NUMERO_POLICE",
#     "B-DATE":     "B-DATE",
#     "I-DATE":     "I-DATE",
#     "B-PERSON":   "B-NOM_ASSURE",
#     "I-PERSON":   "I-NOM_ASSURE",
#     "O":          "O",
# }
# finer-ord-bio : tags entiers — mapping direct ID → label SG
FINER_ID_MAP = {
    0: "O",
    1: "B-NOM_ASSURE",   # PER_B
    2: "I-NOM_ASSURE",   # PER_I
    3: "O",              # LOC_B → pas d'ADRESSE ici (trop générique)
    4: "O",              # LOC_I
    5: "O",              # ORG_B
    6: "O",              # ORG_I
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def remap_labels(labels_str: list[str], mapping: dict) -> list[int]:
    """Convertit une liste de labels string vers les IDs cibles via mapping."""
    remapped = [mapping.get(l, "O") for l in labels_str]
    return [LABEL2ID[l] for l in remapped]


def align_labels_with_tokens(tokenized, labels_ids: list[int]) -> list[int]:
    """
    Aligne les labels BIO avec les sous-tokens CamemBERT.
    - Premier sous-token d'un mot  → hérite du label original
    - Sous-tokens suivants          → héritent du label I- correspondant (ou O)
    - Tokens spéciaux [CLS]/[SEP]   → -100 (ignorés par la loss)
    """
    aligned = []
    word_ids = tokenized.word_ids()
    prev_word_id = None

    for wid in word_ids:
        if wid is None:
            aligned.append(-100)
        elif wid != prev_word_id:
            # Premier sous-token du mot
            lbl = labels_ids[wid] if wid < len(labels_ids) else LABEL2ID["O"]
            aligned.append(lbl)
        else:
            # Sous-token suivant : B- → I-, I- reste I-, O reste O
            prev_lbl = aligned[-1]
            if prev_lbl == -100:
                aligned.append(-100)
            else:
                lbl_name = ID2LABEL.get(prev_lbl, "O")
                if lbl_name.startswith("B-"):
                    aligned.append(LABEL2ID["I-" + lbl_name[2:]])
                else:
                    aligned.append(prev_lbl)
        prev_word_id = wid

    return aligned


def tokenize_and_align(example, tokenizer, mapping: dict):
    tokenized = tokenizer(
        example["tokens"],
        truncation=True,
        max_length=MAX_LENGTH,
        is_split_into_words=True,
        padding="max_length",
    )
    label_ids = remap_labels(example["ner_tags"], mapping)
    tokenized["labels"] = align_labels_with_tokens(tokenized, label_ids)
    return tokenized


# ---------------------------------------------------------------------------
# Chargement et normalisation par source
# ---------------------------------------------------------------------------

def load_funsd(tokenizer) -> DatasetDict:
    print("[FUNSD] Chargement...")
    raw = load_dataset("nielsr/funsd", trust_remote_code=True)

    def normalize(examples):
        # FUNSD expose 'words' et 'ner_tags' (entiers) avec feature.names
        feature_names = raw["train"].features["ner_tags"].feature.names
        str_tags = [[feature_names[t] for t in seq] for seq in examples["ner_tags"]]
        return {"tokens": examples["words"], "ner_tags": str_tags}

    normalized = raw.map(normalize, batched=True, remove_columns=raw["train"].column_names)
    return normalized.map(
        lambda ex: tokenize_and_align(ex, tokenizer, FUNSD_MAP),
        remove_columns=["tokens", "ner_tags"],
    )


def load_mapa(tokenizer) -> DatasetDict:
    print("[MAPA] Chargement (sous-ensemble FR)...")
    raw = load_dataset("joelito/mapa", "default")

    # Filtrage français + colonne labels = coarse_grained
    def normalize(example):
        return {
            "tokens":   example["tokens"],
            "ner_tags": example["coarse_grained"],
        }

    keep_cols = ["tokens", "ner_tags"]
    filtered = DatasetDict({
        split: raw[split]
            .filter(lambda ex: ex["language"] == "fr")
            .map(normalize, remove_columns=raw[split].column_names)
        for split in raw.keys()
    })

    print(f"  FR train : {len(filtered['train'])} exemples")

    return filtered.map(
        lambda ex: tokenize_and_align(ex, tokenizer, MAPA_MAP),
        remove_columns=keep_cols,
    )


def load_finer(tokenizer) -> DatasetDict:
    print("[FiNER] Chargement...")
    raw = load_dataset("gtfintechlab/finer-ord-bio")

    def normalize(example):
        str_tags = [FINER_ID_MAP.get(t, "O") for t in example["tags"]]
        # Cast défensif — certains tokens peuvent être None ou non-string
        clean_tokens = [str(t) if t is not None else "[UNK]" for t in example["tokens"]]
        return {
            "tokens":   clean_tokens,
            "ner_tags": str_tags,
        }

    normalized = raw.map(normalize, remove_columns=["tags"])
    return normalized.map(
        lambda ex: tokenize_and_align(ex, tokenizer, {l: l for l in LABEL_LIST}),
        remove_columns=["tokens", "ner_tags"],
    )


# ---------------------------------------------------------------------------
# Fusion et split
# ---------------------------------------------------------------------------

def merge_and_split(*dataset_dicts: DatasetDict) -> DatasetDict:
    """
    Fusionne les splits train/validation/test de plusieurs DatasetDict.
    Les datasets sans validation sont splittés automatiquement (90/10).
    """
    trains, vals, tests = [], [], []

    for dd in dataset_dicts:
        if "train" in dd:
            trains.append(dd["train"])
        if "validation" in dd:
            vals.append(dd["validation"])
        elif "train" in dd:
            # Pas de validation explicite → on coupe 10% du train
            split = dd["train"].train_test_split(test_size=0.1, seed=42)
            trains[-1] = split["train"]   # remplace le train ajouté
            vals.append(split["test"])
        if "test" in dd:
            tests.append(dd["test"])

    from datasets import concatenate_datasets

    merged_train = concatenate_datasets(trains)
    merged_val   = concatenate_datasets(vals)   if vals  else merged_train.select([])
    merged_test  = concatenate_datasets(tests)  if tests else merged_train.select([])

    # Shuffle final
    merged_train = merged_train.shuffle(seed=42)

    return DatasetDict({
        "train":      merged_train,
        "validation": merged_val,
        "test":       merged_test,
    })


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Tokenizer : {MODEL_NAME}")
    tokenizer = CamembertTokenizerFast.from_pretrained(MODEL_NAME)

    # Chargement des 3 sources
    funsd = load_funsd(tokenizer)
    
    # raw_mapa = load_dataset("joelito/mapa", "default", trust_remote_code=False)
    # print("MAPA colonnes :", raw_mapa["train"].column_names)
    # print("MAPA exemple  :", raw_mapa["train"][0])
    mapa  = load_mapa(tokenizer)
    
    
    # raw_finer = load_dataset("nlpaueb/finer-ord")
    raw_finer = load_dataset("gtfintechlab/finer-ord-bio")
    print("FiNER colonnes :", raw_finer["train"].column_names)
    print("FiNER exemple  :", raw_finer["train"][0])
    print("FiNER features :", raw_finer["train"].features)
    finer = load_finer(tokenizer)

    # Fusion
    print("\n[MERGE] Fusion des 3 sources...")
    merged = merge_and_split(funsd, mapa, finer)

    print(f"\n  train      : {len(merged['train'])} exemples")
    print(f"  validation : {len(merged['validation'])} exemples")
    print(f"  test       : {len(merged['test'])} exemples")

    # Sauvegarde
    out = OUTPUT_DIR / "ner_sg_dataset"
    merged.save_to_disk(str(out))
    print(f"\n[OK] Dataset sauvegardé → {out}")

    # Sauvegarde metadata label map
    meta = {"label2id": LABEL2ID, "id2label": ID2LABEL, "label_list": LABEL_LIST}
    with open(OUTPUT_DIR / "label_map.json", "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"[OK] label_map.json sauvegardé → {OUTPUT_DIR / 'label_map.json'}")


if __name__ == "__main__":
    main()
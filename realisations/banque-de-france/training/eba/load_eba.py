"""
load_eba.py - Extraction et harmonisation des donnees EBA Transparency Exercise
MVP Banque de France - module EBA (scoring de risque bancaire)

Responsabilite unique de ce script : extraire les 6 lignes utiles par banque x
periode (CET1 num/denom, Leverage num/denom, NPL num/denom) depuis les CSV bruts
tr_oth.csv et tr_cre.csv, sur les annees disponibles, et produire un pool
consolide au format long.

Ne calcule AUCUN ratio ici - c'est le role de compute_score.py.

Prerequis : training/eba/data/<annee>/tr_oth.csv et tr_cre.csv presents,
pour chaque annee listee dans YEARS.
"""

from pathlib import Path
import pandas as pd

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent / "data"
YEARS = [2023, 2024, 2025]

OUTPUT_DIR = DATA_DIR / "interim"
OUTPUT_FILE = OUTPUT_DIR / "consolidated_pool.csv"

FRENCH_BANKS = {
    "R0MUWSFPU8MPRO8K5P83": "BNP Paribas",
    "FR9695005MSX1OYEMGDF": "Groupe BPCE",
    "FR969500TJ5KRTCJQWXH": "Groupe Credit Agricole",
    "9695000CG7B84NLR5984": "Confederation Nationale du Credit Mutuel",
    "96950066U5XAAIRCPA78": "La Banque Postale",
    "O2RNE8IBXP4R0TD8PU41": "Societe generale S.A.",
}

# Filtres (Sheet, sous-chaine a inclure, sous-chaine a exclure) par metrique.
# IMPORTANT : ces sous-chaines ont ete validees sur l'annee 2025 pendant
# l'exploration (cf. training/eba/exploration/exploration_eba.ipynb).
# Le script imprime un avertissement si 0 ou plusieurs labels matchent -
# a verifier avant de faire confiance au pool en sortie.
LABEL_FILTERS_OTH = {
    "cet1_numerator": ("Capital", r"^COMMON EQUITY TIER 1 CAPITAL \(FULLY LOADED\)$", []),
    "cet1_denominator": ("Capital", r"^TOTAL RISK EXPOSURE AMOUNT$", []),
    "leverage_numerator": ("Leverage", r"^TIER 1 CAPITAL - FULLY PHASED-IN DEFINITION$", []),
    "leverage_denominator": ("Leverage", "TOTAL LEVERAGE", ["TRANSITIONAL"]),
}

# Dimensions "total, pas de ventilation" pour la feuille NPE de tr_cre.csv
NPE_TOTAL_DIMS = {"Portfolio": 0, "Exposure": 0, "Status": 0, "NACE_codes": 0}

NPL_LABEL_PATTERN = r"Gross carrying amount on Loans and advances \(including at amortised cost"


# ------------------------------------------------------------------
# Chargement brut
# ------------------------------------------------------------------

def _load_csv(year: int, filename: str) -> pd.DataFrame:
    path = DATA_DIR / str(year) / filename
    df = pd.read_csv(
        path,
        dtype={"LEI_Code": str, "Item": str, "Period": str},
        low_memory=False,
    )
    df["source_year"] = year
    return df


# ------------------------------------------------------------------
# Extraction tr_oth.csv (CET1, Leverage)
# ------------------------------------------------------------------

def _extract_oth_metrics(year: int) -> pd.DataFrame:
    """Extrait CET1 num/denom et Leverage num/denom depuis tr_oth.csv."""
    df = _load_csv(year, "tr_oth.csv")
    rows = []

    for metric, (sheet, include, exclude_list) in LABEL_FILTERS_OTH.items():
        label_upper = df["Label"].str.strip().str.upper()
        mask = (df["Sheet"] == sheet) & label_upper.str.contains(include, na=False, regex=True)
        for exclude in exclude_list:
            mask &= ~label_upper.str.contains(exclude, na=False)

        matched = df.loc[mask].copy()
        n_labels = matched["Label"].nunique()

        if n_labels == 0:
            print(f"[ALERTE] {year} / {metric} : aucun label trouve (Sheet={sheet}, include='{include}')")
            continue
        if n_labels > 1:
            print(f"[ATTENTION] {year} / {metric} : {n_labels} labels distincts matchent - a verifier :")
            print(matched["Label"].drop_duplicates().to_string(index=False))

        matched["metric"] = metric
        rows.append(matched[["LEI_Code", "Period", "metric", "Amount", "source_year"]])

    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
        columns=["LEI_Code", "Period", "metric", "Amount", "source_year"]
    )


# ------------------------------------------------------------------
# Extraction tr_cre.csv (NPL)
# ------------------------------------------------------------------

def _extract_npe_metrics(year: int) -> pd.DataFrame:
    """Extrait NPL numerateur (Perf_Status=2) et denominateur (Perf_Status=0) depuis tr_cre.csv."""
    df = _load_csv(year, "tr_cre.csv")

    mask_sheet = df["Sheet"] == "NPE"
    mask_label = df["Label"].str.contains(NPL_LABEL_PATTERN, case=False, na=False, regex=True)

    mask_dims = pd.Series(True, index=df.index)
    for col, val in NPE_TOTAL_DIMS.items():
        mask_dims &= df[col] == val

    base_mask = mask_sheet & mask_label & mask_dims

    numerator = df.loc[base_mask & (df["Perf_Status"] == 2)].copy()
    denominator = df.loc[base_mask & (df["Perf_Status"] == 0)].copy()

    for name, subset in [("npl_numerator", numerator), ("npl_denominator", denominator)]:
        if subset.empty:
            print(f"[ALERTE] {year} / {name} : aucune ligne trouvee")

    numerator["metric"] = "npl_numerator"
    denominator["metric"] = "npl_denominator"

    cols = ["LEI_Code", "Period", "metric", "Amount", "source_year"]
    return pd.concat([numerator[cols], denominator[cols]], ignore_index=True)


# ------------------------------------------------------------------
# Consolidation
# ------------------------------------------------------------------

def build_consolidated_pool() -> pd.DataFrame:
    frames = []
    for year in YEARS:
        print(f"\n=== Extraction {year} ===")
        frames.append(_extract_oth_metrics(year))
        frames.append(_extract_npe_metrics(year))

    pool = pd.concat(frames, ignore_index=True)

    # Deduplication : plusieurs exercices annuels se recouvrent sur certaines Period.
    # On garde la version la plus recente (source_year le plus eleve) en cas de doublon.
    pool = pool.sort_values("source_year", ascending=False)
    pool = pool.drop_duplicates(subset=["LEI_Code", "Period", "metric"], keep="first")

    pool["bank_name"] = pool["LEI_Code"].map(FRENCH_BANKS)  # NaN pour les banques non-francaises

    return pool.sort_values(["LEI_Code", "Period", "metric"]).reset_index(drop=True)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pool = build_consolidated_pool()
    pool.to_csv(OUTPUT_FILE, index=False)

    n_banks = pool["LEI_Code"].nunique()
    n_fr = pool.loc[pool["bank_name"].notna(), "LEI_Code"].nunique()
    print(f"\n--- Resume ---")
    print(f"Pool consolide : {len(pool)} lignes, {n_banks} banques dont {n_fr}/6 francaises")
    print(f"Ecrit dans : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
"""
compute_score.py - Calcul des ratios, moyenne UE et score composite
MVP Banque de France - module EBA (scoring de risque bancaire)

Lit le pool consolide produit par load_eba.py, calcule les 3 ratios
(CET1, Leverage, NPL) par banque x periode, la moyenne UE simple par ratio
x periode, les ecarts des 6 banques francaises vs cette moyenne, et le
score composite (moyenne simple des 3 ecarts).

Aucune ponderation differenciee : poids egal assume et documente dans la
sortie elle-meme (cle "methodology").

Ce n'est PAS un modele entraine, PAS un score reglementaire - un indicateur
comparatif transparent, a toujours presenter avec le detail des 3 ecarts
qui le composent, jamais seul.
"""

from pathlib import Path
import json
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
INPUT_FILE = DATA_DIR / "interim" / "consolidated_pool.csv"
OUTPUT_DIR = DATA_DIR / "processed"
OUTPUT_FILE = OUTPUT_DIR / "eba_scores.json"

# ratio -> (colonne numerateur, colonne denominateur)
RATIO_DEFINITIONS = {
    "cet1_ratio": ("cet1_numerator", "cet1_denominator"),
    "leverage_ratio": ("leverage_numerator", "leverage_denominator"),
    "npl_ratio": ("npl_numerator", "npl_denominator"),
}


def load_pool() -> pd.DataFrame:
    return pd.read_csv(INPUT_FILE, dtype={"LEI_Code": str, "Period": str})


def compute_ratios(pool: pd.DataFrame) -> pd.DataFrame:
    """Pivote le pool long -> une ligne par (LEI_Code, Period), une colonne par ratio."""
    wide = pool.pivot_table(
        index=["LEI_Code", "Period"],
        columns="metric",
        values="Amount",
        aggfunc="first",
        dropna=False,
    ).reset_index()
    wide.columns.name = None

    # bank_name est une fonction 1:1 de LEI_Code - rattache apres le pivot plutot
    # qu'inclus dans l'index (qui provoquerait un produit cartesien LEI_Code x
    # Period x bank_name au lieu des seules combinaisons reellement observees).
    bank_lookup = pool[["LEI_Code", "bank_name"]].drop_duplicates()
    wide = wide.merge(bank_lookup, on="LEI_Code", how="left")

    for ratio_name, (num_col, denom_col) in RATIO_DEFINITIONS.items():
        if num_col not in wide.columns or denom_col not in wide.columns:
            print(f"[ALERTE] colonnes manquantes pour {ratio_name} : {num_col} / {denom_col}")
            wide[ratio_name] = pd.NA
            continue
        wide[ratio_name] = wide[num_col] / wide[denom_col]

    return wide


def compute_eu_average(ratios: pd.DataFrame) -> pd.DataFrame:
    """Moyenne simple (non ponderee par la taille de bilan), par ratio et par periode,
    sur toutes les banques disponibles dans le fichier EBA (pas seulement les 6 francaises)."""
    ratio_cols = list(RATIO_DEFINITIONS.keys())
    eu_avg = ratios.groupby("Period")[ratio_cols].mean().reset_index()
    eu_avg = eu_avg.rename(columns={c: f"eu_avg_{c}" for c in ratio_cols})
    return eu_avg


def compute_french_scores(ratios: pd.DataFrame, eu_avg: pd.DataFrame) -> pd.DataFrame:
    french = ratios[ratios["bank_name"].notna()].copy()
    french = french.merge(eu_avg, on="Period", how="left")
    french = french[french["Period"] <= "202412"].copy()

    # Ecarts, toujours dans le sens "positif = plus solide que la moyenne UE"
    french["gap_cet1_ratio"] = french["cet1_ratio"] - french["eu_avg_cet1_ratio"]
    french["gap_leverage_ratio"] = french["leverage_ratio"] - french["eu_avg_leverage_ratio"]
    french["gap_npl_ratio"] = french["eu_avg_npl_ratio"] - french["npl_ratio"]  # inverse : NPL bas = bien

    gap_cols = ["gap_cet1_ratio", "gap_leverage_ratio", "gap_npl_ratio"]
    french["composite_score"] = french[gap_cols].mean(axis=1)

    return french


def build_output(french: pd.DataFrame) -> dict:
    records = []
    for _, row in french.sort_values(["bank_name", "Period"]).iterrows():
        records.append({
            "bank_name": row["bank_name"],
            "lei_code": row["LEI_Code"],
            "period": row["Period"],
            "ratios": {
                "cet1_ratio": row["cet1_ratio"],
                "leverage_ratio": row["leverage_ratio"],
                "npl_ratio": row["npl_ratio"],
            },
            "eu_average": {
                "cet1_ratio": row["eu_avg_cet1_ratio"],
                "leverage_ratio": row["eu_avg_leverage_ratio"],
                "npl_ratio": row["eu_avg_npl_ratio"],
            },
            "gaps_vs_eu_average": {
                "cet1_ratio": row["gap_cet1_ratio"],
                "leverage_ratio": row["gap_leverage_ratio"],
                "npl_ratio": row["gap_npl_ratio"],
            },
            "composite_score": row["composite_score"],
        })

    return {
        "methodology": {
            "description": (
                "Score composite = moyenne simple de 3 ecarts vs moyenne UE "
                "(CET1 fully loaded, levier fully phased-in, NPL), poids egal assume, "
                "aucune ponderation actuarielle."
            ),
            "eu_average_definition": (
                "Moyenne arithmetique simple sur toutes les banques disponibles du fichier EBA "
                "(~119 banques), non ponderee par la taille de bilan."
            ),
            "coverage_note": (
                "Couverture jusqu'a 202412 : periode la plus complete et homogene disponible "
                "dans le jeu de donnees EBA."
            ),
            "unit": "points de pourcentage d'ecart",
            "not_a_regulatory_score": True,
            "not_a_trained_model": True,
        },
        "records": records,
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pool = load_pool()
    ratios = compute_ratios(pool)
    eu_avg = compute_eu_average(ratios)
    french = compute_french_scores(ratios, eu_avg)

    # import pandas as pd
    # pd.set_option('display.max_rows', 100)
    # print('-')

    # # Ratios bruts des banques francaises (pas les ecarts)
    # print(french[["bank_name", "Period", "cet1_ratio", "leverage_ratio", "npl_ratio"]].to_string(index=False))

    # # Moyenne UE, meme periode
    # print(eu_avg.to_string(index=False))

    output = build_output(french)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=float)

    print(f"\n{len(french)} lignes (banque x periode) ecrites dans {OUTPUT_FILE}")
    print(french[["bank_name", "Period", "composite_score"]].to_string(index=False))


if __name__ == "__main__":
    main()
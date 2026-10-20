import pandas as pd

from pipeline.config import DATE_REFORME, DPE_SCHEMA

COLS_DATE = ["date_etablissement_dpe", "date_reception_dpe"]
COLS_FLOAT = [
    "version_dpe", "conso_5_usages_par_m2_ep", "surface_habitable_logement",
    "coordonnee_cartographique_x_ban", "coordonnee_cartographique_y_ban",
]
COLS_INT = ["annee_construction", "numero_etage_appartement"]


def transformer_dpe(df):
    """Typage, arrondissement et flags métier. Une ligne en entrée = une ligne en sortie."""
    df = df.copy()
    for col in COLS_DATE:
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
    for col in COLS_FLOAT:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in COLS_INT:
        df[col] = pd.to_numeric(df[col], errors="coerce").round().astype("Int64")

    arrondissement = pd.to_numeric(df["code_insee_ban"], errors="coerce") - 75100
    df["arrondissement"] = arrondissement.where(arrondissement.between(1, 20)).astype("Int64")

    df["flag_chauffage_electrique"] = (
        df["type_energie_principale_chauffage"].str.lower().str.contains("lectric", na=False)
    )
    df["flag_post_reforme_2026"] = df["date_etablissement_dpe"] >= pd.Timestamp(DATE_REFORME, tz="UTC")

    for col in COLS_DATE:
        df[col] = df[col].dt.strftime("%Y-%m-%d")
    return df[[nom for nom, _ in DPE_SCHEMA]]

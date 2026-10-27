from collections import Counter

import pandas as pd

from pipeline.dpe_ademe.config import DATE_REFORME, GROUPES, SCHEMA

CHAMPS = [(nom, type_bq) for champs in GROUPES.values() for nom, type_bq in champs]
COLONNES_DATE = [nom for nom, type_bq in CHAMPS if type_bq == "DATE"]
COLONNES_FLOAT = [nom for nom, type_bq in CHAMPS if type_bq == "FLOAT64"]
COLONNES_INT = [nom for nom, type_bq in CHAMPS if type_bq == "INT64"]
FORMAT_DATE = "%Y-%m-%d"


def _illisibles(source, converti):
    """Valeurs présentes dans la source et devenues nulles à la conversion."""
    return int((source.notna() & converti.isna()).sum())


def transformer(df):
    """Typage et colonnes calculées ; une ligne en entrée = une ligne en sortie, aucune ligne écartée.
    df : une page lue en texte (dtype=str). Retourne (df typé, dans l'ordre de SCHEMA ; illisibles par colonne)."""
    df = df.copy()
    illisibles = Counter()

    for col in COLONNES_DATE:
        converti = pd.to_datetime(df[col].str.slice(0, 10), format=FORMAT_DATE, errors="coerce")
        illisibles[col] += _illisibles(df[col], converti)
        df[col] = converti
    for col in COLONNES_FLOAT:
        converti = pd.to_numeric(df[col], errors="coerce")
        illisibles[col] += _illisibles(df[col], converti)
        df[col] = converti
    for col in COLONNES_INT:
        converti = pd.to_numeric(df[col], errors="coerce").round().astype("Int64")
        illisibles[col] += _illisibles(df[col], converti)
        df[col] = converti

    # Paris : le code INSEE 75101 est le 1er arrondissement ; tout code hors 75101 à 75120 donne NULL
    arrondissement = pd.to_numeric(df["code_insee_ban"], errors="coerce") - 75100
    df["arrondissement"] = arrondissement.where(arrondissement.between(1, 20)).astype("Int64")

    df["flag_chauffage_electrique"] = (
        df["type_energie_principale_chauffage"].str.lower().str.contains("lectric", na=False)
    )
    df["flag_post_reforme_2026"] = df["date_etablissement_dpe"] >= pd.Timestamp(DATE_REFORME)

    for col in COLONNES_DATE:
        df[col] = df[col].dt.strftime(FORMAT_DATE)
    return df[[nom for nom, _ in SCHEMA]], illisibles

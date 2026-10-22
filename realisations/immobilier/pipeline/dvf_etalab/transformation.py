import polars as pl

from pipeline.dvf_etalab.config import (
    COLONNE_FICHIER, COLONNE_LIVRAISON, COLONNES, DOSSIER_DVF, FORMAT_DATE, TABLE_DVF,
)

TYPES = {"int": pl.Int64, "float": pl.Float64}


def _typer(nom, type_):
    colonne = pl.col(nom)
    if type_ == "str":
        return colonne
    if type_ == "date":
        return colonne.str.to_date(FORMAT_DATE, strict=True)
    return colonne.cast(TYPES[type_], strict=True)


def _lire(chemin, etiquette, livraison):
    """Un fichier filtré : lu en texte, colonnes contrôlées, puis typé (strict) avec les colonnes ajoutées."""
    df = pl.read_csv(chemin, infer_schema_length=0)
    attendues = [nom for nom, _ in COLONNES]
    if df.columns != attendues:
        raise ValueError(
            f"{chemin.name} : colonnes ou ordre différents de ceux attendus "
            f"(manquantes : {sorted(set(attendues) - set(df.columns))}, en trop : {sorted(set(df.columns) - set(attendues))})"
        )
    return df.select(
        pl.lit(livraison).alias(COLONNE_LIVRAISON),
        *[_typer(nom, type_) for nom, type_ in COLONNES],
        pl.lit(etiquette).alias(COLONNE_FICHIER),
    )


def construire_parquet(livraison, departement, resultats):
    """Fusionne les fichiers filtrés (typage strict, doublons conservés), contrôle et écrit le Parquet de chargement.
    resultats : sortie de telechargement.preparer. Retourne (chemin du Parquet, statistiques)."""
    df = pl.concat([_lire(r["chemin"], etiquette, livraison) for etiquette, r in resultats.items()])

    attendu = sum(r["lignes"] for r in resultats.values())
    if len(df) != attendu:
        raise ValueError(f"{len(df)} lignes après fusion au lieu de {attendu}")
    departements = df["code_departement"].unique().to_list()
    if departements != [departement]:
        raise ValueError(f"code_departement inattendu : {departements} (attendu : {departement})")
    if df["id_mutation"].null_count() or df["date_mutation"].null_count():
        raise ValueError("id_mutation ou date_mutation vide")

    cible = DOSSIER_DVF / livraison / departement / f"{TABLE_DVF}.parquet"
    temporaire = cible.with_suffix(".parquet.tmp")
    df.write_parquet(temporaire)
    temporaire.replace(cible)
    stats = {
        "lignes": len(df), "colonnes": df.width,
        "date_min": df["date_mutation"].min(), "date_max": df["date_mutation"].max(),
    }
    return cible, stats

import polars as pl

from pipeline.bdnb.config import (
    ARRETE_2021, COLONNES_ARRETE_2012, DOSSIER_CHARGEMENT, DOSSIER_PARQUET, FORMAT_DATE,
    METHODE_DPE, SUFFIXE_TYPE_DPE, SURFACE_MIN, TABLES,
)


def lire(source):
    return pl.scan_parquet(DOSSIER_PARQUET / f"{source}.parquet")


def selection_dpe():
    """DPE retenus : arrêté 2021, logement, méthode 3cl, surface > SURFACE_MIN, sans les colonnes de l'arrêté 2012."""
    return lire("dpe_logement").filter(
        (pl.col("arrete_2021") == ARRETE_2021)
        & pl.col("type_dpe").str.ends_with(SUFFIXE_TYPE_DPE)
        & pl.col("type_dpe").str.contains(METHODE_DPE, literal=True)
        & (pl.col("surface_habitable_logement") > SURFACE_MIN)
    ).drop(COLONNES_ARRETE_2012)


def convertir_dates(lf, colonnes):
    """Texte BDNB ('2026/09/13 ...') vers DATE ; strict : une date illisible arrête le chargement."""
    return lf.with_columns(
        [pl.col(c).str.slice(0, 10).str.to_date(FORMAT_DATE, strict=True) for c in colonnes]
    )


def selection(table):
    """Sélection d'une table cible (LazyFrame), selon les règles du cahier (section 4)."""
    config = TABLES[table]
    if table == "bdnb_dpe_logement":
        lf = selection_dpe()
    elif table == "bdnb_rel_dpe_batiment":
        retenus = selection_dpe().select("identifiant_dpe")
        lf = lire(config["source"]).join(retenus, on="identifiant_dpe", how="semi")
    else:
        lf = lire(config["source"])
    return convertir_dates(lf, config["dates"])


def ecrire_parquet(table):
    """Écrit la sélection dans un Parquet temporaire (écriture puis renommage) et retourne son chemin."""
    DOSSIER_CHARGEMENT.mkdir(parents=True, exist_ok=True)
    cible = DOSSIER_CHARGEMENT / f"{table}.parquet"
    temporaire = DOSSIER_CHARGEMENT / f"{table}.parquet.tmp"
    selection(table).sink_parquet(temporaire)
    temporaire.replace(cible)
    return cible

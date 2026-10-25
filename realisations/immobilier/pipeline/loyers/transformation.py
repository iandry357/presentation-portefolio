import json
import logging

import polars as pl

from pipeline.loyers.config import (
    COLONNES, COLONNES_QUARTIERS, COLONNES_REFERENCE, DOSSIER_LOYERS, EPOQUES, FICHIER_QUARTIERS, FICHIER_REFERENCE,
    LIGNES_PAR_ANNEE, MEUBLE, NB_QUARTIERS, PIECES, RATIO_MAJORE, RATIO_MINORE, TOLERANCE_RATIO, VILLE,
)

logger = logging.getLogger(__name__)

TYPES = {"int": pl.Int64, "float": pl.Float64}
CLE = ["annee", "id_quartier", "piece", "epoque", "meuble_txt"]


def _typer(nom, type_):
    colonne = pl.col(nom)
    return colonne if type_ == "str" else colonne.cast(TYPES[type_], strict=True)


def _lire(chemin):
    """Le CSV lu en texte, colonnes contrôlées, puis typé (strict)."""
    df = pl.read_csv(chemin, separator=";", infer_schema_length=0)
    attendues = [nom for nom, _ in COLONNES]
    if df.columns != attendues:
        raise ValueError(
            f"{chemin.name} : colonnes ou ordre différents de ceux attendus "
            f"(manquantes : {sorted(set(attendues) - set(df.columns))}, en trop : {sorted(set(df.columns) - set(attendues))})"
        )
    return df.select(*[_typer(nom, type_) for nom, type_ in COLONNES])


def _controler(df):
    """Contrôles d'intégrité du jeu ; arrêt au premier écart."""
    nuls = {c: df[c].null_count() for c in df.columns if df[c].null_count()}
    if nuls:
        raise ValueError(f"valeurs vides : {nuls}")
    if df["ville"].unique().to_list() != [VILLE]:
        raise ValueError(f"ville : {df['ville'].unique().to_list()} au lieu de {VILLE}")
    for colonne, attendu in (("piece", PIECES), ("epoque", EPOQUES), ("meuble_txt", list(MEUBLE))):
        valeurs = sorted(df[colonne].unique().to_list())
        if valeurs != sorted(attendu):
            raise ValueError(f"{colonne} : {valeurs} au lieu de {sorted(attendu)}")
    if df["id_quartier"].n_unique() != NB_QUARTIERS:
        raise ValueError(f"{df['id_quartier'].n_unique()} quartiers au lieu de {NB_QUARTIERS}")
    incompletes = df.group_by("annee").agg(pl.len().alias("lignes")).filter(pl.col("lignes") != LIGNES_PAR_ANNEE)
    if incompletes.height:
        raise ValueError(f"années incomplètes ({LIGNES_PAR_ANNEE} lignes attendues) : {incompletes.rows()}")
    if df.select(CLE).is_duplicated().any():
        raise ValueError(f"doublons sur la clé {CLE}")
    ordre = df.filter(~((pl.col("min") < pl.col("ref")) & (pl.col("ref") < pl.col("max"))))
    ecarts = df.filter(
        ((pl.col("max") / pl.col("ref") - RATIO_MAJORE).abs() > TOLERANCE_RATIO)
        | ((pl.col("min") / pl.col("ref") - RATIO_MINORE).abs() > TOLERANCE_RATIO)
    )
    if ordre.height or ecarts.height:
        raise ValueError(f"loyers incohérents : {ordre.height} lignes hors ordre minoré < référence < majoré, {ecarts.height} hors ratios")


def _reference(df):
    return df.select(
        *[pl.col(source).alias(cible) for source, cible in COLONNES_REFERENCE],
        pl.col("meuble_txt").replace_strict(MEUBLE, return_dtype=pl.Boolean).alias("meuble"),
    ).sort("annee", "id_quartier", "pieces", "epoque", "meuble")


def _quartiers(df):
    """Une ligne par quartier ; chaque attribut doit avoir une seule valeur par quartier, et la géométrie être un Polygon."""
    attributs = [c for c in COLONNES_QUARTIERS if c != "id_quartier"]
    variables = df.group_by("id_quartier").agg(*[pl.col(c).n_unique().alias(c) for c in attributs]).filter(
        pl.any_horizontal([pl.col(c) > 1 for c in attributs])
    )
    if variables.height:
        raise ValueError(f"attributs de quartier variables selon l'année ou la ligne : {variables.rows()[:5]}")
    quartiers = df.select(COLONNES_QUARTIERS).unique(subset="id_quartier").sort("id_quartier")
    for forme in quartiers["geo_shape"]:
        if json.loads(forme).get("type") != "Polygon":
            raise ValueError("géométrie de quartier qui n'est pas un Polygon")
    return quartiers


def _ecrire(table, nom):
    cible = DOSSIER_LOYERS / nom
    temporaire = cible.with_suffix(".parquet.tmp")
    table.write_parquet(temporaire)
    temporaire.replace(cible)
    return cible


def construire_parquet(resultat):
    """CSV typé et contrôlé, puis deux Parquet (référence, quartiers). resultat : sortie de telechargement.preparer.
    Retourne (chemin de la référence, chemin des quartiers, statistiques)."""
    df = _lire(resultat["chemin"])
    if len(df) != resultat["lignes"]:
        raise ValueError(f"{len(df)} lignes lues au lieu de {resultat['lignes']}")
    _controler(df)
    reference, quartiers = _reference(df), _quartiers(df)
    stats = {
        "lignes": len(reference), "quartiers": len(quartiers),
        "annee_min": int(reference["annee"].min()), "annee_max": int(reference["annee"].max()),
    }
    return _ecrire(reference, FICHIER_REFERENCE), _ecrire(quartiers, FICHIER_QUARTIERS), stats

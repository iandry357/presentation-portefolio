"""Conversion des CSV BDNB (dept. 75) en Parquet, une fois, pour accélérer l'exploration.

Les types viennent des fichiers .csvt (format OGR). Les identifiants et les dates restent en texte.
Usage : python scripts\\convert_bdnb_parquet.py [--tables t1 t2 ...] [--force]
"""
import argparse
import re
import time
from pathlib import Path

import polars as pl

# --- Paramètres ---
DOSSIER_BDNB = Path(__file__).resolve().parent.parent / "pipeline" / "data" / "bdnb"
DOSSIER_CSV = DOSSIER_BDNB / "bdnb_dep75_csv" / "csv"
DOSSIER_PARQUET = DOSSIER_BDNB / "parquet"
SEPARATEUR = ";"

TABLES = [
    "dpe_logement",
    "rel_batiment_groupe_dpe_logement",
    "batiment_groupe_dpe_representatif_logement",
    "rel_batiment_groupe_dvf_open",
    "batiment_groupe_dvf_open_representatif",
    "batiment_groupe_dvf_open_statistique",
    "batiment_groupe",
    "rel_batiment_groupe_adresse",
    "adresse",
    "proprietaire",
    "rel_batiment_groupe_proprietaire",
    "rel_batiment_groupe_proprietaire",
    "rel_batiment_groupe_parcelle",
]

# Types OGR convertis ; tout le reste (String, WKT, Date, DateTime) reste en texte.
TYPES_POLARS = {
    "integer": pl.Int64,
    "integer64": pl.Int64,
    "real": pl.Float64,
}


def lire_types(table):
    ligne = (DOSSIER_CSV / f"{table}.csvt").read_text(encoding="utf-8").strip()
    morceaux = re.findall(r"[^,()]+(?:\([^)]*\))?", ligne)
    return [m.split("(")[0].strip().lower() for m in morceaux]


def convertir(table, force):
    source = DOSSIER_CSV / f"{table}.csv"
    cible = DOSSIER_PARQUET / f"{table}.parquet"
    temporaire = DOSSIER_PARQUET / f"{table}.parquet.tmp"

    if cible.exists() and not force:
        print(f"{table}: déjà converti (--force pour refaire)")
        return

    debut = time.time()
    lf = pl.scan_csv(source, separator=SEPARATEUR, infer_schema_length=0)
    colonnes = lf.collect_schema().names()
    types = lire_types(table)
    if len(types) != len(colonnes):
        raise ValueError(f"{table}: {len(colonnes)} colonnes dans le CSV, {len(types)} dans le .csvt")

    casts = []
    for nom, type_ogr in zip(colonnes, types):
        dtype = TYPES_POLARS.get(type_ogr)
        casts.append(pl.col(nom).cast(dtype) if dtype else pl.col(nom))

    # Écriture dans un fichier temporaire : un arrêt en cours de route ne laisse pas de Parquet incomplet.
    lf.select(casts).sink_parquet(temporaire)
    temporaire.replace(cible)

    nb_csv = lf.select(pl.len()).collect().item()
    nb_parquet = pl.scan_parquet(cible).select(pl.len()).collect().item()
    statut = "OK" if nb_csv == nb_parquet else "ECART"
    print(
        f"{table}: {nb_csv} lignes CSV, {nb_parquet} lignes Parquet [{statut}] | "
        f"{source.stat().st_size / 1e6:.0f} Mo -> {cible.stat().st_size / 1e6:.0f} Mo | "
        f"{time.time() - debut:.0f} s"
    )


def main():
    parser = argparse.ArgumentParser(description="Conversion CSV BDNB vers Parquet")
    parser.add_argument("--tables", nargs="*", default=TABLES, help="tables à convertir (défaut : liste du script)")
    parser.add_argument("--force", action="store_true", help="refaire les tables déjà converties")
    args = parser.parse_args()

    DOSSIER_PARQUET.mkdir(parents=True, exist_ok=True)
    for table in args.tables:
        convertir(table, args.force)


if __name__ == "__main__":
    main()

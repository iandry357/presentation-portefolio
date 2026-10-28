"""Inventaire de la BDNB (dept. 75) : toutes les tables du jeu et toutes leurs colonnes, avec remplissage, unité et définition.
Lecture seule ; aucune valeur n'est affichée (comptages seulement). Depuis realisations/immobilier, venv-explore activé :
    python -m scripts.explore_bdnb_inventaire [--tables MOTIF ...]
Écrit dans pipeline/data/bdnb/rapports : inventaire_tables.txt et inventaire_colonnes.txt (une ligne par table ou colonne, séparées par « | »).
Lit les Parquet s'ils existent, sinon les CSV (types non lus).
"""
import argparse
import re
from functools import lru_cache
from pathlib import Path

import polars as pl

# --- Paramètres ---
DOSSIER_BDNB = Path(__file__).resolve().parent.parent / "pipeline" / "data" / "bdnb"
DOSSIER_CSV = DOSSIER_BDNB / "bdnb_dep75_csv" / "csv"
DOSSIER_PARQUET = DOSSIER_BDNB / "parquet"
DOSSIER_RAPPORTS = DOSSIER_BDNB / "rapports"
LONGUEUR_DEFINITION = 200
CLES = ["batiment_groupe_id", "parcelle_id", "cle_interop_adr", "identifiant_dpe"]   # clés cherchées, dans cet ordre
SENSIBLE = re.compile(r"denomination|siren|siret|l_nom|nom_pdl|nom_copro|nom_demandeur|prenom|numero_immat", re.IGNORECASE)
PROPRIETAIRES = re.compile(r"proprietaire")   # tables de personnes : colonnes listées, jamais comptées


def ouvrir(stem):
    """LazyFrame de la table (Parquet, sinon CSV en texte), None si elle n'existe pas."""
    parquet = DOSSIER_PARQUET / f"{stem}.parquet"
    if parquet.exists():
        return pl.scan_parquet(parquet), "Parquet"
    csv = DOSSIER_CSV / f"{stem}.csv"
    if csv.exists():
        return pl.scan_csv(csv, separator=";", infer_schema_length=0), "CSV"
    return None, None


@lru_cache(maxsize=1)
def definitions():
    """(table, colonne) -> (description, unité) d'après metadonnees_colonne.csv."""
    chemin = DOSSIER_CSV / "metadonnees_colonne.csv"
    if not chemin.exists():
        return {}
    dico = pl.read_csv(chemin, separator=";", infer_schema_length=0)
    return {(r["nom_table"], r["nom_colonne"]): (r["description"] or "", r["unite"] or "") for r in dico.iter_rows(named=True)}


def nettoyer(texte):
    return " ".join(str(texte).split())


def main():
    parser = argparse.ArgumentParser(description="Inventaire des tables et colonnes de la BDNB (dept. 75)")
    parser.add_argument("--tables", nargs="*", default=[], help="motifs de noms de tables (défaut : toutes)")
    args = parser.parse_args()

    stems = sorted({p.stem for p in DOSSIER_PARQUET.glob("*.parquet")} | {c.stem for c in DOSSIER_CSV.glob("*.csv")})
    stems = [s for s in stems if s != "metadonnees_colonne" and (not args.tables or any(m in s for m in args.tables))]
    dico = definitions()
    if not dico:
        print("ATTENTION : metadonnees_colonne.csv introuvable, aucune définition ne sera écrite")

    tables = ["table | lignes | colonnes | cle | une_ligne_par_cle | source"]
    colonnes = ["table | colonne | type | non_nuls_pct | distinctes | unite | sensible | definition"]
    for stem in stems:
        lf, source = ouvrir(stem)
        schema = lf.collect_schema()
        proprietaires = bool(PROPRIETAIRES.search(stem))
        n = lf.select(pl.len()).collect().item()
        comptes = n > 0 and not proprietaires
        nuls = lf.select(pl.all().null_count()).collect().to_dicts()[0] if comptes else {}
        uniques = lf.select(pl.all().n_unique()).collect().to_dicts()[0] if comptes else {}

        cle = next((c for c in CLES if c in schema), None)
        grain = "—" if cle is None or not comptes else ("oui" if uniques[cle] == n else "non")
        tables.append(f"{stem} | {n if not proprietaires else 'non compté'} | {len(schema)} | {cle or '—'} | {grain} | {source}")
        print(tables[-1])

        for nom, type_ in schema.items():
            description, unite = dico.get((stem, nom), ("", ""))
            remplissage = round((n - nuls[nom]) / n * 100, 1) if comptes else "—"
            distinctes = uniques[nom] if comptes else "—"
            sensible = "oui" if SENSIBLE.search(nom) or proprietaires else ""
            colonnes.append(
                f"{stem} | {nom} | {type_} | {remplissage} | {distinctes} | {unite} | {sensible} | "
                f"{nettoyer(description)[:LONGUEUR_DEFINITION]}"
            )

    DOSSIER_RAPPORTS.mkdir(parents=True, exist_ok=True)
    (DOSSIER_RAPPORTS / "inventaire_tables.txt").write_text("\n".join(tables), encoding="utf-8")
    (DOSSIER_RAPPORTS / "inventaire_colonnes.txt").write_text("\n".join(colonnes), encoding="utf-8")
    print(f"\n{len(stems)} tables, {len(colonnes) - 1} colonnes. Rapports : {DOSSIER_RAPPORTS}")


if __name__ == "__main__":
    main()

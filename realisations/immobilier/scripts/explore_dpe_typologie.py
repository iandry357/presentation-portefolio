"""Exploration de la typologie des logements (T1 à T7) de l'API ADEME, pour un axe « pièces » côté DPE.
Aucune écriture BigQuery. Les DPE avec typologie sont rapprochés des DPE de la BDNB (Parquet local).

Usage : python scripts\\explore_dpe_typologie.py --bloc 0|1|...|5|all [--rapport] [--lignes 20] [--force]
Terminal : les --lignes premières lignes de chaque tableau. Fichier (--rapport) : la totalité.
Bloc 1 : télécharge l'extraction du jour si elle n'existe pas (--force : la refaire).
"""
import argparse
import json
import time
from datetime import date, datetime
from pathlib import Path

import polars as pl
import requests

# --- Paramètres ---
DOSSIER_BDNB = Path(__file__).resolve().parent.parent / "pipeline" / "data" / "bdnb"
DOSSIER_PARQUET = DOSSIER_BDNB / "parquet"
DOSSIER_RAPPORTS = DOSSIER_BDNB / "rapports"
DOSSIER_TYPOLOGIE = DOSSIER_BDNB / "typologie_dpe"
LIGNES_TERMINAL = 20

API = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant"
CHAMP_DEPARTEMENT = "code_departement_ban"
DEPARTEMENT = "75"
CHAMPS = ["numero_dpe", "typologie_logement", "date_etablissement_dpe"]
TAILLE_PAGE = 10000
TIMEOUT = 120
MAX_TENTATIVES = 3

# Sélection DPE de la BDNB (pipeline/bdnb/config.py)
ARRETE_2021 = 1
SUFFIXE_TYPE_DPE = "logement"
METHODE_DPE = "3cl"
SURFACE_MIN = 0

# Critère de poursuite (reformulé) : part des DPE de type logement avec typologie retrouvés dans la sélection BDNB
SEUIL_RETROUVES = 0.90

# Fenêtre de l'analyse (mêmes dates que les ventes) et utilisabilité des cellules
DATE_DEBUT_FENETRE = "2025-01-01"
DATE_FIN_FENETRE = "2026-06-30"
SEUIL_CELLULE = 5                # une cellule de moins de 5 DPE serait masquée si l'accès est verrouillé
SEUIL_DPE_EN_CELLULES = 0.80     # part des DPE avec typologie à retrouver dans des cellules utilisables (arrondissement × pièces)
TRANCHES_SURFACE = [25, 40, 60, 80, 120]   # bornes en m², borne basse incluse
LIBELLES_SURFACE = ["1 moins de 25", "2 de 25 à 40", "3 de 40 à 60", "4 de 60 à 80", "5 de 80 à 120", "6 120 et plus"]



class Sortie:
    """Affiche une sélection dans le terminal et garde la totalité pour le fichier."""

    def __init__(self, lignes):
        self.lignes = lignes
        self.contenu = []

    def titre(self, texte):
        print(f"\n== {texte}")
        self.contenu.append(f"\n== {texte}")

    def texte(self, texte):
        print(texte)
        self.contenu.append(texte)

    def tableau(self, df):
        with pl.Config(tbl_rows=self.lignes, tbl_cols=-1, fmt_str_lengths=80):
            print(df)
        with pl.Config(tbl_rows=-1, tbl_cols=-1, fmt_str_lengths=200):
            self.contenu.append(str(df))

    def ecrire(self, nom_bloc):
        DOSSIER_RAPPORTS.mkdir(parents=True, exist_ok=True)
        horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
        chemin = DOSSIER_RAPPORTS / f"{horodatage}_bloc{nom_bloc}.txt"
        chemin.write_text("\n".join(self.contenu), encoding="utf-8")
        print(f"\nRapport écrit : {chemin}")


# --- Outils communs ---
def _get(url, params=None):
    for tentative in range(1, MAX_TENTATIVES + 1):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if tentative == MAX_TENTATIVES:
                raise
            print(f"Tentative {tentative}/{MAX_TENTATIVES} échouée : {e}")
            time.sleep(5 * tentative)


def repartition(df, *colonnes):
    return (
        df.group_by(list(colonnes)).agg(pl.len().alias("lignes"))
        .with_columns((pl.col("lignes") / pl.col("lignes").sum() * 100).round(1).alias("pct"))
        .sort(*colonnes)
    )


def dernier_dossier():
    """Extraction ADEME la plus récente (dossier daté contenant typologie.csv)."""
    dossiers = sorted(p for p in DOSSIER_TYPOLOGIE.glob("*") if (p / "typologie.csv").exists())
    if not dossiers:
        raise SystemExit("Aucune extraction : lancer --bloc 1")
    return dossiers[-1]
def charger_dpe():
    """DPE de la BDNB avec l'indicateur « retenu » (règles de sélection de pipeline/bdnb/config.py)."""
    return pl.scan_parquet(DOSSIER_PARQUET / "dpe_logement.parquet").select(
        pl.col("identifiant_dpe").str.strip_chars().str.to_uppercase(),
        pl.col("arrete_2021").cast(pl.Int64, strict=False),
        "type_dpe",
        pl.col("surface_habitable_logement").cast(pl.Float64, strict=False).alias("surface"),
    ).with_columns(
        (
            (pl.col("arrete_2021") == ARRETE_2021)
            & pl.col("type_dpe").str.ends_with(SUFFIXE_TYPE_DPE)
            & pl.col("type_dpe").str.contains(METHODE_DPE, literal=True)
            & (pl.col("surface") > SURFACE_MIN)
        ).fill_null(False).alias("retenu"),
        pl.lit(True).alias("dans_bdnb"),
    )


# --- Blocs ---
def bloc_0(sortie):
    """Typologie dans l'API ADEME : agrégation seulement, rien n'est téléchargé."""
    sortie.titre("Bloc 0 - Typologie dans l'API ADEME (agrégation, rien n'est téléchargé)")
    reponse = _get(f"{API}/values_agg", {
        "field": "typologie_logement", "qs": f"{CHAMP_DEPARTEMENT}:{DEPARTEMENT}", "agg_size": 25, "size": 0,
    })
    total = reponse.get("total")
    classes = [{"typologie": a.get("value"), "nb_dpe": a.get("total")} for a in reponse.get("aggs", [])]
    if total is None or not classes:
        sortie.texte(f"Réponse inattendue de l'API (clés : {sorted(reponse)}) :")
        sortie.texte(json.dumps(reponse)[:1500])
        return
    renseignes = sum(c["nb_dpe"] for c in classes)
    sortie.tableau(pl.DataFrame(classes).sort("typologie"))
    sortie.texte(f"DPE du département {DEPARTEMENT} : {total} ; avec typologie : {renseignes} ({renseignes / total * 100:.1f} %)")


def bloc_1(sortie, force):
    """Téléchargement des seuls DPE avec typologie dans typologie_dpe/<date du jour>/typologie.csv."""
    dossier = DOSSIER_TYPOLOGIE / datetime.now().strftime("%Y-%m-%d")
    cible = dossier / "typologie.csv"
    sortie.titre(f"Bloc 1 - Téléchargement dans {dossier}")
    if cible.exists() and not force:
        sortie.texte("Extraction du jour déjà présente (--force pour la refaire)")
        return

    qs = f"{CHAMP_DEPARTEMENT}:{DEPARTEMENT} AND _exists_:typologie_logement"
    reponse = _get(f"{API}/lines", {"size": TAILLE_PAGE, "select": ",".join(CHAMPS), "qs": qs})
    total = reponse["total"]
    lignes = []
    while True:
        lignes.extend({c: r.get(c) for c in CHAMPS} for r in reponse["results"])
        print(f"{len(lignes)} / {total}")
        if not reponse.get("next") or not reponse["results"]:
            break
        reponse = _get(reponse["next"])
    if len(lignes) != total:
        raise ValueError(f"{len(lignes)} lignes téléchargées pour {total} annoncées par l'API")

    dossier.mkdir(parents=True, exist_ok=True)
    temporaire = cible.with_suffix(".csv.tmp")
    pl.DataFrame(lignes, schema={c: pl.String for c in CHAMPS}).write_csv(temporaire)
    temporaire.replace(cible)
    (dossier / "manifeste.json").write_text(json.dumps({
        "api": API, "qs": qs, "champs": CHAMPS, "lignes": len(lignes),
        "extrait_le": datetime.now().isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    sortie.texte(f"{len(lignes)} DPE avec typologie téléchargés dans {cible}")


def bloc_2(sortie):
    """Rapprochement des numéros ADEME avec les DPE de la BDNB : part retrouvée dans la sélection, motifs, année."""
    dossier = dernier_dossier()
    typologie = pl.read_csv(dossier / "typologie.csv", infer_schema_length=0).with_columns(
        pl.col("numero_dpe").str.strip_chars().str.to_uppercase()
    )
    sortie.titre(f"Bloc 2 - Extraction ADEME du {dossier.name}")
    sortie.texte(
        f"{len(typologie)} DPE avec typologie, {typologie['numero_dpe'].n_unique()} numéros distincts, "
        f"{typologie['numero_dpe'].null_count()} numéros vides"
    )

    dpe = charger_dpe().collect()
    rapproche = typologie.unique("numero_dpe").join(dpe, left_on="numero_dpe", right_on="identifiant_dpe", how="left")
    rapproche = rapproche.with_columns(
        pl.col("retenu").fill_null(False),
        pl.when(pl.col("retenu").fill_null(False)).then(pl.lit("0 dans la sélection BDNB"))
        .when(pl.col("dans_bdnb").is_null()).then(pl.lit("1 absent de la BDNB"))
        .when((pl.col("arrete_2021") != ARRETE_2021).fill_null(True)).then(pl.lit("2 arrêté 2012 (ou arrêté absent)"))
        .when((~pl.col("type_dpe").str.ends_with(SUFFIXE_TYPE_DPE)).fill_null(True)).then(pl.lit("3 type immeuble ou autre"))
        .when((~pl.col("type_dpe").str.contains(METHODE_DPE, literal=True)).fill_null(True))
        .then(pl.lit(f"4 méthode autre que {METHODE_DPE}"))
        .otherwise(pl.lit("5 surface nulle ou absente")).alias("motif"),
    )

    sortie.titre("Bloc 2 - DPE avec typologie : retrouvés ou non dans la sélection de la BDNB")
    sortie.tableau(repartition(rapproche, "motif"))

    sortie.titre("Bloc 2 - Taux de rapprochement par année d'établissement (date ADEME)")
    sortie.tableau(
        rapproche.group_by(pl.col("date_etablissement_dpe").str.slice(0, 4).alias("annee")).agg(
            pl.len().alias("dpe_avec_typologie"),
            pl.col("retenu").sum().alias("dans_la_selection"),
            (pl.col("retenu").mean() * 100).round(1).alias("pct_retrouves"),
        ).sort("annee")
    )

    sortie.titre("Bloc 2 - Typologie des DPE retrouvés dans la sélection")
    sortie.tableau(repartition(rapproche.filter(pl.col("retenu")), "typologie_logement"))

    hors_immeuble = rapproche.filter(~pl.col("motif").str.starts_with("3"))
    part = hors_immeuble["retenu"].mean()
    verdict = "OK" if part >= SEUIL_RETROUVES else "INSUFFISANT"
    sortie.titre("Bloc 2 - Critère de poursuite (DPE de type logement)")
    sortie.texte(
        f"{len(rapproche) - len(hors_immeuble)} DPE de type immeuble ou autre écartés du dénominateur ; "
        f"{part * 100:.1f} % des {len(hors_immeuble)} DPE restants sont dans la sélection BDNB "
        f"(seuil {SEUIL_RETROUVES * 100:.0f} %) : {verdict}"
    )


# --- Base d'analyse (blocs 3 à 5) ---
def lire_typologie():
    """DPE avec typologie extraits de l'ADEME (dernière extraction)."""
    return pl.read_csv(dernier_dossier() / "typologie.csv", infer_schema_length=0).select(
        pl.col("numero_dpe").str.strip_chars().str.to_uppercase().alias("identifiant_dpe"),
        pl.col("typologie_logement").alias("typologie"),
        pl.col("date_etablissement_dpe").alias("date_ademe"),
    ).unique("identifiant_dpe")


def construire_base():
    """DPE de la sélection BDNB avec arrondissement, tranche de surface, étiquette, pièces (typologie ADEME,
    nulle si absente) et indicateur de fenêtre. Un DPE relié à plusieurs adresses garde l'une d'elles."""
    extra = pl.scan_parquet(DOSSIER_PARQUET / "dpe_logement.parquet").select(
        pl.col("identifiant_dpe").str.strip_chars().str.to_uppercase(),
        pl.col("date_etablissement_dpe").str.slice(0, 10).str.to_date("%Y/%m/%d", strict=False).alias("date_dpe"),
        pl.col("classe_bilan_dpe").alias("etiquette"),
    )
    selection = charger_dpe().filter(pl.col("retenu")).join(extra, on="identifiant_dpe", how="left").collect()
    liens = pl.read_parquet(
        DOSSIER_PARQUET / "rel_batiment_groupe_dpe_logement.parquet", columns=["identifiant_dpe", "cle_interop_adr"]
    ).select(
        pl.col("identifiant_dpe").str.strip_chars().str.to_uppercase(),
        (pl.col("cle_interop_adr").str.slice(0, 5).cast(pl.Int64, strict=False) - 75100).alias("arrondissement"),
    ).filter(pl.col("arrondissement").is_between(1, 20)).unique("identifiant_dpe")
    debut, fin = date.fromisoformat(DATE_DEBUT_FENETRE), date.fromisoformat(DATE_FIN_FENETRE)
    return (
        selection.join(liens, on="identifiant_dpe", how="left")
        .join(lire_typologie().select("identifiant_dpe", "typologie"), on="identifiant_dpe", how="left")
        .with_columns(
            pl.col("typologie").str.extract(r"T(\d)", 1).cast(pl.Int64, strict=False).clip(upper_bound=5).alias("pieces"),
            pl.col("surface").cut(TRANCHES_SURFACE, labels=LIBELLES_SURFACE, left_closed=True)
            .cast(pl.String).alias("tranche_surface"),
            pl.col("date_dpe").is_between(debut, fin).alias("en_fenetre"),
        )
    )


def recouvrement(df, *colonnes):
    return df.group_by(list(colonnes)).agg(
        pl.len().alias("dpe"),
        pl.col("pieces").is_not_null().sum().alias("avec_typologie"),
    ).with_columns(
        (pl.col("avec_typologie") / pl.col("dpe") * 100).round(1).alias("recouvrement_pct")
    ).sort(*colonnes)


def comparer(df, dimension):
    """Répartition d'une dimension : DPE avec typologie contre ensemble des DPE, écart en points."""
    tous = repartition(df, dimension).rename({"lignes": "dpe", "pct": "pct_dpe"})
    avec = repartition(df.filter(pl.col("pieces").is_not_null()), dimension).rename(
        {"lignes": "dpe_typologie", "pct": "pct_typologie"}
    )
    return tous.join(avec, on=dimension, how="left").with_columns(
        (pl.col("pct_typologie") - pl.col("pct_dpe")).round(1).alias("ecart_points")
    ).sort(dimension)


def trimestre(colonne):
    return pl.format("{}-T{}", pl.col(colonne).dt.year(), pl.col(colonne).dt.quarter()).alias("trimestre")


def bloc_3(sortie):
    """Recouvrement de la typologie parmi les DPE de la sélection BDNB, sur la fenêtre de l'analyse."""
    base = construire_base()
    fenetre = base.filter(pl.col("en_fenetre"))
    sortie.titre(f"Bloc 3 - Recouvrement de la typologie (fenêtre {DATE_DEBUT_FENETRE} → {DATE_FIN_FENETRE})")
    sortie.tableau(pl.DataFrame([
        {"perimetre": "toute la sélection BDNB", "dpe": len(base), "avec_typologie": base["pieces"].is_not_null().sum()},
        {"perimetre": "fenêtre de l'analyse", "dpe": len(fenetre), "avec_typologie": fenetre["pieces"].is_not_null().sum()},
    ]).with_columns((pl.col("avec_typologie") / pl.col("dpe") * 100).round(1).alias("recouvrement_pct")))

    for dimension in ("arrondissement", "tranche_surface", "etiquette"):
        sortie.titre(f"Bloc 3 - Recouvrement par {dimension} (fenêtre)")
        sortie.tableau(recouvrement(fenetre, dimension))
    sortie.titre("Bloc 3 - Recouvrement par trimestre d'établissement (toute la sélection)")
    sortie.tableau(recouvrement(base.with_columns(trimestre("date_dpe")).drop_nulls("trimestre"), "trimestre"))

    sortie.titre("Bloc 3 - DPE avec typologie absents de la BDNB, par trimestre d'établissement (date ADEME)")
    typologie = lire_typologie().with_columns(
        pl.col("date_ademe").str.slice(0, 10).str.to_date("%Y-%m-%d", strict=False).alias("date_dpe")
    )
    presents = charger_dpe().select("identifiant_dpe", "dans_bdnb").collect()
    manquants = typologie.join(presents, on="identifiant_dpe", how="left")
    sortie.tableau(
        manquants.with_columns(trimestre("date_dpe")).drop_nulls("trimestre").group_by("trimestre").agg(
            pl.len().alias("dpe_avec_typologie"),
            pl.col("dans_bdnb").is_null().sum().alias("absents_de_la_bdnb"),
        ).with_columns(
            (pl.col("absents_de_la_bdnb") / pl.col("dpe_avec_typologie") * 100).round(1).alias("pct_absents")
        ).sort("trimestre")
    )


def bloc_4(sortie):
    """Représentativité : les DPE avec typologie ressemblent-ils à l'ensemble des DPE de la fenêtre ?"""
    base = construire_base().filter(pl.col("en_fenetre"))
    for dimension in ("arrondissement", "tranche_surface", "etiquette"):
        sortie.titre(f"Bloc 4 - {dimension} : DPE avec typologie contre ensemble des DPE (fenêtre)")
        sortie.tableau(comparer(base, dimension))
    sortie.titre("Bloc 4 - Surface (m²) par nombre de pièces, DPE avec typologie de la fenêtre")
    sortie.tableau(
        base.filter(pl.col("pieces").is_not_null()).group_by("pieces").agg(
            pl.len().alias("dpe"),
            pl.col("surface").quantile(0.25).alias("q25"),
            pl.col("surface").median().alias("mediane"),
            pl.col("surface").quantile(0.75).alias("q75"),
        ).sort("pieces")
    )


GRAINS = [
    ("arrondissement × pièces", ["arrondissement", "pieces"]),
    ("arrondissement × pièces × tranche de surface", ["arrondissement", "pieces", "tranche_surface"]),
    ("arrondissement × pièces × tranche × étiquette", ["arrondissement", "pieces", "tranche_surface", "etiquette"]),
    ("pièces × tranche de surface (Paris entier)", ["pieces", "tranche_surface"]),
]


def bloc_5(sortie):
    """Effectifs utilisables : cellules d'au moins SEUIL_CELLULE DPE avec typologie, pour plusieurs grains."""
    base = construire_base().filter(pl.col("en_fenetre") & pl.col("pieces").is_not_null())
    sortie.titre(f"Bloc 5 - Cellules utilisables (au moins {SEUIL_CELLULE} DPE avec typologie, fenêtre)")
    sortie.texte(f"{len(base)} DPE avec typologie dans la fenêtre")
    lignes = []
    for libelle, colonnes in GRAINS:
        valides = base.drop_nulls(colonnes)
        cellules = valides.group_by(colonnes).agg(pl.len().alias("n"))
        utilisables = cellules.filter(pl.col("n") >= SEUIL_CELLULE)
        dans_utilisables = int(utilisables["n"].sum() or 0)
        lignes.append({
            "grain": libelle,
            "cellules": len(cellules),
            "cellules_utilisables": len(utilisables),
            "pct_cellules": round(len(utilisables) / max(1, len(cellules)) * 100, 1),
            "dpe": len(valides),
            "dpe_en_cellules_utilisables": dans_utilisables,
            "pct_dpe": round(dans_utilisables / max(1, len(valides)) * 100, 1),
        })
    sortie.tableau(pl.DataFrame(lignes))

    part = lignes[0]["pct_dpe"] / 100
    verdict = "OK" if part >= SEUIL_DPE_EN_CELLULES else "INSUFFISANT"
    sortie.titre("Bloc 5 - Critère d'utilisabilité")
    sortie.texte(
        f"Grain « {lignes[0]['grain']} » : {part * 100:.1f} % des DPE avec typologie dans des cellules "
        f"d'au moins {SEUIL_CELLULE} DPE (seuil {SEUIL_DPE_EN_CELLULES * 100:.0f} %) : {verdict}"
    )

BLOCS = {0: bloc_0, 2: bloc_2, 3: bloc_3, 4: bloc_4, 5: bloc_5}


def main():
    parser = argparse.ArgumentParser(description="Exploration de la typologie des logements de l'API ADEME")
    parser.add_argument("--bloc", default="all", choices=["0", "1", "2", "3", "4", "5", "all"])
    parser.add_argument("--rapport", action="store_true", help="écrire la sortie complète dans pipeline/data/bdnb/rapports/")
    parser.add_argument("--lignes", type=int, default=LIGNES_TERMINAL, help="lignes affichées par tableau dans le terminal")
    parser.add_argument("--force", action="store_true", help="bloc 1 : refaire l'extraction du jour")
    args = parser.parse_args()

    for numero in range(6) if args.bloc == "all" else [int(args.bloc)]:
        sortie = Sortie(args.lignes)
        if numero == 1:
            bloc_1(sortie, args.force)
        else:
            BLOCS[numero](sortie)
        if args.rapport:
            sortie.ecrire(f"{numero}_typologie")


if __name__ == "__main__":
    main()

"""Exploration du prix au m² par nombre de pièces (vue « Analyse », source Ventes) : le prix médian monte avec le
nombre de pièces alors qu'il devrait baisser. On remonte la chaîne de l'aval vers la donnée brute et on recalcule à
chaque couche le même tableau (ventes, surface et prix médians par nombre de pièces).

Usage : python scripts\\explore_prix_pieces.py --couche api|cube|vues|table|parquet|diag|carrez|all [--api URL]
Couches : api (route /immobilier/bdnb/analyse, exige --api) · cube (agg_analyse_ventes) · vues (dvf_etalab_ventes_logement
          et dvf_etalab_ventes_batiment) · table (dvf_etalab, règle V1 reconstituée) · parquet (même calcul sur le
          Parquet local) · diag (dépendances, cohérence pièces/surface, arrondissements, bornes, test de correction) · carrez (Carrez des lots contre surface cadastrale)
Lecture seule. Lancé depuis realisations/immobilier, venv-explore activé. « all » finit par l'entonnoir entre couches.
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

import polars as pl
import requests
from google.cloud import bigquery

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # pipeline.*, lancé depuis realisations/immobilier
from pipeline.analyse.config import TABLE_VENTES  # noqa: E402
from pipeline.dvf_etalab.config import (  # noqa: E402
    BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH, TABLE_DVF, TYPE_LOCAL_COMMERCIAL, TYPES_LOGEMENT, VUE_VENTES,
    VUE_VENTES_BATIMENT,
)

# --- Paramètres ---
LIVRAISON = "2026-10"
DEPARTEMENT = "75"
DATE_DEBUT = "2025-01-01"        # fenêtre du cube (pipeline/analyse/config.py)
DATE_FIN = "2026-06-30"
PRIX_M2_MIN = 2000
PRIX_M2_MAX = 30000
PIECES_MAX = 6                   # « 6 et plus »
SEUIL_CELLULE = 5                # cellule de moins de N ventes non affichée (tableau par arrondissement)
M2_PAR_PIECE_MIN = 9             # cohérence : en dessous, surface trop petite pour le nombre de pièces
M2_PAR_PIECE_MAX = 60            # au-dessus, surface trop grande
NATURE_VENTE = "Vente"
TYPE_DEPENDANCE = "Dépendance"
NON_RENSEIGNE = "non renseigné"
CHEMIN_API = "/immobilier/bdnb/analyse"
TIMEOUT = 120
PARQUET = (Path(__file__).resolve().parent.parent / "pipeline" / "data" / "bdnb" / "dvf_etalab" / LIVRAISON
           / DEPARTEMENT / "dvf_etalab.parquet")
CARREZ = [f"lot{i}_surface_carrez" for i in range(1, 6)]
COLONNES_BRUT = [
    "id_mutation", "date_mutation", "nature_mutation", "valeur_fonciere", "type_local", "surface_reelle_bati",
    "nombre_pieces_principales", "code_commune", "nombre_lots", *CARREZ,
]

DEBUT = datetime.strptime(DATE_DEBUT, "%Y-%m-%d").date()
FIN = datetime.strptime(DATE_FIN, "%Y-%m-%d").date()
ETAPES: dict[str, dict[str, int]] = {}   # effectif par nombre de pièces à chaque étape, pour l'entonnoir final


# ── Outils ──────────────────────────────────────────────────

def _client():
    return bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)


def _table(nom):
    return f"`{GCP_PROJECT_ID}.{BQ_DATASET}.{nom}`"


def _lire_bq(client, sql):
    return pl.DataFrame([dict(r) for r in client.query(sql).result()], infer_schema_length=None)


def _etiquette(pieces):
    return NON_RENSEIGNE if pieces is None else str(pieces)


def _cle_etiquette(etiquette):
    return (etiquette == NON_RENSEIGNE, int(etiquette) if etiquette.isdigit() else 0)


def _quantile(valeurs_triees, q):
    """Même interpolation linéaire que backend/app/services/immobilier_bdnb_analyse.py."""
    position = (len(valeurs_triees) - 1) * q
    bas = int(position)
    haut = min(bas + 1, len(valeurs_triees) - 1)
    return valeurs_triees[bas] + (valeurs_triees[haut] - valeurs_triees[bas]) * (position - bas)


def _pieces():
    """Même normalisation que le cube : NULL sous 1 pièce, plafonné à PIECES_MAX."""
    p = pl.col("nombre_pieces_principales")
    return pl.when(p >= 1).then(pl.min_horizontal(p, pl.lit(PIECES_MAX))).otherwise(None).alias("pieces")


def _m2_par_piece():
    nb = pl.col("nombre_pieces_principales")
    return pl.when(nb >= 1).then(pl.col("surface_reelle_bati") / nb)


def _fenetre(df):
    return df.filter(pl.col("date_mutation").is_between(DEBUT, FIN))


def _bornes(df):
    return df.filter(pl.col("prix_m2").is_between(PRIX_M2_MIN, PRIX_M2_MAX))


def _noter(etape, df):
    ETAPES[etape] = {_etiquette(p): n for p, n in df.group_by("pieces").len().iter_rows()}


def _stats(df, par=("pieces",)):
    """Une ligne par groupe : effectif, quartiles et médiane du prix au m², surface médiane si la colonne existe."""
    agg = [
        pl.len().alias("n"),
        pl.col("prix_m2").quantile(0.25, "linear").alias("q1"),
        pl.col("prix_m2").median().alias("prix_median"),
        pl.col("prix_m2").quantile(0.75, "linear").alias("q3"),
    ]
    if "surface_reelle_bati" in df.columns:
        agg.append(pl.col("surface_reelle_bati").median().alias("surface_mediane"))
    return df.group_by(list(par)).agg(agg).sort(list(par), nulls_last=True)


def _afficher(titre, df):
    print(f"\n== {titre}")
    if "pieces" in df.columns:
        df = df.with_columns(pl.col("pieces").cast(pl.Utf8).fill_null(NON_RENSEIGNE))
    with pl.Config(tbl_rows=-1, tbl_cols=-1):
        print(df.with_columns(pl.col(pl.Float64).round(1)))


# ── Données brutes (table BigQuery ou Parquet) ──────────────

def _lire_parquet():
    return pl.read_parquet(PARQUET, columns=COLONNES_BRUT).filter(pl.col("nature_mutation") == NATURE_VENTE)


def _lire_table(client):
    return _lire_bq(client, f"""
        SELECT {", ".join(COLONNES_BRUT)} FROM {_table(TABLE_DVF)}
        WHERE livraison = '{LIVRAISON}' AND code_departement = '{DEPARTEMENT}' AND nature_mutation = '{NATURE_VENTE}'
    """)


def _regle_v1(brut):
    """Règle de la vue dvf_etalab_ventes_logement, reconstituée : une mutation = un seul logement, sans local
    commercial. Une ligne par vente, avec prix au m² (NULL si surface nulle) et la composition de la mutation."""
    return (
        brut.with_columns(
            pl.col("type_local").is_in(TYPES_LOGEMENT).sum().over("id_mutation").alias("nb_logements"),
            (pl.col("type_local") == TYPE_LOCAL_COMMERCIAL).any().over("id_mutation").alias("a_commercial"),
            (pl.col("type_local") == TYPE_DEPENDANCE).any().over("id_mutation").alias("a_dependance"),
            pl.len().over("id_mutation").alias("nb_lignes"),
        )
        .filter((pl.col("nb_logements") == 1) & ~pl.col("a_commercial") & pl.col("type_local").is_in(TYPES_LOGEMENT))
        .with_columns(
            pl.when(pl.col("surface_reelle_bati") > 0)
              .then(pl.col("valeur_fonciere") / pl.col("surface_reelle_bati")).alias("prix_m2"),
            _pieces(),
            (pl.col("code_commune").cast(pl.Int64, strict=False) - 75100).alias("arrondissement"),
        )
    )


def couche_brut(nom, brut):
    """Couches table et parquet : lignes de logement sans règle, puis règle V1, puis fenêtre et bornes du cube."""
    lignes = brut.filter(pl.col("type_local").is_in(TYPES_LOGEMENT)).with_columns(
        pl.when(pl.col("surface_reelle_bati") > 0)
          .then(pl.col("valeur_fonciere") / pl.col("surface_reelle_bati")).alias("prix_m2"),
        _pieces(),
    )
    _noter(f"{nom}:lignes", lignes)
    _afficher(f"{nom.upper()} : lignes de logement, sans aucune règle (prix = valeur de la mutation / surface)", _stats(lignes))

    ventes = _regle_v1(brut)
    _noter(f"{nom}:v1", ventes)
    final = _bornes(_fenetre(ventes))
    _noter(f"{nom}:final", final)
    _afficher(f"{nom.upper()} : règle V1, fenêtre {DATE_DEBUT} → {DATE_FIN}, bornes {PRIX_M2_MIN}–{PRIX_M2_MAX}", _stats(final))


# ── Couches agrégées ────────────────────────────────────────

def couche_api(base):
    reponse = requests.get(base.rstrip("/") + CHEMIN_API, params={"source": "ventes", "axe": "pieces"}, timeout=TIMEOUT)
    reponse.raise_for_status()
    corps = reponse.json()
    meta = corps["meta"]
    print(f"\n== API {reponse.url}")
    print(f"Trimestres {meta['trimestre_min']} → {meta['trimestre_max']} ; seuil appliqué : {meta['seuil_applique']} ; "
          f"groupes masqués : {meta['nb_masquees']}")
    lignes = [
        {"pieces": c["modalites"][0], "n": c["n"], "q1": c["q1"], "prix_median": c["mediane"], "q3": c["q3"]}
        for c in corps["cellules"]
    ]
    ETAPES["api"] = {l["pieces"]: l["n"] for l in lignes}
    _afficher("API : prix au m² par nombre de pièces", pl.DataFrame(lignes))


def couche_cube(client):
    for axes in (["pieces"], ["pieces", "tranche_surface"]):
        colonnes = ", ".join(axes)
        resultat = client.query(
            f"SELECT {colonnes}, SUM(nb_ventes) AS n, ARRAY_CONCAT_AGG(prix_m2) AS prix "
            f"FROM {_table(TABLE_VENTES)} GROUP BY {colonnes}"
        ).result()
        lignes = []
        for r in resultat:
            prix = sorted(r["prix"])
            lignes.append({
                **{a: r[a] for a in axes}, "n": r["n"], "nb_prix": len(prix),
                "q1": _quantile(prix, 0.25), "prix_median": _quantile(prix, 0.5), "q3": _quantile(prix, 0.75),
            })
        lignes.sort(key=lambda l: (l["pieces"] is None, l["pieces"] or 0, l.get("tranche_surface") or ""))
        if axes == ["pieces"]:
            ETAPES["cube"] = {_etiquette(l["pieces"]): l["n"] for l in lignes}
        _afficher(f"CUBE {TABLE_VENTES} par {' x '.join(axes)} (nb_prix doit égaler n)",
                  pl.DataFrame(lignes, infer_schema_length=None))


def couche_vues(client):
    for nom, vue in (("vue_log", VUE_VENTES), ("vue_bat", VUE_VENTES_BATIMENT)):
        df = _lire_bq(client, f"""
            SELECT nombre_pieces_principales, surface_reelle_bati, prix_m2, date_mutation FROM {_table(vue)}
            WHERE livraison = '{LIVRAISON}' AND code_departement = '{DEPARTEMENT}'
        """).with_columns(_pieces())
        _noter(f"{nom}:toutes", df)
        final = _bornes(_fenetre(df))
        _noter(f"{nom}:final", final)
        _afficher(f"VUE {vue} : fenêtre et bornes du cube", _stats(final))


# ── Diagnostics sur le Parquet ──────────────────────────────

def _largeur(ventes):
    """Prix médian par arrondissement (lignes) et nombre de pièces (colonnes), cellules sous le seuil vides."""
    exprs = [pl.len().alias("n")]
    for p in range(1, PIECES_MAX + 1):
        est = pl.col("pieces") == p
        exprs.append(pl.when(est.sum() >= SEUIL_CELLULE).then(pl.col("prix_m2").filter(est).median()).alias(f"{p}p"))
    return ventes.group_by("arrondissement").agg(exprs).sort("arrondissement")


def couche_diag():
    brut = _lire_parquet()
    _afficher("D0 type_local des lignes de vente (le libellé de dépendance doit y figurer tel quel)",
              brut.group_by("type_local").len().sort("len", descending=True))

    avant = _fenetre(_regle_v1(brut))
    ventes = _bornes(avant)

    _afficher("D1 composition des ventes retenues et cohérence pièces / surface", ventes.group_by("pieces").agg(
        pl.len().alias("n"),
        (pl.col("a_dependance").mean() * 100).alias("pct_avec_dependance"),
        pl.col("nb_lignes").median().alias("lignes_par_mutation"),
        pl.col("nombre_lots").median().alias("lots_mediane"),
        pl.col("surface_reelle_bati").median().alias("surface_mediane"),
        _m2_par_piece().median().alias("m2_par_piece"),
        (_m2_par_piece() < M2_PAR_PIECE_MIN).mean().mul(100).alias(f"pct_sous_{M2_PAR_PIECE_MIN}m2_par_piece"),
        (_m2_par_piece() > M2_PAR_PIECE_MAX).mean().mul(100).alias(f"pct_sur_{M2_PAR_PIECE_MAX}m2_par_piece"),
    ).sort("pieces", nulls_last=True))

    _afficher("D2 prix médian avec / sans dépendance dans la mutation",
              _stats(ventes, ("pieces", "a_dependance")).select("pieces", "a_dependance", "n", "prix_median"))

    d4 = _largeur(ventes)
    _afficher(f"D3 prix médian au m² par arrondissement et nombre de pièces (cellules ≥ {SEUIL_CELLULE} ventes)", d4)
    comparables = d4.filter(pl.col("1p").is_not_null() & pl.col("3p").is_not_null())
    print(f"Arrondissements où le 1 pièce est plus cher que le 3 pièces : "
          f"{comparables.filter(pl.col('1p') > pl.col('3p')).height} sur {comparables.height}")

    _afficher(f"D4 ventes écartées par les bornes {PRIX_M2_MIN}–{PRIX_M2_MAX} (avant bornes)", avant.group_by("pieces").agg(
        pl.len().alias("n"),
        pl.col("prix_m2").is_null().sum().alias("surface_nulle"),
        (pl.col("prix_m2") < PRIX_M2_MIN).sum().alias("sous_min"),
        (pl.col("prix_m2") > PRIX_M2_MAX).sum().alias("sur_max"),
    ).sort("pieces", nulls_last=True))

    sans_dependance = ventes.filter(~pl.col("a_dependance"))
    _afficher("D5 test : sans dépendance", _stats(sans_dependance))
    coherentes = sans_dependance.filter(_m2_par_piece().is_between(M2_PAR_PIECE_MIN, M2_PAR_PIECE_MAX))
    _afficher(f"D6 test : sans dépendance et {M2_PAR_PIECE_MIN} à {M2_PAR_PIECE_MAX} m² par pièce", _stats(coherentes))


# ── Surface Carrez ──────────────────────────────────────────

def _avec_carrez(ventes):
    """Ajoute la surface Carrez de la ligne (somme des lots renseignés, NULL si aucun), le prix au m² sur cette surface
    et le rapport surface cadastrale / surface Carrez."""
    renseignes = [pl.col(c).is_not_null() for c in CARREZ]
    return ventes.with_columns(
        pl.when(pl.any_horizontal(*renseignes)).then(pl.sum_horizontal(*CARREZ)).alias("carrez"),
    ).with_columns(
        pl.when(pl.col("carrez") > 0).then(pl.col("valeur_fonciere") / pl.col("carrez")).alias("prix_m2_carrez"),
        pl.when(pl.col("carrez") > 0).then(pl.col("surface_reelle_bati") / pl.col("carrez")).alias("rapport_surfaces"),
    )


def couche_carrez():
    """Prix au m² sur la surface Carrez (lots du DVF) au lieu de la surface réelle bâtie du cadastre, mutations sans
    dépendance. Les deux prix sont comparés sur les mêmes ventes (bornes appliquées aux deux)."""
    ventes = _avec_carrez(_bornes(_fenetre(_regle_v1(_lire_parquet()))).filter(~pl.col("a_dependance")))

    _afficher("C1 couverture de la surface Carrez (ventes sans dépendance)", ventes.group_by("pieces").agg(
        pl.len().alias("n"),
        (pl.col("carrez").fill_null(0) > 0).sum().alias("avec_carrez"),
        ((pl.col("carrez").fill_null(0) > 0).mean() * 100).alias("pct_avec_carrez"),
    ).sort("pieces", nulls_last=True))

    communes = ventes.filter(pl.col("prix_m2_carrez").is_between(PRIX_M2_MIN, PRIX_M2_MAX))

    _afficher("C2 rapport surface cadastre / surface Carrez (ventes ayant un Carrez, prix dans les bornes)",
              communes.group_by("pieces").agg(
                  pl.len().alias("n"),
                  pl.col("rapport_surfaces").quantile(0.25, "linear").alias("rapport_q1"),
                  pl.col("rapport_surfaces").median().alias("rapport_median"),
                  pl.col("rapport_surfaces").quantile(0.75, "linear").alias("rapport_q3"),
                  pl.col("surface_reelle_bati").median().alias("surface_cadastre"),
                  pl.col("carrez").median().alias("surface_carrez"),
              ).sort("pieces", nulls_last=True))

    _afficher("C3 prix au m² : cadastre contre Carrez (mêmes ventes)", communes.group_by("pieces").agg(
        pl.len().alias("n"),
        pl.col("prix_m2").median().alias("prix_median_cadastre"),
        pl.col("prix_m2_carrez").quantile(0.25, "linear").alias("carrez_q1"),
        pl.col("prix_m2_carrez").median().alias("prix_median_carrez"),
        pl.col("prix_m2_carrez").quantile(0.75, "linear").alias("carrez_q3"),
        ((pl.col("prix_m2_carrez").median() / pl.col("prix_m2").median() - 1) * 100).alias("ecart_pct"),
    ).sort("pieces", nulls_last=True))

    sur_carrez = communes.with_columns(pl.col("prix_m2_carrez").alias("prix_m2"))
    _afficher(f"C4 prix médian au m² Carrez par arrondissement et nombre de pièces (cellules ≥ {SEUIL_CELLULE} ventes)",
              _largeur(sur_carrez))
    for nom, base in (("cadastre", communes), ("Carrez", sur_carrez)):
        d = _largeur(base)
        comparables = d.filter(pl.col("1p").is_not_null() & pl.col("3p").is_not_null())
        print(f"{nom} : arrondissements où le 1 pièce est plus cher que le 3 pièces : "
              f"{comparables.filter(pl.col('1p') > pl.col('3p')).height} sur {comparables.height}")




# ── Entonnoir ───────────────────────────────────────────────

def entonnoir():
    etiquettes = sorted({e for d in ETAPES.values() for e in d}, key=_cle_etiquette)
    _afficher("ENTONNOIR : effectif par nombre de pièces à chaque étape", pl.DataFrame({
        "pieces": etiquettes, **{etape: [d.get(e) for e in etiquettes] for etape, d in ETAPES.items()},
    }))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--couche", required=True, choices=["api", "cube", "vues", "table", "parquet", "diag", "carrez", "all"])
    parser.add_argument("--api", help="URL de base du backend (par exemple celle de l'API locale ou de Scaleway)")
    args = parser.parse_args()

    couches = ["api", "cube", "vues", "table", "parquet", "diag", "carrez"] if args.couche == "all" else [args.couche]
    client = None
    for couche in couches:
        if couche == "api":
            if args.api:
                couche_api(args.api)
            elif args.couche == "api":
                parser.error("--api URL requis pour la couche api")
            else:
                print("\n(couche api ignorée : --api absent)")
        elif couche == "parquet":
            couche_brut("parquet", _lire_parquet())
        elif couche == "diag":
            couche_diag()
        elif couche == "carrez":
            couche_carrez()
        else:
            client = client or _client()
            if couche == "cube":
                couche_cube(client)
            elif couche == "vues":
                couche_vues(client)
            else:
                couche_brut("table", _lire_table(client))
    if len(ETAPES) > 1:
        entonnoir()


if __name__ == "__main__":
    main()

"""Exploration des données BDNB (dept. 75) à partir des Parquet produits par convert_bdnb_parquet.py.

Usage : python scripts\\explore_bdnb.py --bloc 1|...|8|all [--rapport] [--lignes 20]
        python scripts\\explore_bdnb.py --dico COLONNE [COLONNE ...] [--table TABLE] [--rapport]
Terminal : les --lignes premières lignes de chaque tableau. Fichier (--rapport) : la totalité.
"""
import argparse
from datetime import datetime
from pathlib import Path

import polars as pl

# --- Paramètres ---
DOSSIER_BDNB = Path(__file__).resolve().parent.parent / "pipeline" / "data" / "bdnb"
DOSSIER_CSV = DOSSIER_BDNB / "bdnb_dep75_csv" / "csv"
DOSSIER_PARQUET = DOSSIER_BDNB / "parquet"
DOSSIER_RAPPORTS = DOSSIER_BDNB / "rapports"
LIGNES_TERMINAL = 20


# Sélection DPE (décision du 2026-10-21 : arrêté 2012 écarté pour le moment)
ARRETE_2021 = 1
SUFFIXE_TYPE_DPE = "logement"  # écarte les DPE "immeuble"
COLONNES_CLES = [
    "surface_habitable_logement", "conso_5_usages_ep_m2", "conso_5_usages_ef_m2",
    "emission_ges_5_usages_m2", "classe_bilan_dpe", "classe_emission_ges",
    "type_energie_chauffage", "type_energie_ecs", "type_generateur_chauffage",
    "annee_construction_dpe", "periode_construction_dpe", "type_batiment_dpe",
    "nombre_niveau_logement", "date_etablissement_dpe", "version",
]
# Étiquettes de l'API ADEME, mesurées le 2026-10-20 (cahier immobilier.md, section 3)
ETIQUETTES_API = {"A": 1058, "B": 9897, "C": 191598, "D": 264376, "E": 232246, "F": 95832, "G": 59964}
# DVF : bornes de prix_m2 de la V1 (backlog n°3) et ventes de logement validées par la V1 sur 2021-2025
PRIX_M2_MIN = 2000
PRIX_M2_MAX = 30000
V1_VENTES_VALIDEES = 145128
COLONNES_DVF = [
    "valeur_fonciere", "date_mutation", "prix_m2_local", "nb_piece_principale",
    "surface_bati_mutee_residencielle_individuelle", "surface_bati_mutee_residencielle_collective",
]
# Simulation de sélection (bloc 8)
METHODE_DPE = "3cl"
FIABILITE_ACCEPTEE = ["très fiable", "globalement fiable"]
DATE_POST_REFORME = (2026, 1, 1)
# Dictionnaire (--dico) : longueur maximale des modalités affichées
MODALITES_MAX = 300

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


def bloc_1(sortie):
    """Volumes : tables converties (lignes, colonnes, tailles) et CSV non convertis (taille seule)."""
    sortie.titre("Bloc 1 - Tables converties en Parquet")
    converties = []
    for chemin in sorted(DOSSIER_PARQUET.glob("*.parquet")):
        lf = pl.scan_parquet(chemin)
        csv = DOSSIER_CSV / f"{chemin.stem}.csv"
        converties.append({
            "table": chemin.stem,
            "lignes": lf.select(pl.len()).collect().item(),
            "colonnes": len(lf.collect_schema()),
            "csv_mo": round(csv.stat().st_size / 1e6, 1),
            "parquet_mo": round(chemin.stat().st_size / 1e6, 1),
        })
    if converties:
        sortie.tableau(pl.DataFrame(converties).sort("lignes", descending=True))
    else:
        print("Aucun Parquet trouvé : lancer convert_bdnb_parquet.py")

    sortie.titre("Bloc 1 - CSV non convertis (taille seule)")
    non_convertis = [
        {"table": csv.stem, "csv_mo": round(csv.stat().st_size / 1e6, 1)}
        for csv in DOSSIER_CSV.glob("*.csv")
        if not (DOSSIER_PARQUET / f"{csv.stem}.parquet").exists()
    ]
    sortie.tableau(pl.DataFrame(non_convertis).sort("csv_mo", descending=True))


def bloc_2(sortie):
    """DPE logement : répartition par arrêté et type, dates, doublons d'identifiant."""
    lf = pl.scan_parquet(DOSSIER_PARQUET / "dpe_logement.parquet").with_columns(
        pl.col("arrete_2021").cast(pl.Int64, strict=False),
        pl.col("date_etablissement_dpe").cast(pl.Utf8).str.slice(0, 10).str.to_date("%Y/%m/%d", strict=False).alias("date_etab"),
        pl.col("date_reception_dpe").cast(pl.Utf8).str.slice(0, 10).str.to_date("%Y/%m/%d", strict=False).alias("date_recep"),
    )

    sortie.titre("Bloc 2 - Totaux et doublons d'identifiant_dpe")
    sortie.tableau(lf.select(
        pl.len().alias("lignes"),
        pl.col("identifiant_dpe").n_unique().alias("identifiants_uniques"),
    ).collect())

    sortie.titre("Bloc 2 - Par arrêté et type de DPE (dates min / max)")
    sortie.tableau(
        lf.group_by("arrete_2021", "type_dpe").agg(
            pl.len().alias("lignes"),
            pl.col("date_etab").min().alias("etab_min"),
            pl.col("date_etab").max().alias("etab_max"),
            pl.col("date_etab").is_null().sum().alias("etab_vide"),
            pl.col("date_recep").min().alias("recep_min"),
            pl.col("date_recep").max().alias("recep_max"),
        ).sort("arrete_2021", "type_dpe").collect()
    )

    sortie.titre("Bloc 2 - Arrêté 2021 : lignes par année d'établissement")
    sortie.tableau(
        lf.filter(pl.col("arrete_2021") == 1)
        .group_by(pl.col("date_etab").dt.year().alias("annee_etablissement"))
        .agg(pl.len().alias("lignes"))
        .sort("annee_etablissement")
        .collect()
    )

def selection_dpe():
    """DPE retenus : arrêté 2021, type logement (paramètres en tête de fichier)."""
    return pl.scan_parquet(DOSSIER_PARQUET / "dpe_logement.parquet").filter(
        (pl.col("arrete_2021").cast(pl.Int64, strict=False) == ARRETE_2021)
        & pl.col("type_dpe").str.ends_with(SUFFIXE_TYPE_DPE)
    )


def compter(lf):
    return lf.select(pl.len()).collect().item()


def mesures_en_tableau(mesures):
    return pl.DataFrame({
        "mesure": [m for m, _ in mesures],
        "valeur": [str(v) for _, v in mesures],
    })


def bloc_3(sortie):
    """Taux de remplissage de la sélection DPE et étiquettes comparées à l'API ADEME."""
    lf = selection_dpe()
    n = lf.select(pl.len()).collect().item()
    sortie.titre(f"Bloc 3 - Sélection DPE : {n} lignes")

    nuls = lf.select(pl.all().null_count()).collect()
    remplissage = pl.DataFrame({
        "colonne": nuls.columns,
        "non_nuls": [n - v for v in nuls.row(0)],
    }).with_columns((pl.col("non_nuls") / n * 100).round(1).alias("taux_pct"))

    sortie.titre("Bloc 3 - Colonnes clés (les moins remplies d'abord)")
    sortie.tableau(remplissage.filter(pl.col("colonne").is_in(COLONNES_CLES)).sort("taux_pct"))

    sortie.titre("Bloc 3 - Toutes les colonnes (les moins remplies d'abord)")
    sortie.tableau(remplissage.sort("taux_pct"))

    sortie.titre("Bloc 3 - Étiquettes (classe_bilan_dpe) comparées à l'API ADEME")
    total_api = sum(ETIQUETTES_API.values())
    api = pl.DataFrame({
        "classe_bilan_dpe": list(ETIQUETTES_API),
        "api_lignes": list(ETIQUETTES_API.values()),
    }).with_columns((pl.col("api_lignes") / total_api * 100).round(1).alias("api_pct"))
    etiquettes = (
        lf.group_by("classe_bilan_dpe").agg(pl.len().alias("bdnb_lignes")).collect()
        .with_columns((pl.col("bdnb_lignes") / n * 100).round(1).alias("bdnb_pct"))
    )
    sortie.tableau(etiquettes.join(api, on="classe_bilan_dpe", how="full", coalesce=True).sort("classe_bilan_dpe"))

    sortie.titre("Bloc 3 - Énergie de chauffage x énergie d'ECS")
    sortie.tableau(
        lf.group_by("type_energie_chauffage", "type_energie_ecs").agg(pl.len().alias("lignes"))
        .with_columns((pl.col("lignes") / n * 100).round(1).alias("part_pct"))
        .sort("lignes", descending=True).collect()
    )


def bloc_4(sortie):
    """Lien DPE vers bâtiment : cohérence des identifiants, liens multiples, fiabilité du géocodage."""
    dpe = pl.scan_parquet(DOSSIER_PARQUET / "dpe_logement.parquet")
    selection = selection_dpe()
    rel = pl.scan_parquet(DOSSIER_PARQUET / "rel_batiment_groupe_dpe_logement.parquet")
    ids_rel = rel.select("identifiant_dpe").unique()

    n_selection = compter(selection)
    n_sans_lien = compter(selection.join(ids_rel, on="identifiant_dpe", how="anti"))
    mesures = [
        ("lignes de rel_batiment_groupe_dpe_logement", compter(rel)),
        ("identifiant_dpe distincts dans rel", compter(ids_rel)),
        ("identifiant_dpe de rel absents de dpe_logement", compter(ids_rel.join(dpe.select("identifiant_dpe"), on="identifiant_dpe", how="anti"))),
        ("batiment_groupe_id distincts dans rel", rel.select(pl.col("batiment_groupe_id").n_unique()).collect().item()),
        ("DPE de la sélection", n_selection),
        ("DPE de la sélection sans lien bâtiment", n_sans_lien),
        ("part rattachée de la sélection (%)", round((n_selection - n_sans_lien) / n_selection * 100, 2)),
    ]
    sortie.titre("Bloc 4 - Cohérence dpe_logement / rel")
    sortie.tableau(pl.DataFrame({
        "mesure": [m for m, _ in mesures],
        "valeur": [str(v) for _, v in mesures],
    }))

    sortie.titre("Bloc 4 - Nombre de lignes de rel par identifiant_dpe")
    sortie.tableau(
        rel.group_by("identifiant_dpe").agg(pl.len().alias("nb_liens"))
        .group_by("nb_liens").agg(pl.len().alias("dpe"))
        .sort("nb_liens").collect()
    )

    liens = selection.select("identifiant_dpe").join(rel, on="identifiant_dpe", how="inner")
    nb_liens = compter(liens)
    for colonne in ("fiabilite_geocodage", "type_appariement"):
        sortie.titre(f"Bloc 4 - Sélection : {colonne}")
        sortie.tableau(
            liens.group_by(colonne).agg(pl.len().alias("liens"))
            .with_columns((pl.col("liens") / nb_liens * 100).round(1).alias("part_pct"))
            .sort("liens", descending=True).collect()
        )


def bloc_5(sortie):
    """DVF : transaction représentative par bâtiment, liens de mutation, statistiques par bâtiment."""
    lf = pl.scan_parquet(DOSSIER_PARQUET / "batiment_groupe_dvf_open_representatif.parquet").with_columns(
        pl.col("date_mutation").cast(pl.Utf8).str.slice(0, 10).str.to_date("%Y/%m/%d", strict=False).alias("date_mut"),
    )

    sortie.titre("Bloc 5 - Transaction représentative : volumes et dates")
    sortie.tableau(lf.select(
        pl.len().alias("lignes"),
        pl.col("batiment_groupe_id").n_unique().alias("batiments_uniques"),
        pl.col("id_opendata").n_unique().alias("mutations_uniques"),
        pl.col("date_mut").min().alias("date_min"),
        pl.col("date_mut").max().alias("date_max"),
        pl.col("date_mut").is_null().sum().alias("date_vide"),
    ).collect())

    sortie.titre("Bloc 5 - Lignes par année de mutation")
    par_annee = (
        lf.group_by(pl.col("date_mut").dt.year().alias("annee"))
        .agg(pl.len().alias("lignes")).sort("annee").collect()
    )
    sortie.tableau(par_annee)

    n_periode = par_annee.filter(pl.col("annee").is_between(2021, 2025))["lignes"].sum()
    sortie.titre("Bloc 5 - Comparaison avec la V1 (2021-2025)")
    sortie.tableau(mesures_en_tableau([
        ("BDNB : transactions représentatives 2021-2025", n_periode),
        ("V1 : ventes de logement validées 2021-2025", V1_VENTES_VALIDEES),
    ]))

    sortie.titre("Bloc 5 - Taux de remplissage des colonnes clés (%)")
    sortie.tableau(
        lf.select([pl.col(c).is_not_null().mean().mul(100).round(1).alias(c) for c in COLONNES_DVF])
        .collect().transpose(include_header=True, header_name="colonne", column_names=["taux_pct"])
    )

    sortie.titre("Bloc 5 - prix_m2_local : quantiles et lignes hors bornes V1")
    quantiles = [0.01, 0.05, 0.5, 0.95, 0.99]
    sortie.tableau(lf.select(
        pl.col("prix_m2_local").min().alias("min"),
        *[pl.col("prix_m2_local").quantile(q).alias(f"p{round(q * 100)}") for q in quantiles],
        pl.col("prix_m2_local").max().alias("max"),
        pl.col("prix_m2_local").is_not_null().sum().alias("avec_prix"),
        (pl.col("prix_m2_local") < PRIX_M2_MIN).sum().alias("sous_min"),
        (pl.col("prix_m2_local") > PRIX_M2_MAX).sum().alias("au_dessus_max"),
    ).collect())

    sortie.titre("Bloc 5 - Nombre de locaux par mutation (3 = 3 ou plus)")
    sortie.tableau(
        lf.group_by(
            pl.when(pl.col("nb_locaux_mutee_mutation") >= 3).then(3)
            .otherwise(pl.col("nb_locaux_mutee_mutation")).alias("nb_locaux")
        ).agg(pl.len().alias("lignes")).sort("nb_locaux").collect()
    )

    rel = pl.scan_parquet(DOSSIER_PARQUET / "rel_batiment_groupe_dvf_open.parquet")
    stat = pl.scan_parquet(DOSSIER_PARQUET / "batiment_groupe_dvf_open_statistique.parquet")
    sortie.titre("Bloc 5 - Liens de mutation et statistiques par bâtiment")
    sortie.tableau(mesures_en_tableau([
        ("lignes de rel_batiment_groupe_dvf_open", compter(rel)),
        ("id_opendata distincts dans rel", rel.select(pl.col("id_opendata").n_unique()).collect().item()),
        ("bâtiments distincts dans rel", rel.select(pl.col("batiment_groupe_id").n_unique()).collect().item()),
        ("statistique : bâtiments", compter(stat)),
        ("statistique : somme de nb_mutation", stat.select(pl.col("nb_mutation").sum()).collect().item()),
        ("statistique : bâtiments avec 2 mutations ou plus", compter(stat.filter(pl.col("nb_mutation") >= 2))),
    ]))

    sortie.titre("Bloc 5 - fiabilite_croisement des liens de mutation")
    sortie.tableau(rel.group_by("fiabilite_croisement").agg(pl.len().alias("liens")).sort("liens", descending=True).collect())


def bloc_6(sortie):
    """Chaîne adresse -> bâtiment -> DPE / DVF : couverture et cardinalités."""
    adresse = pl.scan_parquet(DOSSIER_PARQUET / "adresse.parquet")
    rel_adr = pl.scan_parquet(DOSSIER_PARQUET / "rel_batiment_groupe_adresse.parquet")
    batiments = pl.scan_parquet(DOSSIER_PARQUET / "batiment_groupe.parquet")
    rel_dpe = pl.scan_parquet(DOSSIER_PARQUET / "rel_batiment_groupe_dpe_logement.parquet")
    dvf = pl.scan_parquet(DOSSIER_PARQUET / "batiment_groupe_dvf_open_representatif.parquet")

    cles_adresse = adresse.select("cle_interop_adr").unique()
    cles_rel = rel_adr.select("cle_interop_adr").unique()
    bat_adresses = rel_adr.select("batiment_groupe_id").unique()
    bat_dpe = (
        selection_dpe().select("identifiant_dpe")
        .join(rel_dpe.select("identifiant_dpe", "batiment_groupe_id"), on="identifiant_dpe")
        .select("batiment_groupe_id").unique()
    )
    bat_dvf = dvf.select("batiment_groupe_id").unique()

    sortie.titre("Bloc 6 - Cohérence adresse / rel_batiment_groupe_adresse / batiment_groupe")
    sortie.tableau(mesures_en_tableau([
        ("adresses (cle_interop_adr distinctes)", compter(cles_adresse)),
        ("lignes de rel_batiment_groupe_adresse", compter(rel_adr)),
        ("cle_interop_adr distinctes dans rel", compter(cles_rel)),
        ("bâtiments distincts dans rel", compter(bat_adresses)),
        ("adresses sans lien vers un bâtiment", compter(cles_adresse.join(cles_rel, on="cle_interop_adr", how="anti"))),
        ("clés de rel absentes de la table adresse", compter(cles_rel.join(cles_adresse, on="cle_interop_adr", how="anti"))),
        ("bâtiments (batiment_groupe)", compter(batiments)),
        ("bâtiments sans adresse dans rel", compter(batiments.select("batiment_groupe_id").join(bat_adresses, on="batiment_groupe_id", how="anti"))),
    ]))

    for titre, cle, autre in (
        ("bâtiments par adresse", "cle_interop_adr", "batiment_groupe_id"),
        ("adresses par bâtiment", "batiment_groupe_id", "cle_interop_adr"),
    ):
        sortie.titre(f"Bloc 6 - {titre} (5 = 5 ou plus)")
        sortie.tableau(
            rel_adr.group_by(cle).agg(pl.col(autre).n_unique().alias("nb"))
            .group_by(pl.when(pl.col("nb") >= 5).then(5).otherwise(pl.col("nb")).alias("nb_regroupe"))
            .agg(pl.len().alias("effectif")).sort("nb_regroupe").collect()
        )

    for colonne in ("origine", "fiabilite"):
        sortie.titre(f"Bloc 6 - rel_batiment_groupe_adresse : {colonne}")
        sortie.tableau(rel_adr.group_by(colonne).agg(pl.len().alias("liens")).sort("liens", descending=True).collect())

    sortie.titre("Bloc 6 - Adresses par code_commune_insee")
    sortie.tableau(adresse.group_by("code_commune_insee").agg(pl.len().alias("adresses")).sort("code_commune_insee").collect())
    sortie.titre("Bloc 6 - Adresses par source")
    sortie.tableau(adresse.group_by("source").agg(pl.len().alias("adresses")).sort("adresses", descending=True).collect())

    sortie.titre("Bloc 6 - Couverture en adresse des bâtiments portant un DPE ou une vente")
    sortie.tableau(mesures_en_tableau([
        ("bâtiments avec DPE (sélection)", compter(bat_dpe)),
        ("  dont sans adresse dans rel", compter(bat_dpe.join(bat_adresses, on="batiment_groupe_id", how="anti"))),
        ("bâtiments avec transaction DVF représentative", compter(bat_dvf)),
        ("  dont sans adresse dans rel", compter(bat_dvf.join(bat_adresses, on="batiment_groupe_id", how="anti"))),
        ("bâtiments avec DPE et transaction DVF", compter(bat_dpe.join(bat_dvf, on="batiment_groupe_id", how="inner"))),
    ]))



def bloc_7(sortie):
    """Propriétaires (personnes morales) : comptages seulement, aucune dénomination n'est affichée."""
    prop = pl.scan_parquet(DOSSIER_PARQUET / "proprietaire.parquet")
    rel = pl.scan_parquet(DOSSIER_PARQUET / "rel_batiment_groupe_proprietaire.parquet")
    rel_dpe = pl.scan_parquet(DOSSIER_PARQUET / "rel_batiment_groupe_dpe_logement.parquet")
    bat_dpe = (
        selection_dpe().select("identifiant_dpe")
        .join(rel_dpe.select("identifiant_dpe", "batiment_groupe_id"), on="identifiant_dpe")
        .select("batiment_groupe_id").unique()
    )
    bat_prop = rel.select("batiment_groupe_id").unique()

    sortie.titre("Bloc 7 - Volumes et complétude")
    sortie.tableau(mesures_en_tableau([
        ("lignes de proprietaire", compter(prop)),
        ("personne_id distincts", prop.select(pl.col("personne_id").n_unique()).collect().item()),
        ("sans dénomination", compter(prop.filter(pl.col("denomination").is_null()))),
        ("sans forme juridique", compter(prop.filter(pl.col("forme_juridique").is_null()))),
        ("lignes de rel_batiment_groupe_proprietaire", compter(rel)),
        ("bâtiments distincts dans rel", compter(bat_prop)),
        ("propriétaires distincts dans rel", rel.select(pl.col("personne_id").n_unique()).collect().item()),
        ("bâtiments avec DPE (sélection)", compter(bat_dpe)),
        ("  dont avec au moins un propriétaire", compter(bat_dpe.join(bat_prop, on="batiment_groupe_id", how="inner"))),
    ]))

    sortie.titre("Bloc 7 - dans_majic_pm")
    sortie.tableau(prop.group_by("dans_majic_pm").agg(pl.len().alias("proprietaires")).sort("proprietaires", descending=True).collect())

    sortie.titre("Bloc 7 - Formes juridiques (propriétaires et locaux)")
    sortie.tableau(
        prop.group_by("forme_juridique")
        .agg(pl.len().alias("proprietaires"), pl.col("nb_locaux_open").sum().alias("locaux"))
        .sort("locaux", descending=True).collect()
    )

    sortie.titre("Bloc 7 - Département du siège (2 premiers chiffres du code postal)")
    sortie.tableau(
        prop.group_by(pl.col("code_postal").str.slice(0, 2).alias("departement_siege"))
        .agg(pl.len().alias("proprietaires")).sort("proprietaires", descending=True).collect()
    )

    sortie.titre("Bloc 7 - Propriétaires par bâtiment (5 = 5 ou plus)")
    sortie.tableau(
        rel.group_by("batiment_groupe_id").agg(pl.col("personne_id").n_unique().alias("nb"))
        .group_by(pl.when(pl.col("nb") >= 5).then(5).otherwise(pl.col("nb")).alias("nb_regroupe"))
        .agg(pl.len().alias("batiments")).sort("nb_regroupe").collect()
    )

    locaux = prop.select("nb_locaux_open").collect().to_series().drop_nulls().sort(descending=True)
    total = locaux.sum()
    sortie.titre("Bloc 7 - Concentration des locaux (aucun nom affiché)")
    sortie.tableau(mesures_en_tableau([
        ("total de nb_locaux_open", total),
        ("médiane de nb_locaux_open par propriétaire", locaux.median()),
        ("part des 10 plus gros propriétaires (%)", round(locaux.head(10).sum() / total * 100, 1)),
        ("part des 100 plus gros propriétaires (%)", round(locaux.head(100).sum() / total * 100, 1)),
    ]))


def bloc_8(sortie):
    """Simulation de sélection : volumétrie du jeu DPE selon des filtres cumulés (paramètres en tête de fichier)."""
    base = selection_dpe().with_columns(
        pl.col("date_etablissement_dpe").cast(pl.Utf8).str.slice(0, 10).str.to_date("%Y/%m/%d", strict=False).alias("date_etab"),
    )
    rel = pl.scan_parquet(DOSSIER_PARQUET / "rel_batiment_groupe_dpe_logement.parquet")
    liens_fiables = rel.filter(pl.col("fiabilite_geocodage").is_in(FIABILITE_ACCEPTEE)).select("identifiant_dpe", "batiment_groupe_id")
    bat_dvf = pl.scan_parquet(DOSSIER_PARQUET / "batiment_groupe_dvf_open_representatif.parquet").select("batiment_groupe_id").unique()

    methode = base.filter(pl.col("type_dpe").str.contains(METHODE_DPE, literal=True))
    surface = methode.filter(pl.col("surface_habitable_logement") > 0)
    geocode = surface.join(liens_fiables, on="identifiant_dpe", how="inner")
    avec_vente = geocode.join(bat_dvf, on="batiment_groupe_id", how="inner")
    etapes = [
        ("1. Base : arrêté 2021, logement", base),
        (f"2. + méthode {METHODE_DPE}", methode),
        ("3. + surface > 0", surface),
        (f"4. + géocodage {' / '.join(FIABILITE_ACCEPTEE)}", geocode),
        ("5. + bâtiment avec transaction DVF", avec_vente),
        ("variante A : 4 + DPE établis depuis la réforme", geocode.filter(pl.col("date_etab") >= pl.date(*DATE_POST_REFORME))),
        ("variante B : 4 + chauffage et ECS électriques", geocode.filter(
            (pl.col("type_energie_chauffage") == "electricite") & (pl.col("type_energie_ecs") == "electricite")
        )),
    ]

    lignes = []
    for nom, lf in etapes:
        colonnes = lf.collect_schema().names()
        dpe, batiments = lf.select(
            pl.col("identifiant_dpe").n_unique().alias("dpe"),
            (pl.col("batiment_groupe_id").n_unique() if "batiment_groupe_id" in colonnes else pl.lit(None)).alias("batiments"),
        ).collect().row(0)
        lignes.append({"etape": nom, "dpe": dpe, "batiments": batiments})

    sortie.titre("Bloc 8 - Volumétrie par étape de filtrage (DPE distincts)")
    sortie.tableau(
        pl.DataFrame(lignes, infer_schema_length=None)
        .with_columns((pl.col("dpe") / lignes[0]["dpe"] * 100).round(1).alias("part_base_pct"))
    )


def consulter_dico(sortie, noms, table, limite):
    """Affiche la définition des colonnes dont le nom contient l'un des motifs (metadonnees_colonne.csv)."""
    dico = pl.read_csv(DOSSIER_CSV / "metadonnees_colonne.csv", separator=";", infer_schema_length=0)
    trouvees = dico.filter(pl.any_horizontal([pl.col("nom_colonne").str.contains(n, literal=True) for n in noms]))
    if table:
        trouvees = trouvees.filter(pl.col("nom_table") == table)
    trouvees = trouvees.sort("nom_table", "nom_colonne")

    sortie.titre(f"Dictionnaire : {trouvees.height} colonne(s) trouvée(s) pour {noms}" + (f" dans {table}" if table else ""))
    for ligne in trouvees.head(limite).iter_rows(named=True):
        unite = f" ({ligne['unite']})" if ligne["unite"] else ""
        sortie.texte(f"\n{ligne['nom_table']}.{ligne['nom_colonne']} [{ligne['type_sql']}]{unite}")
        sortie.texte(ligne["description"] or "(pas de description)")
        if ligne["modalite_enum"]:
            sortie.texte(f"Modalités : {ligne['modalite_enum'][:MODALITES_MAX]}")
    if trouvees.height > limite:
        print(f"\n{trouvees.height - limite} autre(s) : augmenter --lignes ou filtrer avec --table")


BLOCS = {"1": bloc_1, "2": bloc_2, "3": bloc_3, "4": bloc_4, "5": bloc_5, "6": bloc_6, "7": bloc_7, "8": bloc_8}


def main():
    parser = argparse.ArgumentParser(description="Exploration des données BDNB (Parquet)")
    parser.add_argument("--bloc", choices=[*BLOCS, "all"], help="bloc à exécuter ou all")
    parser.add_argument("--dico", nargs="+", metavar="COLONNE", help="définition des colonnes dont le nom contient COLONNE")
    parser.add_argument("--table", help="avec --dico : limite la recherche à cette table")
    parser.add_argument("--rapport", action="store_true", help="écrit le compte rendu complet dans rapports/")
    parser.add_argument("--lignes", type=int, default=LIGNES_TERMINAL, help="lignes affichées par tableau dans le terminal")
    args = parser.parse_args()

    if not args.bloc and not args.dico:
        parser.error("--bloc ou --dico est requis")

    if args.dico:
        sortie = Sortie(args.lignes)
        consulter_dico(sortie, args.dico, args.table, args.lignes)
        if args.rapport:
            sortie.ecrire("dico")
        return

    for nom in (BLOCS if args.bloc == "all" else [args.bloc]):
        sortie = Sortie(args.lignes)
        BLOCS[nom](sortie)
        if args.rapport:
            sortie.ecrire(nom)



if __name__ == "__main__":
    main()

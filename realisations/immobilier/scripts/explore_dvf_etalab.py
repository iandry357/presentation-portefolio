"""Exploration de la livraison DVF Etalab : inventaire, téléchargement à part, comparaison avec le DVF de la V1,
remplissage, rattachement à blanc à la BDNB. Aucune écriture BigQuery (lecture seule, bloc 3).

Usage : python scripts\\explore_dvf_etalab.py --bloc 0|1|...|6|all [--rapport] [--lignes 20] [--force]
Terminal : les --lignes premières lignes de chaque tableau. Fichier (--rapport) : la totalité.
Bloc 1 : télécharge les fichiers absents (--force : tout retélécharger). Les blocs 2 à 6 lisent la fusion des fichiers annuels.
"""
import argparse
import csv
import gzip
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import polars as pl
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # pipeline.* (bloc 3), lancé depuis realisations/immobilier

# --- Paramètres ---
DOSSIER_BDNB = Path(__file__).resolve().parent.parent / "pipeline" / "data" / "bdnb"
DOSSIER_PARQUET = DOSSIER_BDNB / "parquet"
DOSSIER_RAPPORTS = DOSSIER_BDNB / "rapports"
DOSSIER_DVF = DOSSIER_BDNB / "dvf_etalab"
LIVRAISON = "2026-10"  # sous-dossier de la livraison (jamais celui de la V1 : son collecteur vide data/dvf)
DEPARTEMENT = "75"
# Livraison du 2026-10-20 (API data.gouv, jeu demandes-de-valeurs-foncieres-geolocalisees) : fichiers France entière
_BASE = "https://static.data.gouv.fr/resources/demandes-de-valeurs-foncieres-geolocalisees"
FICHIERS = {
    "2021-s2": {"url": f"{_BASE}/20261020-113024/full-2021-s2.csv.gz", "sha1": "077a1f07b802c32bb9d490b86f2496b1cec12950"},
    "2022": {"url": f"{_BASE}/20261020-114218/full-2022.csv.gz", "sha1": "a6e76cd85bf0bf09e52b0e72e0eca0c851925a5c"},
    "2023": {"url": f"{_BASE}/20261020-114336/full-2023.csv.gz", "sha1": "1fdaf0d76d52c4ca4b6e18fea382cab2faa6d06b"},
    "2024": {"url": f"{_BASE}/20261020-114532/full-2024.csv.gz", "sha1": "02e77911bdaf882bd63333b3032f1c37b4f4dc3f"},
    "2025": {"url": f"{_BASE}/20261020-114721/full-2025.csv.gz", "sha1": "3f01863b4913bf2d45e5331959e935e1a224b107"},
    "2026-s1": {"url": f"{_BASE}/20261020-114825/full-2026-s1.csv.gz", "sha1": "7cf0773e4df06028ab22a569425402739974d6a3"},
}
TIMEOUT = 120
LIGNES_TERMINAL = 20

# Règles de sélection identiques à la V1 (pipeline/transformation/dvf_transform.py)
LOGEMENTS = ["Appartement", "Maison"]
LOCAL_COMMERCIAL = "Local industriel. commercial ou assimilé"
PRIX_M2_MIN = 2000
PRIX_M2_MAX = 30000

# Colonnes dont on mesure le remplissage (bloc 2)
COLONNES_CLES = [
    "id_mutation", "date_mutation", "nature_mutation", "valeur_fonciere", "id_parcelle", "adresse_numero",
    "adresse_suffixe", "adresse_nom_voie", "adresse_code_voie", "code_commune", "type_local",
    "surface_reelle_bati", "nombre_pieces_principales", "lot1_surface_carrez", "longitude", "latitude",
]

# Normalisation des noms de voie (clé B du rattachement par adresse)
MOTS_VIDES = {"DE", "DU", "DES", "LA", "LE", "LES", "L", "D", "ET"}
ABREVIATIONS = {
    "AV": "AVENUE", "BD": "BOULEVARD", "FBG": "FAUBOURG", "ST": "SAINT", "STE": "SAINTE", "PL": "PLACE",
    "IMP": "IMPASSE", "PAS": "PASSAGE", "CHE": "CHEMIN", "SQ": "SQUARE", "ALL": "ALLEE", "RTE": "ROUTE",
    "QU": "QUAI", "VLA": "VILLA",
}


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
def dossier_livraison():
    return DOSSIER_DVF / LIVRAISON


def lire_bdnb(table, colonnes):
    return pl.read_parquet(DOSSIER_PARQUET / f"{table}.parquet", columns=colonnes)


def repartition(df, *colonnes):
    return (
        df.group_by(list(colonnes)).agg(pl.len().alias("lignes"))
        .with_columns((pl.col("lignes") / pl.col("lignes").sum() * 100).round(1).alias("pct"))
        .sort("lignes", descending=True)
    )


def semestre():
    d = pl.col("date_mutation")
    return pl.format("{}-S{}", d.dt.year(), pl.when(d.dt.month() <= 6).then(1).otherwise(2))


def lire_livraison():
    """Fusion des fichiers annuels en un seul Parquet de travail (tout en texte, colonne fichier_annee)."""
    fusion = dossier_livraison() / "fusion.parquet"
    if not fusion.exists():
        fichiers = sorted(dossier_livraison().glob("*.csv"))
        if not fichiers:
            raise SystemExit("Aucun fichier téléchargé : lancer --bloc 1")
        morceaux = [
            pl.read_csv(f, infer_schema_length=0).with_columns(pl.lit(f.stem).alias("fichier_annee"))
            for f in fichiers
        ]
        pl.concat(morceaux, how="diagonal").write_parquet(fusion)
    return pl.scan_parquet(fusion)


def typer(lf):
    valeur = pl.col("valeur_fonciere").cast(pl.Float64, strict=False)
    surface = pl.col("surface_reelle_bati").cast(pl.Float64, strict=False)
    return lf.with_columns(
        pl.col("date_mutation").str.to_date("%Y-%m-%d", strict=False),
        valeur.alias("valeur_fonciere"),
        surface.alias("surface_reelle_bati"),
        pl.when(surface > 0).then(valeur / surface).alias("prix_m2"),
        pl.col("nombre_pieces_principales").cast(pl.Float64, strict=False).round(0).cast(pl.Int64)
        .alias("nombre_pieces_principales"),
    )


def ventes_logement(lf):
    """(lignes de vente, lignes de vente de logement). Règle V1 : une mutation = un seul logement, sans local commercial."""
    ventes = typer(lf.filter(pl.col("nature_mutation") == "Vente")).with_columns(
        pl.col("type_local").is_in(LOGEMENTS).sum().over("id_mutation").alias("nb_logements"),
        (pl.col("type_local") == LOCAL_COMMERCIAL).any().over("id_mutation").alias("a_commercial"),
    )
    logements = ventes.filter(
        (pl.col("nb_logements") == 1) & ~pl.col("a_commercial") & pl.col("type_local").is_in(LOGEMENTS)
    )
    return ventes, logements


# --- Blocs ---
def bloc_0(sortie):
    """Inventaire de la source : requêtes HEAD, rien n'est téléchargé."""
    sortie.titre("Bloc 0 - Inventaire (statut, taille, Last-Modified, ETag)")
    lignes = []
    for etiquette, source in FICHIERS.items():
        url = source["url"]
        ligne = {"fichier": etiquette, "statut": None, "taille_mo": None, "last_modified": None, "etag": None, "erreur": None}
        try:
            r = requests.head(url, timeout=TIMEOUT, allow_redirects=True)
            ligne.update(
                statut=r.status_code,
                taille_mo=round(int(r.headers.get("Content-Length", 0)) / 1e6, 1),
                last_modified=r.headers.get("Last-Modified"),
                etag=r.headers.get("ETag"),
            )
        except requests.RequestException as e:
            ligne["erreur"] = str(e)[:80]
        lignes.append(ligne)
    sortie.tableau(pl.DataFrame(lignes, infer_schema_length=None))


def telecharger(url, cible, sha1_attendu):
    sha = hashlib.sha1()
    temporaire = cible.with_suffix(cible.suffix + ".tmp")
    with requests.get(url, timeout=TIMEOUT, stream=True) as r:
        r.raise_for_status()
        with open(temporaire, "wb") as f:
            for morceau in r.iter_content(chunk_size=1 << 20):
                f.write(morceau)
                sha.update(morceau)
        meta = {"url": url, "last_modified": r.headers.get("Last-Modified"), "etag": r.headers.get("ETag")}
    if sha.hexdigest() != sha1_attendu:
        temporaire.unlink()
        raise ValueError(f"sha1 {sha.hexdigest()} différent du sha1 publié {sha1_attendu}")
    temporaire.replace(cible)
    meta.update(
        taille_octets=cible.stat().st_size,
        sha1=sha.hexdigest(),
        telecharge_le=datetime.now().isoformat(timespec="seconds"),
    )
    return meta


def filtrer_departement(brut, cible):
    """Copie en flux les lignes du département (colonne code_departement) d'un fichier national. Retourne leur nombre."""
    temporaire = cible.with_suffix(".csv.tmp")
    nb = 0
    with gzip.open(brut, "rt", encoding="utf-8", newline="") as entree, \
            open(temporaire, "w", encoding="utf-8", newline="") as sortie_csv:
        lecteur, ecrivain = csv.reader(entree), csv.writer(sortie_csv)
        entete = next(lecteur)
        ecrivain.writerow(entete)
        colonne = entete.index("code_departement")
        for ligne in lecteur:
            if ligne[colonne] == DEPARTEMENT:
                ecrivain.writerow(ligne)
                nb += 1
    temporaire.replace(cible)
    return nb


def bloc_1(sortie, force):
    """Téléchargement des fichiers nationaux dans <livraison>/brut/, sha1 vérifié, puis filtre du département dans <livraison>/<étiquette>.csv.
    Manifeste (URL, dates, taille, sha1). N'écrase rien d'existant sans --force."""
    sortie.titre(f"Bloc 1 - Téléchargement dans {dossier_livraison()}")
    dossier = dossier_livraison()
    (dossier / "brut").mkdir(parents=True, exist_ok=True)
    chemin_manifeste = dossier / "manifeste.json"
    manifeste = json.loads(chemin_manifeste.read_text(encoding="utf-8")) if chemin_manifeste.exists() else {}
    nouveaux = False
    for etiquette, source in FICHIERS.items():
        brut = dossier / "brut" / f"{etiquette}.csv.gz"
        filtre = dossier / f"{etiquette}.csv"
        if filtre.exists() and not force:
            sortie.texte(f"{etiquette}: déjà prêt (--force pour refaire)")
            continue
        try:
            if force or not brut.exists():
                manifeste[etiquette] = telecharger(source["url"], brut, source["sha1"])
            lignes = filtrer_departement(brut, filtre)
        except (requests.RequestException, ValueError) as e:
            sortie.texte(f"{etiquette}: échec ({e})")
            continue
        nouveaux = True
        manifeste.setdefault(etiquette, {})["lignes_departement"] = lignes
        sortie.texte(f"{etiquette}: {lignes} lignes pour le département {DEPARTEMENT} | sha1 vérifié")
    chemin_manifeste.write_text(json.dumps(manifeste, indent=2, ensure_ascii=False), encoding="utf-8")
    if nouveaux:
        (dossier / "fusion.parquet").unlink(missing_ok=True)  # la fusion sera refaite à la prochaine lecture


def bloc_2(sortie):
    """Structure de la livraison fusionnée : colonnes, lignes par fichier et par semestre, doublons, remplissage."""
    lf = lire_livraison()
    noms = lf.collect_schema().names()
    sortie.titre("Bloc 2 - Colonnes de la livraison fusionnée")
    sortie.texte(", ".join(noms))
    sortie.titre("Bloc 2 - Lignes et dates de mutation par fichier annuel")
    typee = typer(lf)
    sortie.tableau(
        typee.group_by("fichier_annee").agg(
            pl.len().alias("lignes"),
            pl.col("id_mutation").n_unique().alias("mutations"),
            pl.col("date_mutation").min().alias("date_min"),
            pl.col("date_mutation").max().alias("date_max"),
        ).sort("fichier_annee").collect()
    )
    sortie.titre("Bloc 2 - Lignes par semestre de mutation")
    sortie.tableau(
        typee.group_by(semestre().alias("semestre")).agg(pl.len().alias("lignes")).sort("semestre").collect()
    )
    sortie.titre("Bloc 2 - Lignes entièrement identiques d'un fichier à l'autre (hors fichier_annee)")
    doublons = lf.drop("fichier_annee").collect().is_duplicated().sum()
    sortie.texte(f"{doublons} lignes en double (non retirées)")
    sortie.titre("Bloc 2 - Remplissage des colonnes clés (% non vide)")
    presentes = [c for c in COLONNES_CLES if c in noms]
    sortie.tableau(
        lf.select([(pl.col(c).is_not_null().mean() * 100).round(1).alias(c) for c in presentes]).collect().transpose(
            include_header=True, header_name="colonne", column_names=["pct_rempli"]
        )
    )
    manquantes = [c for c in COLONNES_CLES if c not in noms]
    sortie.texte(f"Colonnes attendues absentes : {manquantes if manquantes else 'aucune'}")


def lire_v1():
    """Ventes de la V1 (lecture seule de dvf_mutations)."""
    from google.cloud import bigquery
    from pipeline.bdnb.config import BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH
    from pipeline.config import BQ_TABLE_DVF

    client = bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)
    sql = (
        "SELECT id_mutation, date_mutation, code_commune, valeur_fonciere, surface_reelle_bati, prix_m2, nombre_pieces_principales "
        f"FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE_DVF}`"
    )
    return pl.DataFrame([dict(r) for r in client.query(sql).result()], infer_schema_length=None)


def par_semestre(df, suffixe):
    return df.group_by(semestre().alias("semestre")).agg(
        pl.len().alias(f"ventes_{suffixe}"),
        pl.col("prix_m2").median().round(0).alias(f"prix_m2_median_{suffixe}"),
        pl.col("surface_reelle_bati").median().alias(f"surface_mediane_{suffixe}"),
        ((pl.col("prix_m2").is_not_null() & ~pl.col("prix_m2").is_between(PRIX_M2_MIN, PRIX_M2_MAX)).mean() * 100)
        .round(1).alias(f"pct_hors_bornes_{suffixe}"),
        (pl.col("prix_m2").is_null().mean() * 100).round(1).alias(f"pct_sans_prix_{suffixe}"),
    )


def bloc_3(sortie):
    """Comparaison avec le DVF de la V1 sur la période commune."""
    ventes, logements = ventes_logement(lire_livraison())
    nouv = logements.collect()
    v1 = lire_v1()
    sortie.titre("Bloc 3 - Périodes couvertes")
    sortie.texte(f"V1 : {v1['date_mutation'].min()} -> {v1['date_mutation'].max()} ({len(v1)} ventes)")
    sortie.texte(f"Livraison : {nouv['date_mutation'].min()} -> {nouv['date_mutation'].max()} ({len(nouv)} ventes)")
    debut = max(v1["date_mutation"].min(), nouv["date_mutation"].min())
    fin = min(v1["date_mutation"].max(), nouv["date_mutation"].max())
    sortie.texte(f"Période commune : {debut} -> {fin}")
    n = nouv.filter(pl.col("date_mutation").is_between(debut, fin))
    v = v1.filter(pl.col("date_mutation").is_between(debut, fin))

    sortie.titre("Bloc 3 - Par semestre (période commune) : volumes, prix, surfaces")
    tableau = par_semestre(n, "nouv").join(par_semestre(v, "v1"), on="semestre", how="full", coalesce=True)
    sortie.tableau(
        tableau.with_columns(
            ((pl.col("ventes_nouv") - pl.col("ventes_v1")) / pl.col("ventes_v1") * 100).round(1).alias("ecart_ventes_pct")
        ).sort("semestre")
    )

    sortie.titre("Bloc 3 - Appariement par clé naturelle (les id_mutation changent à chaque livraison)")
    # La V1 écarte les prix hors bornes : on applique le même filtre à la livraison pour comparer
    n_borne = n.filter(pl.col("prix_m2").is_between(PRIX_M2_MIN, PRIX_M2_MAX))
    cle = ["date_mutation", "code_commune", "surface_reelle_bati", "nombre_pieces_principales"]
    colonnes = cle + ["valeur_fonciere"]
    rang = lambda df: df.select(colonnes).with_columns(pl.int_range(pl.len()).over(colonnes).alias("rang"))
    n_cle, v_cle = rang(n_borne), rang(v)
    jointure = colonnes + ["rang"]
    seuls_n = n_cle.join(v_cle, on=jointure, how="anti")
    seuls_v = v_cle.join(n_cle, on=jointure, how="anti")
    sortie.tableau(pl.DataFrame([{
        "ventes_livraison_dans_bornes": len(n_borne), "ventes_v1": len(v),
        "identiques": len(n_cle) - len(seuls_n), "livraison_seule": len(seuls_n), "v1_seule": len(seuls_v),
    }]))
    sortie.titre("Bloc 3 - Ventes présentes dans un seul des deux jeux, par semestre")
    sortie.tableau(
        repartition(seuls_n.with_columns(semestre().alias("semestre")), "semestre").sort("semestre")
    )
    sortie.tableau(
        repartition(seuls_v.with_columns(semestre().alias("semestre")), "semestre").sort("semestre")
    )
    sortie.titre("Bloc 3 - Valeur probablement corrigée (même date, commune, surface, pièces ; clé unique des deux côtés)")
    unique = lambda df: df.filter(pl.len().over(cle) == 1)
    corrigees = unique(seuls_n).join(unique(seuls_v), on=cle, suffix="_v1")
    rapport = (pl.col("valeur_fonciere") / pl.col("valeur_fonciere_v1")).round(3)
    sortie.tableau(corrigees.select(pl.len().alias("paires"), rapport.median().alias("rapport_median")))
    sortie.tableau(corrigees.select(cle + ["valeur_fonciere", "valeur_fonciere_v1", rapport.alias("rapport")]).sort("date_mutation"))


    sortie.titre("Bloc 3 - Mutations de vente par nombre de logements (toute la livraison)")
    sortie.tableau(repartition(
        ventes.group_by("id_mutation").agg(
            pl.col("nb_logements").first().clip(0, 3).alias("nb_logements_0_a_3_et_plus"),
            pl.col("a_commercial").first().alias("avec_local_commercial"),
        ).collect(),
        "nb_logements_0_a_3_et_plus", "avec_local_commercial",
    ).sort("nb_logements_0_a_3_et_plus", "avec_local_commercial"))


def bloc_4(sortie):
    """Remplissage surface et pièces (DVF) ; typologie et surfaces côté BDNB."""
    logements = ventes_logement(lire_livraison())[1]
    noms = logements.collect_schema().names()
    pct = lambda e: (e.fill_null(False).mean() * 100).round(1)
    mesures = [
        pl.len().alias("ventes"),
        pct(pl.col("nombre_pieces_principales") > 0).alias("pct_pieces"),
        pct(pl.col("surface_reelle_bati") > 0).alias("pct_surface_bati"),
    ]
    if "lot1_surface_carrez" in noms:
        mesures.append(pct(pl.col("lot1_surface_carrez").is_not_null()).alias("pct_carrez_lot1"))
    sortie.titre("Bloc 4 - Remplissage DVF par année et type de local")
    sortie.tableau(
        logements.group_by(pl.col("date_mutation").dt.year().alias("annee"), "type_local").agg(mesures)
        .sort("annee", "type_local").collect()
    )
    sortie.titre("Bloc 4 - Nombre de pièces (DVF, 5 et plus regroupés)")
    sortie.tableau(
        repartition(
            logements.select(pl.col("nombre_pieces_principales").clip(0, 5).alias("pieces_0_a_5_et_plus")).collect(),
            "pieces_0_a_5_et_plus",
        ).sort("pieces_0_a_5_et_plus")
    )

    dpe = pl.scan_parquet(DOSSIER_PARQUET / "dpe_logement.parquet")
    colonnes = dpe.collect_schema().names()
    sortie.titre("Bloc 4 - BDNB : colonnes candidates (typologie, pièces) de dpe_logement")
    sortie.texte(", ".join(c for c in colonnes if "typolog" in c or "piece" in c))
    if "typologie_logement" in colonnes:
        sortie.titre("Bloc 4 - BDNB : valeurs de typologie_logement")
        sortie.tableau(repartition(dpe.select("typologie_logement").collect(), "typologie_logement"))
    else:
        sortie.texte("typologie_logement absente de dpe_logement : voir les colonnes candidates ci-dessus")

    sortie.titre("Bloc 4 - Quantiles de surface : DVF (surface bâtie) et BDNB (surface habitable)")
    quantiles = [0.1, 0.25, 0.5, 0.75, 0.9]
    dvf_q = logements.select([
        pl.col("surface_reelle_bati").filter(pl.col("surface_reelle_bati") > 0).quantile(q).alias(f"q{int(q * 100)}")
        for q in quantiles
    ]).collect().with_columns(pl.lit("DVF").alias("source"))
    surface = pl.col("surface_habitable_logement").cast(pl.Float64, strict=False)
    dpe_q = dpe.select([surface.filter(surface > 0).quantile(q).alias(f"q{int(q * 100)}") for q in quantiles]) \
        .collect().with_columns(pl.lit("BDNB (DPE)").alias("source"))
    sortie.tableau(pl.concat([dvf_q, dpe_q]))


# --- Rattachement à blanc ---
def normaliser_voie(texte):
    if texte is None:
        return None
    t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().upper()
    mots = [ABREVIATIONS.get(m, m) for m in re.sub(r"[^A-Z0-9 ]", " ", t).split()]
    return " ".join(sorted(m for m in mots if m not in MOTS_VIDES))


def charger_bdnb():
    """Tables de correspondance BDNB : parcelle -> bâtiments, clé A -> bâtiments, clé B -> bâtiments, adresses."""
    rel_p = lire_bdnb("rel_batiment_groupe_parcelle", ["batiment_groupe_id", "parcelle_id", "parcelle_principale"]) \
        .with_columns(pl.col("parcelle_principale").cast(pl.Int64, strict=False).alias("principal"))
    par = rel_p.group_by("parcelle_id").agg(
        pl.col("batiment_groupe_id").unique().alias("cands_p"),
        (pl.col("principal") == 1).sum().alias("nb_principal"),
        pl.col("batiment_groupe_id").filter(pl.col("principal") == 1).first().alias("bat_principal"),
    )

    adresse = lire_bdnb(
        "adresse", ["cle_interop_adr", "numero", "rep", "type_voie", "nom_voie", "code_commune_insee", "source"]
    ).with_columns(
        pl.col("cle_interop_adr").str.to_lowercase(),
        pl.col("numero").cast(pl.Int64, strict=False).alias("numero_i"),
        pl.col("rep").fill_null("").str.to_lowercase().str.slice(0, 1).alias("rep_l"),
        (pl.col("type_voie").fill_null("") + pl.lit(" ") + pl.col("nom_voie").fill_null(""))
        .map_elements(normaliser_voie, return_dtype=pl.String).alias("voie_n"),
    ).with_columns(
        pl.concat_str(
            [pl.col("code_commune_insee"), pl.col("numero_i").cast(pl.String), pl.col("rep_l"), pl.col("voie_n")],
            separator="|",
        ).alias("cle_b")
    )
    rel_adr = lire_bdnb("rel_batiment_groupe_adresse", ["batiment_groupe_id", "cle_interop_adr"]) \
        .with_columns(pl.col("cle_interop_adr").str.to_lowercase())
    adr_a = rel_adr.group_by("cle_interop_adr").agg(pl.col("batiment_groupe_id").unique().alias("cands_a1"))
    adr_b = (
        adresse.select("cle_interop_adr", "cle_b").filter(pl.col("cle_b").is_not_null())
        .join(rel_adr, on="cle_interop_adr")
        .group_by("cle_b").agg(pl.col("batiment_groupe_id").unique().alias("cands_b"))
    )
    return par, adr_a, adr_b, adresse


def cles_dvf(df):
    numero = pl.col("adresse_numero").cast(pl.Int64, strict=False)
    suffixe = pl.col("adresse_suffixe").fill_null("").str.to_lowercase().str.slice(0, 1)
    cle_a = pl.concat_str(
        [pl.col("code_commune"), pl.col("adresse_code_voie").str.to_lowercase(), numero.cast(pl.String).str.zfill(5)],
        separator="_",
    ) + pl.when(suffixe != "").then(pl.lit("_") + suffixe).otherwise(pl.lit(""))
    cle_b = pl.concat_str(
        [pl.col("code_commune"), numero.cast(pl.String), suffixe,
         pl.col("adresse_nom_voie").map_elements(normaliser_voie, return_dtype=pl.String)],
        separator="|",
    )
    return df.with_columns(cle_a.alias("cle_a"), cle_b.alias("cle_b"))


def rattacher(df, par, adr_a, adr_b):
    """Candidats par parcelle (cands_p) et par adresse (cands_a : clé A, sinon clé B), choix si unique, méthode."""
    df = (
        cles_dvf(df)
        .join(par, left_on="id_parcelle", right_on="parcelle_id", how="left")
        .join(adr_a, left_on="cle_a", right_on="cle_interop_adr", how="left")
        .join(adr_b, on="cle_b", how="left")
        .with_columns(
            pl.coalesce("cands_a1", "cands_b").alias("cands_a"),
            pl.when(pl.col("cands_a1").is_not_null()).then(pl.lit("cle"))
            .when(pl.col("cands_b").is_not_null()).then(pl.lit("texte")).alias("origine_a"),
        )
        .with_columns(
            pl.when(pl.col("cands_p").is_null()).then(pl.lit("absente"))
            .when(pl.col("cands_p").list.len() == 1).then(pl.lit("unique"))
            .when(pl.col("nb_principal") == 1).then(pl.lit("principale"))
            .otherwise(pl.lit("ambigue")).alias("statut_p"),
            pl.when(pl.col("cands_a").is_null()).then(pl.lit("absente"))
            .when(pl.col("cands_a").list.len() == 1).then(pl.lit("unique"))
            .otherwise(pl.lit("ambigue")).alias("statut_a"),
        )
        .with_columns(
            pl.when(pl.col("statut_p") == "unique").then(pl.col("cands_p").list.first())
            .when(pl.col("statut_p") == "principale").then(pl.col("bat_principal")).alias("bat_p"),
            pl.when(pl.col("statut_a") == "unique").then(pl.col("cands_a").list.first()).alias("bat_a"),
        )
    )
    return df.with_columns(
        pl.when(pl.col("bat_p").is_not_null() & pl.col("bat_a").is_not_null())
        .then(pl.when(pl.col("bat_p") == pl.col("bat_a")).then(pl.lit("concordent")).otherwise(pl.lit("divergent")))
        .when(pl.col("bat_p").is_not_null()).then(pl.lit("parcelle seule"))
        .when(pl.col("bat_a").is_not_null()).then(pl.lit("adresse seule"))
        .otherwise(pl.lit("aucune")).alias("methode")
    )


def bloc_5(sortie):
    """Rattachement à blanc des ventes de logement aux bâtiments BDNB (rien n'est chargé)."""
    logements = ventes_logement(lire_livraison())[1].collect()
    par, adr_a, adr_b, adresse = charger_bdnb()
    r = rattacher(logements, par, adr_a, adr_b)
    sortie.texte(f"{len(r)} ventes de logement")

    sortie.titre("Bloc 5 - Par parcelle : statut")
    sortie.tableau(repartition(r, "statut_p"))
    sortie.titre("Bloc 5 - Par parcelle : nombre de bâtiments candidats (5 et plus regroupés)")
    sortie.tableau(repartition(
        r.filter(pl.col("cands_p").is_not_null()).select(pl.col("cands_p").list.len().clip(1, 5).alias("batiments_0_a_5")),
        "batiments_0_a_5",
    ).sort("batiments_0_a_5"))
    sortie.titre("Bloc 5 - Clés d'adresse : construites et retrouvées (A : format BAN reconstruit, B : texte normalisé)")
    sortie.tableau(r.select(
        pl.len().alias("ventes"),
        pl.col("cle_a").is_not_null().sum().alias("cle_a_construite"),
        pl.col("cands_a1").is_not_null().sum().alias("cle_a_trouvee"),
        pl.col("cle_b").is_not_null().sum().alias("cle_b_construite"),
        pl.col("cands_b").is_not_null().sum().alias("cle_b_trouvee"),
    ))
    sortie.titre("Bloc 5 - Par adresse : origine de la clé retenue et statut")
    sortie.tableau(repartition(r, "origine_a", "statut_a"))
    sortie.titre("Bloc 5 - Gain de l'adresse sur les ventes sans bâtiment unique par parcelle (absente ou ambiguë)")
    sortie.tableau(repartition(r.filter(pl.col("statut_p").is_in(["absente", "ambigue"])), "statut_a"))
    sortie.titre("Bloc 5 - Méthode de rattachement (parcelle et adresse, choix uniques seulement)")
    sortie.tableau(repartition(r, "methode"))
    sortie.titre("Bloc 5 - Adresses BDNB par source et part des clés sans '_' (clés d'origine Arcep)")
    sortie.tableau(repartition(adresse, "source"))
    sortie.tableau(adresse.select(
        (~pl.col("cle_interop_adr").str.contains("_")).mean().mul(100).round(1).alias("pct_cles_sans_tiret")
    ))

    chemin = dossier_livraison() / "rattachement_a_blanc.parquet"
    r.select(
        "id_mutation", "date_mutation", "valeur_fonciere", "id_parcelle", "statut_p", "bat_p",
        "origine_a", "statut_a", "bat_a", "methode",
    ).write_parquet(chemin)
    sortie.texte(f"Parquet de travail écrit : {chemin}")


def bloc_6(sortie):
    """Validation sur bdnb_dvf_representatif : même date et même prix, même bâtiment ?"""
    ventes = ventes_logement(lire_livraison())[0].collect()
    par, adr_a, adr_b, _ = charger_bdnb()
    r = rattacher(ventes, par, adr_a, adr_b)
    debut, fin = r["date_mutation"].min(), r["date_mutation"].max()
    rep = lire_bdnb(
        "batiment_groupe_dvf_open_representatif", ["batiment_groupe_id", "date_mutation", "valeur_fonciere"]
    ).with_columns(
        pl.col("date_mutation").str.slice(0, 10).str.to_date("%Y/%m/%d", strict=False),
        pl.col("valeur_fonciere").cast(pl.Float64, strict=False),
    ).filter(pl.col("date_mutation").is_between(debut, fin)).with_row_index("rep_id")
    mutations = r.select("id_mutation", "date_mutation", "valeur_fonciere").unique()
    paires = rep.join(mutations, on=["date_mutation", "valeur_fonciere"], how="inner")
    sortie.titre("Bloc 6 - Ventes représentatives de la BDNB sur la période de la livraison")
    sortie.tableau(pl.DataFrame([{
        "periode_debut": debut, "periode_fin": fin, "representatives": len(rep),
        "retrouvees_date_et_prix": paires["rep_id"].n_unique(),
        "non_retrouvees": len(rep) - paires["rep_id"].n_unique(),
    }]))

    tables = {
        "parcelle": (
            r.select("id_mutation", pl.col("cands_p").alias("bat")).explode("bat").drop_nulls().unique(),
            r.filter(pl.col("bat_p").is_not_null()).select("id_mutation", pl.col("bat_p").alias("bat")).unique(),
        ),
        "adresse": (
            r.select("id_mutation", pl.col("cands_a").alias("bat")).explode("bat").drop_nulls().unique(),
            r.filter(pl.col("bat_a").is_not_null()).select("id_mutation", pl.col("bat_a").alias("bat")).unique(),
        ),
    }
    resultats = {}
    for nom, (tous, choix) in tables.items():
        ids_choix = choix["id_mutation"].unique()
        p = (
            paires
            .join(tous.with_columns(pl.lit(True).alias("dans_cands")),
                  left_on=["id_mutation", "batiment_groupe_id"], right_on=["id_mutation", "bat"], how="left")
            .join(choix.with_columns(pl.lit(True).alias("dans_choix")),
                  left_on=["id_mutation", "batiment_groupe_id"], right_on=["id_mutation", "bat"], how="left")
            .with_columns(pl.col("id_mutation").is_in(ids_choix.implode()).alias("a_choix"))
        )
        resultats[nom] = p.group_by("rep_id").agg(
            pl.col("dans_choix").any(), pl.col("dans_cands").any(), pl.col("a_choix").any()
        ).with_columns(
            pl.when(pl.col("dans_choix")).then(pl.lit("1 bon bâtiment, rattachement unique"))
            .when(pl.col("a_choix")).then(pl.lit("2 autre bâtiment choisi (erreur)"))
            .when(pl.col("dans_cands")).then(pl.lit("3 ambigu, bon bâtiment parmi les candidats"))
            .otherwise(pl.lit("4 sans choix, bon bâtiment non candidat")).alias("classe")
        )
        sortie.titre(f"Bloc 6 - Validation par {nom} (sur les représentatives retrouvées)")
        sortie.tableau(repartition(resultats[nom], "classe").sort("classe"))

    ensemble = resultats["parcelle"].join(resultats["adresse"], on="rep_id", suffix="_a")
    sortie.titre("Bloc 6 - Au moins une des deux méthodes donne le bon bâtiment (choix unique)")
    sortie.tableau(ensemble.select(
        pl.len().alias("retrouvees"),
        (pl.col("dans_choix") | pl.col("dans_choix_a")).sum().alias("bon_batiment"),
        ((pl.col("dans_choix") | pl.col("dans_choix_a")).mean() * 100).round(1).alias("pct"),
    ))


BLOCS = {0: bloc_0, 2: bloc_2, 3: bloc_3, 4: bloc_4, 5: bloc_5, 6: bloc_6}


def main():
    parser = argparse.ArgumentParser(description="Exploration de la livraison DVF Etalab")
    parser.add_argument("--bloc", default="all", choices=[str(i) for i in range(7)] + ["all"])
    parser.add_argument("--rapport", action="store_true", help="écrire la sortie complète dans pipeline/data/bdnb/rapports/")
    parser.add_argument("--lignes", type=int, default=LIGNES_TERMINAL, help="lignes affichées par tableau dans le terminal")
    parser.add_argument("--force", action="store_true", help="bloc 1 : retélécharger les fichiers déjà présents")
    args = parser.parse_args()

    for numero in range(7) if args.bloc == "all" else [int(args.bloc)]:
        sortie = Sortie(args.lignes)
        if numero == 1:
            bloc_1(sortie, args.force)
        else:
            BLOCS[numero](sortie)
        if args.rapport:
            sortie.ecrire(f"{numero}_dvf")


if __name__ == "__main__":
    main()

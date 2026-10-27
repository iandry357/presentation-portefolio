"""Exploration complémentaire de la BDNB (dept. 75) : tables non chargées, étape 0 de « Géoplateforme et Émergence BDNB ».

Usage : python scripts\\explore_bdnb_complement.py --bloc 1|...|9|all [--rapport] [--lignes 20]
        python scripts\\explore_bdnb_complement.py --dico COLONNE [COLONNE ...] [--table TABLE] [--rapport]
Blocs : 1 volumes et grain · 2 bâti · 3 copropriétés · 4 risques et patrimoine · 5 consommation réelle
        6 travaux et rénovation · 7 tables secondaires · 8 époque (fichiers fonciers contre DPE)
        9 débordement BDNB contre Géorisques (appels réseau, jamais inclus dans « all »)
Lit les Parquet s'ils existent, sinon les CSV (types non lus). Terminal : les --lignes premières lignes ; fichier (--rapport) : la totalité.
"""
import argparse
import re
import time
import urllib.parse
import urllib.request
import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from math import atan, atan2, cos, degrees, hypot, log, pi, radians, sin, sqrt, tan

import polars as pl

# --- Paramètres ---
DOSSIER_BDNB = Path(__file__).resolve().parent.parent / "pipeline" / "data" / "bdnb"
DOSSIER_CSV = DOSSIER_BDNB / "bdnb_dep75_csv" / "csv"
DOSSIER_PARQUET = DOSSIER_BDNB / "parquet"
DOSSIER_RAPPORTS = DOSSIER_BDNB / "rapports"
LIGNES_TERMINAL = 20
MODALITES_MAX = 15            # une colonne à 15 valeurs distinctes ou moins est décrite par ses modalités
LONGUEUR_DESCRIPTION = 110
SENSIBLE = re.compile(r"denomination|siren|siret|l_nom|nom_pdl|nom_copro|nom_demandeur|prenom", re.IGNORECASE)

# Tables par bloc : nom exact, sinon toute table dont le nom le contient
TABLES_BLOCS = {
    "2": ["batiment_groupe_ffo_bat", "batiment_groupe_bdtopo_bat", "batiment_construction"],
    "3": ["batiment_groupe_rnc"],
    "4": ["batiment_groupe_risques", "batiment_groupe_urbanisme", "batiment_groupe_merimee"],
    "5": ["batiment_groupe_dle_elec_multimillesime", "dle_gaz", "dle_reseaux"],
    "6": ["sitadel", "parcelle_sitadel", "indicateur_reseau_chaud_froid", "contrainte_opportunite_renovation"],
    "7": ["audit_energetique_logement", "rpls", "grand_iris_icu_sat4bdnb", "dpe_tertiaire", "bpe", "qpv", "certification", "hthd"],
}

# Bloc 2 et 8 : année de construction des fichiers fonciers
TABLE_FFO = "batiment_groupe_ffo_bat"
COLONNE_ANNEE = "annee_construction"
TOP_ANNEES = 15

# Bloc 8 : même sélection DPE et même table de périodes que pipeline/loyers (config.py), recopiées ici
ARRETE_2021 = 1
SUFFIXE_TYPE_DPE = "logement"
METHODE_DPE = "3cl"
COLONNE_PERIODE = "periode_construction_dpe"
PERIODES_EPOQUES = {
    "avant 1948": ("Avant 1946", True), "1948-1974": ("1946-1970", True), "1975-1977": ("1971-1990", False),
    "1978-1982": ("1971-1990", False), "1983-1988": ("1971-1990", False), "1989-2000": ("Apres 1990", True),
    "2001-2005": ("Apres 1990", False), "2006-2012": ("Apres 1990", False), "2013-2021": ("Apres 1990", False),
    "après 2021": ("Apres 1990", False),
}

# Bloc 9 : Géorisques
TABLE_RISQUES = "batiment_groupe_risques"
URL_GEORISQUES = "https://georisques.gouv.fr/api/v1/resultats_rapport_risque"
EN_TETES = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept-Encoding": "identity",
}
N_PAR_MODALITE = 25
GRAINE = 42
PAUSE_SEC = 1.0
NB_TENTATIVES = 5
DELAI_SEC = 10
LAT_MIN, LAT_MAX = 48.80, 48.92
LON_MIN, LON_MAX = 2.20, 2.50
# Lambert-93 (RGF93, EPSG:2154) : projection conique conforme, ellipsoïde GRS80 ; adresse.WKT est en Lambert-93
L93_A, L93_E = 6378137.0, 0.0818191910428158
L93_PHI1, L93_PHI2, L93_PHI0, L93_LAMBDA0 = radians(44), radians(49), radians(46.5), radians(3)
L93_X0, L93_Y0 = 700000.0, 6600000.0
POINT_VERIF = ((652461.22, 6862050.56), (2.352092, 48.856737))  # (x, y) -> (lon, lat), adresse renvoyée par la Géoplateforme
TOLERANCE_VERIF = 1e-4  # degrés
REGEX_POINT = r"POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)"

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
        chemin = DOSSIER_RAPPORTS / f"{horodatage}_complement_bloc{nom_bloc}.txt"
        chemin.write_text("\n".join(self.contenu), encoding="utf-8")
        print(f"\nRapport écrit : {chemin}")


def ouvrir(stem):
    """LazyFrame de la table (Parquet, sinon CSV en texte), None si elle n'existe pas."""
    parquet = DOSSIER_PARQUET / f"{stem}.parquet"
    if parquet.exists():
        return pl.scan_parquet(parquet)
    csv = DOSSIER_CSV / f"{stem}.csv"
    if csv.exists():
        return pl.scan_csv(csv, separator=";", infer_schema_length=0)
    return None


def resoudre(motif):
    """Tables dont le nom est exactement le motif, sinon dont le nom le contient."""
    stems = sorted({p.stem for p in DOSSIER_PARQUET.glob("*.parquet")} | {c.stem for c in DOSSIER_CSV.glob("*.csv")})
    return [motif] if motif in stems else [s for s in stems if motif in s]


@lru_cache(maxsize=1)
def definitions():
    """(table, colonne) -> (description, unité) d'après metadonnees_colonne.csv."""
    chemin = DOSSIER_CSV / "metadonnees_colonne.csv"
    if not chemin.exists():
        return {}
    dico = pl.read_csv(chemin, separator=";", infer_schema_length=0)
    return {(r["nom_table"], r["nom_colonne"]): (r["description"] or "", r["unite"] or "") for r in dico.iter_rows(named=True)}


def profil(sortie, stem, detail=True):
    """Remplissage, valeurs distinctes et définition de chaque colonne ; en détail : modalités et quantiles."""
    lf = ouvrir(stem)
    schema = lf.collect_schema()
    n = lf.select(pl.len()).collect().item()
    source = "Parquet" if (DOSSIER_PARQUET / f"{stem}.parquet").exists() else "CSV, types non lus"
    sortie.titre(f"{stem} : {n} lignes, {len(schema)} colonnes [{source}]")
    if n == 0:
        return
    nuls = lf.select(pl.all().null_count()).collect().to_dicts()[0]
    uniques = lf.select(pl.all().n_unique()).collect().to_dicts()[0]
    dico = definitions()
    lignes = []
    for nom, type_ in schema.items():
        description, unite = dico.get((stem, nom), ("", ""))
        lignes.append({
            "colonne": nom, "type": str(type_), "non_nuls_pct": round((n - nuls[nom]) / n * 100, 1),
            "valeurs_distinctes": uniques[nom], "unite": unite, "definition": description[:LONGUEUR_DESCRIPTION],
        })
    sortie.tableau(pl.DataFrame(lignes).sort("non_nuls_pct"))
    if not detail:
        return

    morceaux = []
    for nom in schema:
        if SENSIBLE.search(nom) or uniques[nom] > MODALITES_MAX:
            continue
        morceaux.append(
            lf.group_by(nom).agg(pl.len().alias("lignes")).sort("lignes", descending=True)
            .select(pl.lit(nom).alias("colonne"), pl.col(nom).cast(pl.Utf8).alias("valeur"), pl.col("lignes"))
            .with_columns((pl.col("lignes") / n * 100).round(1).alias("pct")).collect()
        )
    if morceaux:
        sortie.titre(f"{stem} : modalités (colonnes à {MODALITES_MAX} valeurs distinctes ou moins)")
        sortie.tableau(pl.concat(morceaux))

    quantiles = []
    for nom, type_ in schema.items():
        if SENSIBLE.search(nom) or not type_.is_numeric() or uniques[nom] <= MODALITES_MAX:
            continue
        c = pl.col(nom).cast(pl.Float64)
        ligne = lf.select(
            c.min().alias("min"), c.quantile(0.05).alias("p5"), c.quantile(0.5).alias("p50"),
            c.quantile(0.95).alias("p95"), c.max().alias("max"),
        ).collect().to_dicts()[0]
        quantiles.append({"colonne": nom, **ligne})
    if quantiles:
        sortie.titre(f"{stem} : quantiles des colonnes numériques")
        sortie.tableau(pl.DataFrame(quantiles))


def bloc_profil(sortie, bloc, detail=True):
    for motif in TABLES_BLOCS[bloc]:
        stems = resoudre(motif)
        if not stems:
            sortie.titre(f"{motif} : introuvable (ni Parquet ni CSV)")
        for stem in stems:
            profil(sortie, stem, detail)


def bloc_1(sortie):
    """Volumes et grain : lignes, colonnes de lien (bâtiment, parcelle, adresse) et lignes par clé."""
    lignes, absentes = [], []
    for bloc, motifs in TABLES_BLOCS.items():
        for motif in motifs:
            stems = resoudre(motif)
            if not stems:
                absentes.append(motif)
            for stem in stems:
                lf = ouvrir(stem)
                noms = lf.collect_schema().names()
                ligne = {"bloc": bloc, "table": stem, "lignes": lf.select(pl.len()).collect().item(), "colonnes": len(noms)}
                for cle in ("batiment_groupe_id", "parcelle_id", "cle_interop_adr"):
                    ligne[f"{cle}_distincts"] = lf.select(pl.col(cle).n_unique()).collect().item() if cle in noms else None
                lignes.append(ligne)
    sortie.titre("Bloc 1 - Volumes et grain (lignes comparées aux clés distinctes ; vide = colonne absente)")
    sortie.tableau(pl.DataFrame(lignes, infer_schema_length=None))
    if absentes:
        sortie.texte(f"Introuvables : {absentes}")


def bloc_2(sortie):
    bloc_profil(sortie, "2")
    ffo = ouvrir(TABLE_FFO)
    if ffo is None or COLONNE_ANNEE not in ffo.collect_schema().names():
        sortie.texte(f"{TABLE_FFO}.{COLONNE_ANNEE} absente : voir --dico annee --table {TABLE_FFO}")
        return
    annees = ffo.select(pl.col(COLONNE_ANNEE).cast(pl.Int64, strict=False).alias("annee")).filter(pl.col("annee").is_not_null())
    n = annees.select(pl.len()).collect().item()
    sortie.titre(f"Bloc 2 - {COLONNE_ANNEE} : années les plus fréquentes (sur {n} valeurs ; une pointe signale une valeur plancher)")
    sortie.tableau(
        annees.group_by("annee").agg(pl.len().alias("batiments")).sort("batiments", descending=True).head(TOP_ANNEES)
        .with_columns((pl.col("batiments") / n * 100).round(1).alias("pct")).collect()
    )


def bloc_3(sortie):
    bloc_profil(sortie, "3")


def bloc_4(sortie):
    bloc_profil(sortie, "4")


def bloc_5(sortie):
    bloc_profil(sortie, "5")
    sortie.texte(
        "\nÀ lire dans les définitions ci-dessus : grain (bâtiment, adresse ou point de livraison), millésimes, unité "
        "(kWh d'énergie finale ?), colonnes de secret statistique (valeurs vides ou indicateur de masquage)."
    )


def bloc_6(sortie):
    bloc_profil(sortie, "6")


def bloc_7(sortie):
    bloc_profil(sortie, "7", detail=False)


def epoque_annee(col):
    """Époque de l'encadrement d'après une année (bornes à confirmer avec les libellés du jeu)."""
    return (
        pl.when(col < 1946).then(pl.lit("Avant 1946"))
        .when(col <= 1970).then(pl.lit("1946-1970"))
        .when(col <= 1990).then(pl.lit("1971-1990"))
        .otherwise(pl.lit("Apres 1990"))
    )


def bloc_8(sortie):
    """Époque d'un bâtiment : année des fichiers fonciers contre période DPE majoritaire (règle actuelle des loyers)."""
    ffo, dpe, rel, batiments = ouvrir(TABLE_FFO), ouvrir("dpe_logement"), ouvrir("rel_batiment_groupe_dpe_logement"), ouvrir("batiment_groupe")
    if any(t is None for t in (ffo, dpe, rel, batiments)) or COLONNE_ANNEE not in ffo.collect_schema().names():
        sortie.texte(f"Tables ou colonne manquantes ({TABLE_FFO}.{COLONNE_ANNEE}, dpe_logement, rel_batiment_groupe_dpe_logement, batiment_groupe)")
        return

    annees = (
        ffo.select("batiment_groupe_id", pl.col(COLONNE_ANNEE).cast(pl.Int64, strict=False).alias("annee"))
        .filter(pl.col("annee") > 0)
        .with_columns(epoque_annee(pl.col("annee")).alias("epoque_ff"))
        .unique(subset="batiment_groupe_id")
    )
    selection = dpe.filter(
        (pl.col("arrete_2021").cast(pl.Int64, strict=False) == ARRETE_2021)
        & pl.col("type_dpe").str.ends_with(SUFFIXE_TYPE_DPE)
        & pl.col("type_dpe").str.contains(METHODE_DPE, literal=True)
        & (pl.col("surface_habitable_logement").cast(pl.Float64, strict=False) > 0)
    ).select("identifiant_dpe", pl.col(COLONNE_PERIODE).alias("periode"))
    comptes = (
        selection.join(rel.select("identifiant_dpe", "batiment_groupe_id"), on="identifiant_dpe")
        .filter(pl.col("periode").is_not_null())
        .group_by("batiment_groupe_id", "periode").agg(pl.len().alias("n"))
        .with_columns(pl.col("n").max().over("batiment_groupe_id").alias("n_max"))
    )
    majoritaires = (
        comptes.filter(pl.col("n") == pl.col("n_max"))
        .group_by("batiment_groupe_id").agg(pl.len().alias("ex_aequo"), pl.col("periode").first().alias("periode"))
    )
    carte = pl.DataFrame({
        "periode": list(PERIODES_EPOQUES), "epoque_dpe": [v[0] for v in PERIODES_EPOQUES.values()],
        "periode_ambigue": [v[1] for v in PERIODES_EPOQUES.values()],
    }).lazy()
    tout = (
        batiments.select("batiment_groupe_id").join(annees, on="batiment_groupe_id", how="left")
        .join(majoritaires.filter(pl.col("ex_aequo") == 1), on="batiment_groupe_id", how="left")
        .join(carte, on="periode", how="left")
    ).collect()

    deux = tout.filter(pl.col("epoque_ff").is_not_null() & pl.col("epoque_dpe").is_not_null())
    concordants = deux.filter(pl.col("epoque_ff") == pl.col("epoque_dpe")).height
    ambigus = deux.filter(pl.col("periode_ambigue"))
    sortie.titre("Bloc 8 - Couverture (bâtiments de batiment_groupe ; mesure par bâtiment, non pondérée par les ventes)")
    sortie.tableau(pl.DataFrame({
        "mesure": [
            "bâtiments", "avec année des fichiers fonciers", "avec période DPE majoritaire sans égalité",
            "avec les deux", "avec année seule (gain de couverture)", "avec période DPE seule (perte si l'année remplace)",
            "concordance d'époque quand les deux existent (%)",
            "période DPE ambiguë : part des bâtiments avec les deux (%)",
            "période DPE ambiguë : concordance (%)",
        ],
        "valeur": [str(v) for v in (
            tout.height, tout["annee"].is_not_null().sum(), tout["epoque_dpe"].is_not_null().sum(), deux.height,
            tout.filter(pl.col("epoque_ff").is_not_null() & pl.col("epoque_dpe").is_null()).height,
            tout.filter(pl.col("epoque_ff").is_null() & pl.col("epoque_dpe").is_not_null()).height,
            round(concordants / deux.height * 100, 1) if deux.height else None,
            round(ambigus.height / deux.height * 100, 1) if deux.height else None,
            round(ambigus.filter(pl.col("epoque_ff") == pl.col("epoque_dpe")).height / ambigus.height * 100, 1) if ambigus.height else None,
        )],
    }))
    sortie.titre("Bloc 8 - Matrice : époque d'après l'année (lignes) et d'après la période DPE (colonnes), bâtiments avec les deux")
    sortie.tableau(deux.group_by("epoque_ff", "epoque_dpe").agg(pl.len().alias("batiments")).sort("epoque_ff", "epoque_dpe"))

def _m(phi):
    return cos(phi) / sqrt(1 - L93_E ** 2 * sin(phi) ** 2)


def _t(phi):
    return tan(pi / 4 - phi / 2) / ((1 - L93_E * sin(phi)) / (1 + L93_E * sin(phi))) ** (L93_E / 2)


L93_N = (log(_m(L93_PHI1)) - log(_m(L93_PHI2))) / (log(_t(L93_PHI1)) - log(_t(L93_PHI2)))
L93_F = _m(L93_PHI1) / (L93_N * _t(L93_PHI1) ** L93_N)
L93_RHO0 = L93_A * L93_F * _t(L93_PHI0) ** L93_N


def lambert93_vers_wgs84(x, y):
    """(x, y) Lambert-93 -> (longitude, latitude) WGS84, projection conique conforme inversée."""
    dx, dy = x - L93_X0, L93_RHO0 - (y - L93_Y0)
    t = (hypot(dx, dy) / (L93_A * L93_F)) ** (1 / L93_N)
    phi = pi / 2 - 2 * atan(t)
    for _ in range(10):
        phi = pi / 2 - 2 * atan(t * ((1 - L93_E * sin(phi)) / (1 + L93_E * sin(phi))) ** (L93_E / 2))
    return degrees(atan2(dx, dy) / L93_N + L93_LAMBDA0), degrees(phi)


def interroger_georisques(lat, lon):
    """Statut à l'adresse du risque d'inondation du rapport Géorisques, (None, erreur) si l'API échoue."""
    url = URL_GEORISQUES + "?" + urllib.parse.urlencode({"latlon": f"{lon},{lat}"})
    for _ in range(NB_TENTATIVES):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=EN_TETES), timeout=DELAI_SEC) as r:
                data = json.loads(r.read())
            break
        except Exception as e:
            erreur = str(e)
            time.sleep(PAUSE_SEC)
    else:
        return None, erreur
    for bloc in (data.get("risquesNaturels"), data.get("risquesTechnologiques")):
        for risque in (bloc or {}).values():
            if "inondation" in (risque.get("libelle") or "").lower():
                return (risque.get("libelleStatutAdresse") if risque.get("present") else "non présent au rapport"), None
    return "inondation absente du rapport", None


def bloc_9(sortie, n_par_modalite, col_inond, col_lon, col_lat):
    """Échantillon de bâtiments par modalité du débordement BDNB, comparé au statut d'inondation de Géorisques à leur adresse.
    Coordonnées : colonnes lon / lat de adresse si elles existent, sinon le WKT Lambert-93 converti en WGS84."""
    risques, adresse, rel_adr = ouvrir(TABLE_RISQUES), ouvrir("adresse"), ouvrir("rel_batiment_groupe_adresse")
    if any(t is None for t in (risques, adresse, rel_adr)):
        sortie.texte("Tables manquantes (batiment_groupe_risques, adresse, rel_batiment_groupe_adresse)")
        return
    noms = risques.collect_schema().names()
    candidates = [c for c in noms if re.search(r"inond|debord", c, re.IGNORECASE)]
    sortie.texte(f"Colonnes d'inondation candidates dans {TABLE_RISQUES} : {candidates}")
    col = col_inond or next((c for c in candidates if "debord" in c.lower()), candidates[0] if candidates else None)
    noms_adr = adresse.collect_schema().names()
    lon = col_lon or next((c for c in ("longitude", "lon", "long") if c in noms_adr), None)
    lat = col_lat or next((c for c in ("latitude", "lat") if c in noms_adr), None)
    avec_lonlat = bool(lon and lat)
    if not col or not (avec_lonlat or "WKT" in noms_adr):
        sortie.texte(f"Colonne d'inondation ({col}) ou coordonnées introuvables ; colonnes de adresse : {noms_adr}")
        return
    if avec_lonlat:
        sortie.texte(f"Colonne retenue : {col} ; coordonnées : {lon}, {lat}")
        coordonnees = [pl.col(lon).cast(pl.Float64, strict=False).alias("lon"), pl.col(lat).cast(pl.Float64, strict=False).alias("lat")]
        cle_coordonnee = "lon"
    else:
        trouve = lambert93_vers_wgs84(*POINT_VERIF[0])
        if max(abs(trouve[0] - POINT_VERIF[1][0]), abs(trouve[1] - POINT_VERIF[1][1])) > TOLERANCE_VERIF:
            sortie.texte(f"Conversion Lambert-93 invalide : {trouve} au lieu de {POINT_VERIF[1]}")
            return
        sortie.texte(f"Colonne retenue : {col} ; coordonnées : WKT Lambert-93 converti (point de contrôle retrouvé : {trouve})")
        coordonnees = [
            pl.col("WKT").str.extract(REGEX_POINT, 1).cast(pl.Float64, strict=False).alias("x"),
            pl.col("WKT").str.extract(REGEX_POINT, 2).cast(pl.Float64, strict=False).alias("y"),
        ]
        cle_coordonnee = "x"

    adresses = (
        rel_adr.select("batiment_groupe_id", "cle_interop_adr").unique(subset="batiment_groupe_id", keep="first")
        .join(adresse.select("cle_interop_adr", *coordonnees), on="cle_interop_adr")
    )
    points = (
        risques.select("batiment_groupe_id", pl.col(col).cast(pl.Utf8).fill_null("(vide)").alias("modalite"))
        .join(adresses, on="batiment_groupe_id")
        .filter(pl.col(cle_coordonnee).is_not_null())
        .collect()
    )
    echantillon = pl.concat([
        points.filter(pl.col("modalite") == m).sample(n=min(n_par_modalite, points.filter(pl.col("modalite") == m).height), seed=GRAINE)
        for m in points["modalite"].unique().sort()
    ])
    if not avec_lonlat:
        paires = [lambert93_vers_wgs84(x, y) for x, y in zip(echantillon["x"], echantillon["y"])]
        echantillon = echantillon.with_columns(pl.Series("lon", [p[0] for p in paires]), pl.Series("lat", [p[1] for p in paires]))
    avant = echantillon.height
    echantillon = echantillon.filter(pl.col("lat").is_between(LAT_MIN, LAT_MAX) & pl.col("lon").is_between(LON_MIN, LON_MAX))
    sortie.texte(f"{echantillon.height} points à interroger ({avant - echantillon.height} hors emprise de Paris écartés), environ {round(echantillon.height * PAUSE_SEC / 60, 1)} min")

    resultats = []
    for i, ligne in enumerate(echantillon.iter_rows(named=True), 1):
        statut, erreur = interroger_georisques(ligne["lat"], ligne["lon"])
        resultats.append({"modalite_bdnb": ligne["modalite"], "statut_georisques": statut or f"ERREUR : {erreur}"[:60]})
        if i % 10 == 0:
            print(f"  {i}/{echantillon.height}")
        time.sleep(PAUSE_SEC)
    sortie.titre(f"Bloc 9 - {col} (BDNB) contre statut d'inondation à l'adresse (Géorisques)")
    sortie.tableau(pl.DataFrame(resultats).group_by("modalite_bdnb", "statut_georisques").agg(pl.len().alias("points")).sort("modalite_bdnb", "points", descending=[False, True]))


def consulter_dico(sortie, noms, table, limite):
    """Définition des colonnes dont le nom contient l'un des motifs (metadonnees_colonne.csv)."""
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
            sortie.texte(f"Modalités : {ligne['modalite_enum'][:300]}")
    if trouvees.height > limite:
        print(f"\n{trouvees.height - limite} autre(s) : augmenter --lignes ou filtrer avec --table")


BLOCS = {"1": bloc_1, "2": bloc_2, "3": bloc_3, "4": bloc_4, "5": bloc_5, "6": bloc_6, "7": bloc_7, "8": bloc_8}


def main():
    parser = argparse.ArgumentParser(description="Exploration complémentaire de la BDNB (étape 0 Géoplateforme et Émergence BDNB)")
    parser.add_argument("--bloc", choices=[*BLOCS, "9", "all"], help="bloc à exécuter ; all = 1 à 8 (le 9 appelle Géorisques)")
    parser.add_argument("--dico", nargs="+", metavar="COLONNE", help="définition des colonnes dont le nom contient COLONNE")
    parser.add_argument("--table", help="avec --dico : limite la recherche à cette table")
    parser.add_argument("--rapport", action="store_true", help="écrit le compte rendu complet dans rapports/")
    parser.add_argument("--lignes", type=int, default=LIGNES_TERMINAL, help="lignes affichées par tableau dans le terminal")
    parser.add_argument("--n-par-modalite", type=int, default=N_PAR_MODALITE, help="bloc 9 : points tirés par modalité")
    parser.add_argument("--col-inondation", help="bloc 9 : colonne d'inondation de batiment_groupe_risques")
    parser.add_argument("--col-lon", help="bloc 9 : colonne de longitude de adresse")
    parser.add_argument("--col-lat", help="bloc 9 : colonne de latitude de adresse")
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
        if nom == "9":
            bloc_9(sortie, args.n_par_modalite, args.col_inondation, args.col_lon, args.col_lat)
        else:
            BLOCS[nom](sortie)
        if args.rapport:
            sortie.ecrire(nom)


if __name__ == "__main__":
    main()

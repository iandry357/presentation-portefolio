"""Exploration R0 du référentiel bailleur : inventaire des sources, accès PISTE, jeux de données (loyers, BOFiP),
tables BDNB locales. Aucune écriture BigQuery ni ChromaDB (lecture seule).

Usage : python scripts\\explore_referentiel.py --bloc 0|1|2|3|all [--rapport] [--lignes 20] [--piste-env sandbox|production] [--force]
Terminal : les --lignes premières lignes de chaque tableau. Fichier (--rapport) : la totalité.
Bloc 0 : environnement, accès PISTE (jeton, table des matières du CGI, versions d'articles), recherche des jeux de données
(loyers, BOFiP), tables BDNB locales.
Bloc 1 : jeu « Logement - Encadrement des loyers » (téléchargé s'il est absent ; --force : retélécharger).
Bloc 2 : année et période de construction dans la BDNB, au regard des époques de l'encadrement.
Bloc 3 : champs, valeurs et recherche plein texte des jeux BOFiP (data.economie.gouv.fr).
"""
import argparse
import importlib.util
import time
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl
import requests
import json

# --- Paramètres ---
RACINE = Path(__file__).resolve().parent.parent  # realisations/immobilier
DOSSIER_REF = RACINE / "pipeline" / "data" / "referentiel"
DOSSIER_RAPPORTS = DOSSIER_REF / "rapports"
DOSSIER_PARQUET = RACINE / "pipeline" / "data" / "bdnb" / "parquet"
DOSSIER_LOYERS = DOSSIER_REF / "loyers"
ENV_PISTE = RACINE / "pipeline" / ".env"  # PISTE_ENV, PISTE_CLIENT_ID, PISTE_CLIENT_SECRET (propres à Immobilier)
CGI_TEXT_ID = "LEGITEXT000006069577"  # confirmé par le pipeline gestion-patrimoine
MODULES = ["polars", "requests", "dotenv", "pyarrow"]
TIMEOUT = 60
LIGNES_TERMINAL = 20
MOTS_COLONNES = ("annee", "construction", "periode")  # colonnes utiles au bloc 2 (époque du bâtiment)
RECHERCHES_DATAGOUV = [
    "encadrement des loyers Paris",
    "BOFiP Impôts publications en vigueur",
]
RECHERCHES_ODS = {  # catalogues Opendatasoft : (url, mot cherché)
    "opendata.paris.fr": ("https://opendata.paris.fr/api/explore/v2.1/catalog/datasets", "encadrement"),
    "data.economie.gouv.fr": ("https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets", "bofip"),
}
ARTICLES_FRAICHEUR = ["156", "31", "32"]  # articles du CGI dont on lit les versions (bloc 0b)
URL_LOYERS = "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/logement-encadrement-des-loyers/exports/csv"
FICHIER_LOYERS = "logement-encadrement-des-loyers.csv"
URL_LOYERS_META = "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/logement-encadrement-des-loyers"
RECHERCHES_LOYERS = [  # recherche d'un millésime plus récent que 2025 (bloc 1f)
    "encadrement des loyers 2026 Paris",
    "loyers de référence Paris arrêté 2026",
]
NB_ANNEES_TOP = 5  # années les plus fréquentes listées par période DPE (bloc 2f)
URL_ECO = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets"
DATASETS_BOFIP = ["bofip-vigueur", "bofip-impots", "dgfip-bulletin-officiel-gcp-rho"]  # trouvés au bloc 0d
TERMES_BOFIP = ["RFPI", "BIC", "LMNP", "déficit foncier"]  # recherche plein texte dans bofip-vigueur (bloc 3b)
DOSSIER_BOFIP = DOSSIER_REF / "bofip"
FICHIER_BOFIP = "bofip-series.csv"
SERIES_BOFIP = ["RFPI", "BIC"]  # séries téléchargées pour mesurer le volume (bloc 3c)
MOTS_PAR_CHUNK = 300  # taille visée d'un chunk, pour estimer le volume (bloc 3c)
TERMES_CONTENU = ["loueur en meublé", "micro-BIC", "déficit foncier", "micro-foncier", "performance énergétique", "amortissement"]
TERMES_CIBLES = ["loueur en meublé", "location meublée", "micro-BIC", "déficit foncier", "micro-foncier", "performance énergétique"]  # documents listés au bloc 3d
PROFONDEUR_PREFIXE = 4  # niveaux d'identifiant regroupés au bloc 3e (BOI-RFPI-BASE-30)
TEXTES_LEGI = {  # textes retrouvés par recherche (fond LODA_DATE), repérés par leur numéro en tête du titre
    "loi 89-462": {"requete": "tendant à améliorer les rapports locatifs", "numero": "89-462", "nature": "LOI"},
    "décret 2002-120": {"requete": "caractéristiques du logement décent", "numero": "2002-120", "nature": "DECRET"},
}
MOTS_CLES_TEXTES = ["performance énergétique", "décence", "décent", "énergie finale", "classe", "révision"]  # comptés dans chaque article (bloc 4b)
MAX_ARTICLES_TEXTE = 150
DELAI_APPELS = 0.5  # pause entre deux appels getArticle
CCH_MOTS = ["construction", "habitation"]  # mots du titre du code dans /list/code
THEMES_CCH = ["diagnostic de performance énergétique", "audit énergétique"]  # titres de sections retenus (bloc 4c)
SEUIL_VALEURS = 100  # colonne à moins de valeurs distinctes : listée valeur par valeur (bloc 1b)
RATIO_MAJORE, RATIO_MINORE = 1.2, 0.7  # majoré = 1,2 × référence, minoré = 0,7 × référence (bloc 1d)
TOLERANCE_RATIO = 0.005
EPOQUES = [("avant 1946", 1945), ("1946-1970", 1970), ("1971-1990", 1990), ("après 1990", None)]  # époques de l'encadrement, borne haute incluse
ANNEE_MIN, ANNEE_MAX = 1700, 2026  # années de construction jugées plausibles (bloc 2)


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
def lire_json(sortie, url, params=None):
    """GET JSON ; en cas d'échec, l'écrit dans la sortie et renvoie None."""
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        corps = getattr(getattr(e, "response", None), "text", "")[:300]
        sortie.texte(f"  Échec {url} : {e} {corps}")
        return None


def en_date(valeur):
    """Date AAAA-MM-JJ depuis un horodatage en millisecondes ou une chaîne ISO ; None si illisible."""
    try:
        if isinstance(valeur, (int, float)):
            return (datetime(1970, 1, 1) + timedelta(milliseconds=valeur)).strftime("%Y-%m-%d")
        return str(valeur)[:10] if valeur else None
    except (OverflowError, ValueError):
        return None


# --- Bloc 0 ---
def bloc0_environnement(sortie):
    sortie.titre("0a. Modules Python du venv")
    lignes = [{"module": m, "present": importlib.util.find_spec(m) is not None} for m in MODULES]
    sortie.tableau(pl.DataFrame(lignes))


def piste_urls(env):
    if env == "production":
        return "https://oauth.piste.gouv.fr/api/oauth/token", "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"
    return "https://sandbox-oauth.piste.gouv.fr/api/oauth/token", "https://sandbox-api.piste.gouv.fr/dila/legifrance/lf-engine-app"


def articles_de(section):
    """Tous les articles d'une section et de ses sous-sections (nœuds de la table des matières)."""
    articles = list(section.get("articles", []))
    for sous in section.get("sections", []):
        articles.extend(articles_de(sous))
    return articles


def echantillon_versions(sortie, url_api, jeton, articles):
    """Versions de quelques articles du CGI (getArticle) : mesure la fraîcheur de l'environnement PISTE."""
    sortie.texte("\n  Échantillon d'articles (fraîcheur) :")
    if articles:
        sortie.texte(f"  Clés d'un nœud de la table des matières : {sorted(articles[0].keys())}")
    entetes = {"Authorization": f"Bearer {jeton}", "Content-Type": "application/json", "Accept": "application/json"}
    for num in ARTICLES_FRAICHEUR:
        noeuds = [a for a in articles if str(a.get("num", "")).strip() == num]
        vigueur = [a for a in noeuds if a.get("etat") == "VIGUEUR"]
        sortie.texte(f"  Article {num} : {len(noeuds)} nœud(s), {len(vigueur)} en vigueur")
        if not vigueur:
            continue
        try:
            r = requests.post(f"{url_api}/consult/getArticle", headers=entetes, json={"id": vigueur[0]["id"]}, timeout=TIMEOUT)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            sortie.texte(f"    Échec : {e}")
            continue
        reponse = r.json()
        article = reponse.get("article", reponse)
        sortie.texte(f"    clés : {sorted(article.keys())}")
        sortie.texte(f"    dateDebut {en_date(article.get('dateDebut'))} · dateFin {en_date(article.get('dateFin'))} · etat {article.get('etat')}")
        for v in article.get("articleVersions") or []:
            sortie.texte(f"    version {v.get('id')} · {v.get('etat')} · {en_date(v.get('dateDebut'))} → {en_date(v.get('dateFin'))}")


def bloc0_piste(sortie, piste_env):
    sortie.titre("0b. Accès PISTE / Légifrance")
    try:
        from dotenv import dotenv_values
    except ImportError:
        sortie.texte("  Module python-dotenv absent du venv : pip install python-dotenv")
        return
    if not ENV_PISTE.exists():
        sortie.texte(f"  .env introuvable : {ENV_PISTE}")
        return
    valeurs = dotenv_values(ENV_PISTE)
    env = piste_env or valeurs.get("PISTE_ENV", "sandbox")
    for nom in ("PISTE_CLIENT_ID", "PISTE_CLIENT_SECRET"):
        sortie.texte(f"  {nom} : {'présent' if valeurs.get(nom) else 'ABSENT'}")  # jamais la valeur
    sortie.texte(f"  Environnement utilisé : {env} (.env : {valeurs.get('PISTE_ENV', 'non défini')})")
    url_jeton, url_api = piste_urls(env)
    try:
        r = requests.post(
            url_jeton,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": valeurs.get("PISTE_CLIENT_ID"),
                "client_secret": valeurs.get("PISTE_CLIENT_SECRET"),
                "scope": "openid",
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        jeton = r.json()
        sortie.texte(f"  Jeton obtenu (expire dans {jeton.get('expires_in')} s)")
        r = requests.post(
            f"{url_api}/consult/code/tableMatieres",
            headers={"Authorization": f"Bearer {jeton['access_token']}", "Content-Type": "application/json", "Accept": "application/json"},
            json={"date": int(time.time() * 1000), "sctId": "", "textId": CGI_TEXT_ID},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        corps = getattr(getattr(e, "response", None), "text", "")[:300]
        sortie.texte(f"  Échec : {e} {corps}")
        return
    arbre = r.json()
    articles = articles_de(arbre)
    sortie.texte(f"  Table des matières du CGI : {len(arbre.get('sections', []))} sections de premier niveau, {len(articles)} articles")
    etats = pl.DataFrame({"etat": [a.get("etat") for a in articles]}).group_by("etat").agg(pl.len().alias("articles")).sort("articles", descending=True)
    sortie.tableau(etats)
    debuts = sorted(d for d in (en_date(a.get("dateDebut")) for a in articles) if d)
    if debuts:
        sortie.texte(f"  Fraîcheur : dateDebut la plus récente = {debuts[-1]} (à comparer à la date du jour)")
    echantillon_versions(sortie, url_api, jeton["access_token"], articles)


def bloc0_jeux(sortie):
    sortie.titre("0c. Jeux de données (data.gouv.fr)")
    for recherche in RECHERCHES_DATAGOUV:
        sortie.texte(f"\n  Recherche : {recherche}")
        donnees = lire_json(sortie, "https://www.data.gouv.fr/api/1/datasets/", {"q": recherche, "page_size": 8})
        if not donnees:
            continue
        lignes = [
            {
                "id": d.get("id"),
                "titre": d.get("title"),
                "organisation": (d.get("organization") or {}).get("name"),
                "maj": (d.get("last_update") or d.get("last_modified") or "")[:10],
                "ressources": len(d.get("resources", [])),
            }
            for d in donnees.get("data", [])
        ]
        sortie.tableau(pl.DataFrame(lignes) if lignes else pl.DataFrame({"resultat": []}))
    sortie.titre("0d. Catalogues Opendatasoft")
    for nom, (url, mot) in RECHERCHES_ODS.items():
        sortie.texte(f"\n  {nom} : recherche « {mot} »")
        donnees = lire_json(sortie, url, {"limit": 8, "where": f'search("{mot}")'})
        if not donnees:
            continue
        lignes = []
        for d in donnees.get("results", []):
            meta = (d.get("metas") or {}).get("default", {})
            lignes.append({
                "dataset_id": d.get("dataset_id"),
                "titre": meta.get("title"),
                "maj": (meta.get("data_processed") or meta.get("modified") or "")[:10],
                "enregistrements": meta.get("records_count"),
                "champs": len(d.get("fields", [])),
            })
        sortie.tableau(pl.DataFrame(lignes) if lignes else pl.DataFrame({"resultat": []}))


def bloc0_parquet(sortie):
    sortie.titre("0e. Tables BDNB locales (Parquet)")
    if not DOSSIER_PARQUET.exists():
        sortie.texte(f"  Dossier introuvable : {DOSSIER_PARQUET}")
        return
    lignes, colonnes_utiles = [], []
    for chemin in sorted(DOSSIER_PARQUET.glob("*.parquet")):
        vue = pl.scan_parquet(chemin)
        noms = vue.collect_schema().names()
        lignes.append({
            "table": chemin.stem,
            "lignes": vue.select(pl.len()).collect().item(),
            "colonnes": len(noms),
            "mo": round(chemin.stat().st_size / 1e6, 1),
        })
        colonnes_utiles += [{"table": chemin.stem, "colonne": n} for n in noms if any(m in n.lower() for m in MOTS_COLONNES)]
    sortie.tableau(pl.DataFrame(lignes))
    sortie.texte(f"\n  Colonnes dont le nom évoque l'année ou la période de construction ({'/'.join(MOTS_COLONNES)}) :")
    sortie.tableau(pl.DataFrame(colonnes_utiles) if colonnes_utiles else pl.DataFrame({"resultat": []}))


def bloc0(sortie, args):
    bloc0_environnement(sortie)
    bloc0_piste(sortie, args.piste_env)
    bloc0_jeux(sortie)
    bloc0_parquet(sortie)


# --- Outils des blocs 1 et 2 ---
def telecharger(sortie, url, chemin, params=None, force=False):
    if chemin.exists() and not force:
        sortie.texte(f"  Déjà présent : {chemin} ({chemin.stat().st_size / 1e6:.1f} Mo)")
        return True
    chemin.parent.mkdir(parents=True, exist_ok=True)
    try:
        with requests.get(url, params=params, stream=True, timeout=TIMEOUT) as r:
            r.raise_for_status()
            with open(chemin, "wb") as f:
                for morceau in r.iter_content(chunk_size=1 << 20):
                    f.write(morceau)
    except requests.exceptions.RequestException as e:
        sortie.texte(f"  Échec {url} : {e}")
        return False
    sortie.texte(f"  Téléchargé : {chemin} ({chemin.stat().st_size / 1e6:.1f} Mo)")
    return True


def trouver(colonnes, *motifs):
    """Première colonne dont le nom est égal à un motif, à défaut qui le contient ; None si absente."""
    for m in motifs:
        for c in colonnes:
            if c.lower() == m:
                return c
    for m in motifs:
        for c in colonnes:
            if m in c.lower():
                return c
    return None


def points(coordonnees):
    """Couples de coordonnées d'une géométrie GeoJSON, quelle que soit sa profondeur."""
    if coordonnees and isinstance(coordonnees[0], (int, float)):
        yield coordonnees
    else:
        for c in coordonnees:
            yield from points(c)


def epoque_py(annee):
    if annee is None:
        return None
    for libelle, fin in EPOQUES:
        if fin is None or annee <= fin:
            return libelle


def annee_valide():
    a = pl.col("annee_construction_dpe").cast(pl.Int64, strict=False)
    return pl.when(a.is_between(ANNEE_MIN, ANNEE_MAX)).then(a)


def epoque_de(annee):
    expr = pl.when(annee.is_null()).then(pl.lit(None, dtype=pl.Utf8))
    for libelle, fin in EPOQUES[:-1]:
        expr = expr.when(annee <= fin).then(pl.lit(libelle))
    return expr.otherwise(pl.lit(EPOQUES[-1][0]))


# --- Bloc 1 : loyers ---
def bloc1_loyers(sortie, args):
    sortie.titre("1a. Jeu « Logement - Encadrement des loyers » (opendata.paris.fr)")
    chemin = DOSSIER_LOYERS / FICHIER_LOYERS
    if not telecharger(sortie, URL_LOYERS, chemin, {"delimiter": ";", "with_bom": "false"}, args.force):
        return
    df = pl.read_csv(chemin, separator=";", infer_schema_length=10000)
    sortie.texte(f"  {df.height} lignes, {df.width} colonnes")
    sortie.tableau(pl.DataFrame([
        {"colonne": c, "type": str(df.schema[c]), "nuls": df[c].null_count(), "uniques": df[c].n_unique(), "exemple": str(df[c][0])[:60]}
        for c in df.columns
    ]))

    sortie.titre(f"1b. Valeurs des colonnes à moins de {SEUIL_VALEURS} valeurs distinctes")
    for c in df.columns:
        if "geo" in c.lower() or df[c].n_unique() > SEUIL_VALEURS:
            continue
        sortie.texte(f"\n  {c}")
        sortie.tableau(df.group_by(c).agg(pl.len().alias("lignes")).sort(c))

    sortie.titre("1c. Lignes par année")
    col_annee = trouver(df.columns, "annee")
    if col_annee:
        sortie.texte(f"  Colonne détectée : {col_annee}")
        sortie.tableau(df.group_by(col_annee).agg(pl.len().alias("lignes")).sort(col_annee))
        derniere = df[col_annee].cast(pl.Int64, strict=False).max()
        sortie.texte(f"  Dernière année présente : {derniere}" + (" (aucune ligne pour 2026)" if derniere is not None and derniere < 2026 else ""))
    else:
        sortie.texte("  Aucune colonne d'année détectée")

    sortie.titre("1d. Cohérence référence / majoré / minoré")
    col_ref, col_max, col_min = trouver(df.columns, "ref"), trouver(df.columns, "max"), trouver(df.columns, "min")
    sortie.texte(f"  Colonnes détectées : référence={col_ref}, majoré={col_max}, minoré={col_min}")
    if col_ref and col_max and col_min:
        num = df.select(
            pl.col(col_ref).cast(pl.Float64, strict=False).alias("ref"),
            pl.col(col_max).cast(pl.Float64, strict=False).alias("max"),
            pl.col(col_min).cast(pl.Float64, strict=False).alias("min"),
        ).with_columns((pl.col("max") / pl.col("ref")).alias("r_max"), (pl.col("min") / pl.col("ref")).alias("r_min"))
        sortie.tableau(num.select(
            pl.col("r_max").min().alias("r_max_min"), pl.col("r_max").median().alias("r_max_median"), pl.col("r_max").max().alias("r_max_max"),
            pl.col("r_min").min().alias("r_min_min"), pl.col("r_min").median().alias("r_min_median"), pl.col("r_min").max().alias("r_min_max"),
            ((pl.col("r_max") - RATIO_MAJORE).abs() > TOLERANCE_RATIO).sum().alias("ecart_majore"),
            ((pl.col("r_min") - RATIO_MINORE).abs() > TOLERANCE_RATIO).sum().alias("ecart_minore"),
            ((pl.col("min") >= pl.col("ref")) | (pl.col("ref") >= pl.col("max"))).sum().alias("ordre_incoherent"),
        ))

    sortie.titre("1e. Géométrie des quartiers")
    col_geo = trouver(df.columns, "geo_shape")
    if not col_geo:
        sortie.texte("  Aucune colonne geo_shape détectée")
        return
    formes = df[col_geo].drop_nulls().unique().to_list()
    types, lon, lat, illisibles = {}, [], [], 0
    for forme in formes:
        try:
            g = json.loads(forme)
            types[g.get("type")] = types.get(g.get("type"), 0) + 1
            for p in points(g["coordinates"]):
                lon.append(p[0])
                lat.append(p[1])
        except (ValueError, KeyError, TypeError):
            illisibles += 1
    sortie.texte(f"  {len(formes)} géométries distinctes (colonne {col_geo}), illisibles : {illisibles}, types : {types}")
    if lon:
        sortie.texte(f"  Emprise : longitude {min(lon):.4f} à {max(lon):.4f}, latitude {min(lat):.4f} à {max(lat):.4f}")
        sortie.texte("  Système de coordonnées : " + ("compatible lon/lat WGS84 (comme DVF)" if 1.5 < min(lon) and max(lon) < 3.5 and 48 < min(lat) and max(lat) < 49.5 else "NON lon/lat WGS84, à convertir"))


# --- Bloc 2 : année et période de construction ---
def bloc2_epoque(sortie, args):
    dpe_logement = DOSSIER_PARQUET / "dpe_logement.parquet"
    representatif = DOSSIER_PARQUET / "batiment_groupe_dpe_representatif_logement.parquet"

    sortie.titre("2a. Remplissage (tables brutes, sans la sélection du pipeline)")
    lignes = []
    for chemin in (dpe_logement, representatif):
        stats = pl.scan_parquet(chemin).select(
            pl.len().alias("lignes"),
            pl.col("annee_construction_dpe").cast(pl.Int64, strict=False).count().alias("annee_renseignee"),
            annee_valide().count().alias("annee_plausible"),
            pl.col("periode_construction_dpe").count().alias("periode_renseignee"),
            annee_valide().min().alias("annee_min"),
            annee_valide().median().alias("annee_mediane"),
            annee_valide().max().alias("annee_max"),
        ).collect()
        lignes.append({"table": chemin.stem} | stats.row(0, named=True))
    sortie.tableau(pl.DataFrame(lignes))

    sortie.titre("2b. Période DPE au regard des époques de l'encadrement (dpe_logement)")
    dpe = pl.scan_parquet(dpe_logement).select(
        "identifiant_dpe", annee_valide().alias("annee"), pl.col("periode_construction_dpe").alias("periode"),
    ).with_columns(epoque_de(pl.col("annee")).alias("epoque"))
    par_periode = dpe.group_by("periode").agg(
        pl.len().alias("lignes"),
        pl.col("annee").min().alias("annee_min"),
        pl.col("annee").quantile(0.05).alias("p05"),
        pl.col("annee").quantile(0.95).alias("p95"),
        pl.col("annee").max().alias("annee_max"),
    ).sort("annee_min").collect()
    par_periode = par_periode.with_columns(pl.struct("p05", "p95").map_elements(
        lambda s: "AMBIGUË" if epoque_py(s["p05"]) != epoque_py(s["p95"]) else "unique", return_dtype=pl.Utf8,
    ).alias("epoque_p05_p95"))
    sortie.tableau(par_periode)
    croise = dpe.group_by("periode", "epoque").agg(pl.len().alias("lignes")).collect()
    sortie.tableau(croise.pivot(on="epoque", index="periode", values="lignes").fill_null(0).sort("periode"))

    sortie.titre("2c. Année au niveau du bâtiment")
    for chemin, colonnes in ((DOSSIER_PARQUET / "rel_batiment_groupe_dpe_logement.parquet", ["batiment_groupe_id", "identifiant_dpe"]),
                             (DOSSIER_PARQUET / "rel_batiment_groupe_dvf_open.parquet", ["batiment_groupe_id"])):
        manque = [c for c in colonnes if c not in pl.scan_parquet(chemin).collect_schema().names()]
        if manque:
            sortie.texte(f"  {chemin.stem} : colonnes absentes {manque}")
            return
    rel = pl.scan_parquet(DOSSIER_PARQUET / "rel_batiment_groupe_dpe_logement.parquet").select("batiment_groupe_id", "identifiant_dpe").unique()
    bat = rel.join(dpe, on="identifiant_dpe", how="inner").group_by("batiment_groupe_id").agg(
        pl.len().alias("n_dpe"),
        pl.col("annee").count().alias("n_annee"),
        pl.col("annee").min().alias("annee_min"),
        pl.col("annee").max().alias("annee_max"),
        pl.col("epoque").drop_nulls().n_unique().alias("n_epoques"),
        pl.col("periode").drop_nulls().n_unique().alias("n_periodes"),
    ).collect()
    ecart = pl.col("annee_max") - pl.col("annee_min")
    sortie.texte(f"  {bat.height} bâtiments avec au moins un DPE, dont {bat.filter(pl.col('n_annee') > 0).height} avec au moins une année")
    sortie.texte("  Écart entre l'année la plus ancienne et la plus récente des DPE d'un même bâtiment :")
    sortie.tableau(
        bat.filter(pl.col("n_annee") > 0)
        .select(pl.when(ecart == 0).then(pl.lit("0 an")).when(ecart <= 5).then(pl.lit("1 à 5 ans"))
                .when(ecart <= 20).then(pl.lit("6 à 20 ans")).otherwise(pl.lit("plus de 20 ans")).alias("ecart"))
        .group_by("ecart").agg(pl.len().alias("batiments"))
        .with_columns((pl.col("batiments") / pl.col("batiments").sum() * 100).round(1).alias("pct"))
        .sort("batiments", descending=True)
    )

    sortie.titre("2d. Époque de l'encadrement des bâtiments avec une vente DVF")
    categories = bat.with_columns(
        pl.when(pl.col("n_annee") == 0)
        .then(pl.when(pl.col("n_periodes") > 0).then(pl.lit("pas d'année, période connue")).otherwise(pl.lit("ni année ni période")))
        .when(pl.col("n_epoques") == 1).then(pl.lit("année connue, époque unique"))
        .otherwise(pl.lit("année connue, plusieurs époques")).alias("categorie")
    )
    ventes = pl.scan_parquet(DOSSIER_PARQUET / "rel_batiment_groupe_dvf_open.parquet").select("batiment_groupe_id").unique().collect()
    avec_dpe = categories.join(ventes, on="batiment_groupe_id", how="semi")
    sortie.texte(f"  {ventes.height} bâtiments avec une vente DVF (Cerema), dont {avec_dpe.height} avec au moins un DPE")
    for titre, source in (("Bâtiments avec vente", avec_dpe), ("Tous les bâtiments avec DPE", categories)):
        sortie.texte(f"\n  {titre} :")
        sortie.tableau(
            source.group_by("categorie").agg(pl.len().alias("batiments"))
            .with_columns((pl.col("batiments") / pl.col("batiments").sum() * 100).round(1).alias("pct"))
            .sort("batiments", descending=True)
        )


def bloc1_millesime(sortie):
    sortie.titre("1f. Millésime du jeu des loyers et recherche d'un jeu 2026")
    meta = lire_json(sortie, URL_LOYERS_META)
    if meta:
        for groupe, contenu in (meta.get("metas") or {}).items():
            sortie.texte(f"\n  metas.{groupe}")
            for cle, valeur in (contenu or {}).items():
                sortie.texte(f"    {cle} : {str(valeur)[:150]}")
    for recherche in RECHERCHES_LOYERS:
        sortie.texte(f"\n  data.gouv.fr : {recherche}")
        donnees = lire_json(sortie, "https://www.data.gouv.fr/api/1/datasets/", {"q": recherche, "page_size": 10})
        if not donnees:
            continue
        lignes = [
            {
                "titre": d.get("title"),
                "organisation": (d.get("organization") or {}).get("name"),
                "maj": (d.get("last_update") or d.get("last_modified") or "")[:10],
                "couverture_fin": ((d.get("temporal_coverage") or {}).get("end") or "")[:10],
            }
            for d in donnees.get("data", [])
        ]
        sortie.tableau(pl.DataFrame(lignes) if lignes else pl.DataFrame({"resultat": []}))
    sortie.texte("\n  opendata.paris.fr : recherche « loyer »")
    donnees = lire_json(sortie, RECHERCHES_ODS["opendata.paris.fr"][0], {"limit": 10, "where": 'search("loyer")'})
    if donnees:
        lignes = []
        for d in donnees.get("results", []):
            m = (d.get("metas") or {}).get("default", {})
            lignes.append({"dataset_id": d.get("dataset_id"), "titre": m.get("title"), "maj": (m.get("data_processed") or m.get("modified") or "")[:10]})
        sortie.tableau(pl.DataFrame(lignes) if lignes else pl.DataFrame({"resultat": []}))


def bloc2_valeurs(sortie):
    sortie.titre("2f. Années les plus fréquentes par période DPE (l'année sert-elle de borne à la période ?)")
    dpe = pl.scan_parquet(DOSSIER_PARQUET / "dpe_logement.parquet").select(
        annee_valide().alias("annee"), pl.col("periode_construction_dpe").alias("periode"),
    ).filter(pl.col("annee").is_not_null())
    frequences = dpe.group_by("periode", "annee").agg(pl.len().alias("lignes")).collect()
    totaux = frequences.group_by("periode").agg(pl.col("lignes").sum().alias("total"))
    top = (
        frequences.join(totaux, on="periode")
        .with_columns((pl.col("lignes") / pl.col("total") * 100).round(1).alias("pct"))
        .sort("periode", "lignes", descending=[False, True])
        .group_by("periode", maintain_order=True).head(NB_ANNEES_TOP)
    )
    sortie.texte("  Résumé par période (part de l'année la plus fréquente et des premières années) :")
    sortie.tableau(top.group_by("periode", maintain_order=True).agg(
        pl.col("annee").first().alias("annee_la_plus_frequente"),
        pl.col("pct").first().alias("pct_top1"),
        pl.col("pct").sum().round(1).alias(f"pct_top{NB_ANNEES_TOP}"),
    ))
    sortie.texte(f"\n  Détail : les {NB_ANNEES_TOP} années les plus fréquentes de chaque période :")
    sortie.tableau(top.select("periode", "annee", "lignes", "pct"))


def bloc1(sortie, args):
    bloc1_loyers(sortie, args)
    bloc1_millesime(sortie)


def part(df, *colonnes):
    return (
        df.group_by(list(colonnes)).agg(pl.len().alias("batiments"))
        .with_columns((pl.col("batiments") / pl.col("batiments").sum() * 100).round(1).alias("pct"))
        .sort("batiments", descending=True)
    )


def bloc2_periode_batiment(sortie):
    sortie.titre("2g. Période DPE au niveau du bâtiment")
    chemin_rep = DOSSIER_PARQUET / "batiment_groupe_dpe_representatif_logement.parquet"
    if "batiment_groupe_id" not in pl.scan_parquet(chemin_rep).collect_schema().names():
        sortie.texte("  batiment_groupe_id absent de batiment_groupe_dpe_representatif_logement")
        return
    dpe = pl.scan_parquet(DOSSIER_PARQUET / "dpe_logement.parquet").select("identifiant_dpe", pl.col("periode_construction_dpe").alias("periode"))
    rel = pl.scan_parquet(DOSSIER_PARQUET / "rel_batiment_groupe_dpe_logement.parquet").select("batiment_groupe_id", "identifiant_dpe").unique()
    par_periode = (
        rel.join(dpe, on="identifiant_dpe", how="inner").filter(pl.col("periode").is_not_null())
        .group_by("batiment_groupe_id", "periode").agg(pl.len().alias("n")).collect()
    )
    bat = par_periode.group_by("batiment_groupe_id").agg(
        pl.col("n").sum().alias("n_dpe"),
        pl.len().alias("n_periodes"),
        pl.col("n").max().alias("n_majoritaire"),
        (pl.col("n") == pl.col("n").max()).sum().alias("n_ex_aequo"),
        pl.col("periode").sort_by("n", descending=True).first().alias("periode_majoritaire"),
    ).with_columns((pl.col("n_majoritaire") / pl.col("n_dpe") * 100).alias("pct_majoritaire"))
    representatif = (
        pl.scan_parquet(chemin_rep)
        .select("batiment_groupe_id", pl.col("periode_construction_dpe").alias("periode_rep"))
        .filter(pl.col("periode_rep").is_not_null()).collect()
    )
    ventes = pl.scan_parquet(DOSSIER_PARQUET / "rel_batiment_groupe_dvf_open.parquet").select("batiment_groupe_id").unique().collect()
    for titre, source in (("Tous les bâtiments avec DPE", bat), ("Bâtiments avec vente DVF", bat.join(ventes, on="batiment_groupe_id", how="semi"))):
        sortie.texte(f"\n  {titre} : {source.height} bâtiments")
        sortie.texte("  Périodes distinctes par bâtiment :")
        sortie.tableau(part(source.select(
            pl.when(pl.col("n_periodes") >= 3).then(pl.lit("3 ou plus")).otherwise(pl.col("n_periodes").cast(pl.Utf8)).alias("periodes_distinctes")
        ), "periodes_distinctes"))
        sortie.texte("  Part des DPE du bâtiment qui suivent la période majoritaire :")
        sortie.tableau(part(source.select(
            pl.when(pl.col("pct_majoritaire") >= 100).then(pl.lit("100 %")).when(pl.col("pct_majoritaire") >= 75).then(pl.lit("75 à 99 %"))
            .when(pl.col("pct_majoritaire") >= 50).then(pl.lit("50 à 74 %")).otherwise(pl.lit("moins de 50 %")).alias("part_majoritaire")
        ), "part_majoritaire"))
        sortie.texte(f"  Bâtiments dont la période majoritaire n'est pas unique (ex aequo) : {source.filter(pl.col('n_ex_aequo') > 1).height}")
        accord = source.join(representatif, on="batiment_groupe_id", how="inner").with_columns(
            (pl.col("periode_majoritaire") == pl.col("periode_rep")).alias("accord"),
            (pl.col("n_periodes") > 1).alias("plusieurs_periodes"),
        )
        sortie.texte(f"  Accord entre la période majoritaire et celle du logement représentatif ({accord.height} bâtiments comparés) :")
        sortie.tableau(part(accord, "plusieurs_periodes", "accord"))


def bloc2(sortie, args):
    bloc2_epoque(sortie, args)
    bloc2_valeurs(sortie)
    bloc2_periode_batiment(sortie)


# --- Bloc 3 : BOFiP ---
def bloc3_bofip(sortie, args):
    for jeu in DATASETS_BOFIP:
        sortie.titre(f"3a. Jeu {jeu} (data.economie.gouv.fr)")
        meta = lire_json(sortie, f"{URL_ECO}/{jeu}")
        if not meta:
            continue
        m = (meta.get("metas") or {}).get("default", {})
        sortie.texte(f"  {m.get('title')} · modifié {m.get('modified')} · {m.get('records_count')} enregistrements · licence {m.get('license')}")
        sortie.texte(f"  Description : {str(m.get('description'))[:300]}")
        champs = meta.get("fields") or []
        sortie.tableau(pl.DataFrame([{"champ": f.get("name"), "libelle": f.get("label"), "type": f.get("type")} for f in champs]) if champs else pl.DataFrame({"resultat": []}))
        exemples = lire_json(sortie, f"{URL_ECO}/{jeu}/records", {"limit": 2})
        for enreg in (exemples or {}).get("results", []):
            sortie.texte("\n  Exemple d'enregistrement :")
            for cle, valeur in enreg.items():
                sortie.texte(f"    {cle} : {str(valeur)[:150]}")
        if (m.get("records_count") or 0) <= SEUIL_VALEURS:
            continue
        sortie.texte(f"\n  Valeurs des champs texte (au plus {SEUIL_VALEURS} valeurs distinctes affichées) :")
        for f in champs:
            if f.get("type") != "text":
                continue
            groupes = lire_json(sortie, f"{URL_ECO}/{jeu}/records", {"select": f"{f['name']}, count(*) as n", "group_by": f["name"], "order_by": "n desc", "limit": SEUIL_VALEURS})
            if not groupes:
                continue
            valeurs = groupes.get("results", [])
            sortie.texte(f"\n  {f['name']}" + (f" : au moins {SEUIL_VALEURS} valeurs distinctes" if len(valeurs) >= SEUIL_VALEURS else ""))
            if valeurs and len(valeurs) < SEUIL_VALEURS:
                sortie.tableau(pl.DataFrame(valeurs))

    sortie.titre("3b. Recherche plein texte dans bofip-vigueur")
    for terme in TERMES_BOFIP:
        r = lire_json(sortie, f"{URL_ECO}/bofip-vigueur/records", {"where": f'search("{terme}")', "limit": 3})
        if not r:
            continue
        sortie.texte(f"\n  « {terme} » : {r.get('total_count')} enregistrements")
        for enreg in r.get("results", []):
            sortie.texte("    " + " | ".join(str(v)[:60] for v in list(enreg.values())[:4]))


def bloc3_volumes(sortie, args):
    sortie.titre(f"3c. Séries BOFiP retenues : {', '.join(SERIES_BOFIP)}")
    chemin = DOSSIER_BOFIP / FICHIER_BOFIP
    params = {
        "delimiter": ";", "with_bom": "false",
        "where": " or ".join(f'serie="{s}"' for s in SERIES_BOFIP),
        "select": "type,titre,debut_de_validite,serie,division,identifiant_juridique,permalien,contenu",
    }
    if not telecharger(sortie, f"{URL_ECO}/bofip-vigueur/exports/csv", chemin, params, args.force):
        return
    df = pl.read_csv(chemin, separator=";", infer_schema_length=0).with_columns(pl.col("contenu").fill_null(""))
    df = df.with_columns(pl.col("contenu").str.count_matches(r"\S+").alias("mots"), pl.col("contenu").str.to_lowercase().alias("contenu_min"))
    sortie.texte(f"  {df.height} documents, {df['mots'].sum()} mots")
    sortie.texte("\n  Par série et type :")
    sortie.tableau(df.group_by("serie", "type").agg(
        pl.len().alias("documents"),
        pl.col("mots").sum().alias("mots_total"),
        pl.col("mots").median().alias("mots_mediane"),
        pl.col("mots").max().alias("mots_max"),
        (pl.col("mots").sum() / MOTS_PAR_CHUNK).ceil().alias("chunks_estimes"),
        pl.col("debut_de_validite").min().alias("validite_min"),
        pl.col("debut_de_validite").max().alias("validite_max"),
    ).sort("serie", "type"))
    for serie in SERIES_BOFIP:
        sortie.texte(f"\n  Série {serie} : divisions les plus volumineuses (type Contenu et Actualité confondus) :")
        sortie.tableau(
            df.filter(pl.col("serie") == serie).group_by("division")
            .agg(pl.len().alias("documents"), pl.col("mots").sum().alias("mots_total"))
            .sort("mots_total", descending=True).head(15)
        )
    sortie.texte("\n  Documents contenant chaque terme (texte intégral) :")
    sortie.tableau(df.group_by("serie").agg(
        *[pl.col("contenu_min").str.contains(t.lower(), literal=True).sum().alias(t) for t in TERMES_CONTENU]
    ))


# --- Bloc 4 : Légifrance (PISTE) ---
def ouvrir_piste(sortie, piste_env):
    """(url_api, entêtes) d'une session PISTE, ou None."""
    try:
        from dotenv import dotenv_values
    except ImportError:
        sortie.texte("  Module python-dotenv absent du venv : pip install python-dotenv")
        return None
    if not ENV_PISTE.exists():
        sortie.texte(f"  .env introuvable : {ENV_PISTE}")
        return None
    valeurs = dotenv_values(ENV_PISTE)
    env = piste_env or valeurs.get("PISTE_ENV", "sandbox")
    url_jeton, url_api = piste_urls(env)
    try:
        r = requests.post(
            url_jeton,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "client_id": valeurs.get("PISTE_CLIENT_ID"), "client_secret": valeurs.get("PISTE_CLIENT_SECRET"), "scope": "openid"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        jeton = r.json()["access_token"]
    except (requests.exceptions.RequestException, KeyError) as e:
        sortie.texte(f"  Échec du jeton : {e}")
        return None
    sortie.texte(f"  Session PISTE ouverte ({env})")
    return url_api, {"Authorization": f"Bearer {jeton}", "Content-Type": "application/json", "Accept": "application/json"}


def appeler_piste(sortie, session, chemin, payload):
    url_api, entetes = session
    try:
        r = requests.post(f"{url_api}{chemin}", headers=entetes, json=payload, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        corps = getattr(getattr(e, "response", None), "text", "")[:300]
        sortie.texte(f"  Échec {chemin} : {e} {corps}")
        return None


def maintenant_ms():
    return int(time.time() * 1000)


def chercher_texte(sortie, session, nom, cfg):
    """Retrouve un texte consolidé (loi, décret) par son titre ; renvoie son identifiant LEGITEXT ou None."""
    payload = {
        "fond": "LODA_DATE",
        "recherche": {
            "champs": [{"typeChamp": "TITLE", "criteres": [{"typeRecherche": "TOUS_LES_MOTS_DANS_UN_CHAMP", "valeur": cfg["requete"], "operateur": "ET"}], "operateur": "ET"}],
            "filtres": [], "pageNumber": 1, "pageSize": 100, "operateur": "ET", "sort": "PERTINENCE", "typePagination": "DEFAUT",
        },
    }
    reponse = appeler_piste(sortie, session, "/search", payload)
    if not reponse:
        return None
    resultats = reponse.get("results") or []
    sortie.texte(f"  {reponse.get('totalResultNumber')} résultats ; clés du premier : {sorted(resultats[0].keys()) if resultats else []}")
    candidats = [
        {"id": t.get("id"), "cid": t.get("cid"), "titre": t.get("title") or "", "nature": res.get("nature"), "etat": res.get("etat")}
        for res in resultats for t in res.get("titles") or []
    ]
    sortie.tableau(pl.DataFrame([c | {"titre": c["titre"][:90]} for c in candidats]) if candidats else pl.DataFrame({"resultat": []}))
    correspondants = [c for c in candidats if cfg["numero"] in c["titre"][:40] and c["nature"] == cfg["nature"]]
    if not correspondants:
        sortie.texte(f"  Aucun titre ne contient « {cfg['numero']} »")
        return None

    def date_version(c):
        try:
            return datetime.strptime(c["id"].split("_")[1], "%d-%m-%Y")
        except (IndexError, ValueError):
            return datetime.min

    valides = [c for c in correspondants if date_version(c) <= datetime.now()]
    sortie.texte(f"  {len(correspondants)} versions du texte, dont {len(valides)} en vigueur à ce jour")
    return max(valides or correspondants, key=date_version)["id"]



def structure_texte(sortie, session, texte_id, nature):
    """Arbre d'un texte consolidé : essaie legi/tableMatieres, à défaut lawDecree."""
    for chemin, payload in (
        ("/consult/lawDecree", {"textId": texte_id, "date": maintenant_ms()}),
        ("/consult/lawDecree", {"textId": texte_id.split("_")[0], "date": maintenant_ms()}),
    ):
        arbre = appeler_piste(sortie, session, chemin, payload)
        if arbre:
            sortie.texte(f"  {chemin} : clés {sorted(arbre.keys())}")
            return arbre
    return None


def sections_correspondantes(section, mots, resultats):
    """Sections dont le titre contient un des mots ; la branche entière est retenue, sans descendre plus bas."""
    titre = section.get("title") or ""
    if any(m in titre.lower() for m in mots):
        resultats.append((titre, articles_de(section)))
        return
    for sous in section.get("sections", []):
        sections_correspondantes(sous, mots, resultats)


def bloc4_legifrance(sortie, args):
    sortie.titre("4a. Session PISTE")
    session = ouvrir_piste(sortie, args.piste_env)
    if not session:
        return
    for nom, cfg in TEXTES_LEGI.items():
        sortie.titre(f"4b. {nom}")
        texte_id = chercher_texte(sortie, session, nom, cfg)
        if not texte_id:
            continue
        sortie.texte(f"  Identifiant retenu : {texte_id}")
        arbre = structure_texte(sortie, session, texte_id, cfg["nature"])
        articles = articles_de(arbre) if arbre else []
        if not articles:
            sortie.texte("  Aucun article trouvé dans la structure" + (f" : {json.dumps(arbre, ensure_ascii=False)[:600]}" if arbre else ""))
            continue
        sortie.texte(f"  {len(articles)} articles dans la structure" + (f" (les {MAX_ARTICLES_TEXTE} premiers lus)" if len(articles) > MAX_ARTICLES_TEXTE else ""))
        lignes = []
        for noeud in articles[:MAX_ARTICLES_TEXTE]:
            reponse = appeler_piste(sortie, session, "/consult/getArticle", {"id": noeud.get("id")})
            if not reponse:
                continue
            article = reponse.get("article", reponse)
            texte = str(article.get("texte") or article.get("content") or "").lower()
            ligne = {"num": noeud.get("num"), "etat": article.get("etat") or noeud.get("etat"), "debut": en_date(article.get("dateDebut")), "fin": en_date(article.get("dateFin")), "mots": len(texte.split())}
            ligne |= {mot: texte.count(mot.lower()) for mot in MOTS_CLES_TEXTES}
            lignes.append(ligne)
            time.sleep(DELAI_APPELS)
        if not lignes:
            continue
        df = pl.DataFrame(lignes)
        sortie.texte("\n  Articles par état :")
        sortie.tableau(df.group_by("etat").agg(pl.len().alias("articles")).sort("articles", descending=True))
        sortie.texte(f"\n  Articles contenant au moins un mot clé ({', '.join(MOTS_CLES_TEXTES)}) :")
        sortie.tableau(df.filter(pl.sum_horizontal([pl.col(m) for m in MOTS_CLES_TEXTES]) > 0))

    sortie.titre("4c. Code de la construction et de l'habitation")
    liste = appeler_piste(sortie, session, "/list/code", {"pageSize": 100, "pageNumber": 1, "states": ["VIGUEUR"]})
    if not liste:
        return
    codes = liste.get("results") or []
    sortie.texte(f"  {len(codes)} codes listés ; clés du premier : {sorted(codes[0].keys()) if codes else []}")
    trouves = [c for c in codes if all(m in str(c.get("titre") or c.get("title") or "").lower() for m in CCH_MOTS)]
    if not trouves:
        sortie.texte("  Code introuvable dans la liste")
        return
    code_id = trouves[0].get("id") or trouves[0].get("cid")
    sortie.texte(f"  Code retenu : {trouves[0].get('titre') or trouves[0].get('title')} ({code_id})")
    arbre = appeler_piste(sortie, session, "/consult/code/tableMatieres", {"date": maintenant_ms(), "sctId": "", "textId": code_id})
    if not arbre:
        return
    resultats = []
    sections_correspondantes(arbre, [m.lower() for m in THEMES_CCH], resultats)
    sortie.texte(f"  {len(resultats)} sections dont le titre contient : {', '.join(THEMES_CCH)}")
    sortie.tableau(pl.DataFrame([
        {"section": titre[:100], "articles": len(arts), "en_vigueur": sum(1 for a in arts if a.get("etat") == "VIGUEUR"), "numeros": ", ".join(str(a.get("num")) for a in arts[:12])}
        for titre, arts in resultats
    ]) if resultats else pl.DataFrame({"resultat": []}))
    sortie.texte("  Article D126-19 présent : " + str(any(str(a.get("num")).strip() == "D126-19" for _, arts in resultats for a in arts)))


def bloc3_titres(sortie, args):
    sortie.titre("3d. Documents BOFiP contenant les termes ciblés")
    chemin = DOSSIER_BOFIP / FICHIER_BOFIP
    if not chemin.exists():
        sortie.texte("  Fichier absent : lancer d'abord --bloc 3c")
        return
    df = pl.read_csv(chemin, separator=";", infer_schema_length=0).with_columns(pl.col("contenu").fill_null(""))
    df = df.with_columns(pl.col("contenu").str.count_matches(r"\S+").alias("mots"), pl.col("contenu").str.to_lowercase().alias("contenu_min"))
    for terme in TERMES_CIBLES:
        trouves = (
            df.filter(pl.col("contenu_min").str.contains(terme.lower(), literal=True))
            .select("serie", "type", "identifiant_juridique", "titre", "debut_de_validite", "mots")
            .sort("identifiant_juridique")
        )
        sortie.texte(f"\n  « {terme} » : {trouves.height} documents, {trouves['mots'].sum()} mots")
        sortie.tableau(trouves)


def bloc3_prefixes(sortie, args):
    sortie.titre("3e. Documents de type Contenu regroupés par préfixe d'identifiant")
    chemin = DOSSIER_BOFIP / FICHIER_BOFIP
    if not chemin.exists():
        sortie.texte("  Fichier absent : lancer d'abord --bloc 3c")
        return
    df = pl.read_csv(chemin, separator=";", infer_schema_length=0).with_columns(pl.col("contenu").fill_null(""), pl.col("identifiant_juridique").fill_null(""))
    df = df.filter(pl.col("type") == "Contenu").with_columns(
        pl.col("contenu").str.count_matches(r"\S+").alias("mots"),
        pl.col("identifiant_juridique").str.split("-").list.head(PROFONDEUR_PREFIXE).list.join("-").alias("prefixe"),
        pl.sum_horizontal([pl.col("contenu").str.to_lowercase().str.contains(t.lower(), literal=True).cast(pl.UInt8) for t in TERMES_CIBLES]).alias("termes"),
    )
    for serie in SERIES_BOFIP:
        sortie.texte(f"\n  Série {serie} :")
        sortie.tableau(
            df.filter(pl.col("serie") == serie).group_by("prefixe").agg(
                pl.len().alias("documents"),
                pl.col("mots").sum().alias("mots_total"),
                (pl.col("termes") > 0).sum().alias("documents_avec_termes"),
                pl.col("titre").first().alias("exemple_titre"),
            ).sort("prefixe")
        )


BLOCS = {"0": bloc0, "1": bloc1, "2": bloc2, "3": bloc3_bofip, "3c": bloc3_volumes, "3d": bloc3_titres, "3e": bloc3_prefixes, "4": bloc4_legifrance}



def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bloc", required=True, choices=[*BLOCS, "all"])
    parser.add_argument("--rapport", action="store_true", help="écrit la totalité dans pipeline/data/referentiel/rapports/")
    parser.add_argument("--lignes", type=int, default=LIGNES_TERMINAL)
    parser.add_argument("--piste-env", choices=["sandbox", "production"], default=None, help="force l'environnement PISTE (défaut : .env)")
    parser.add_argument("--force", action="store_true", help="retélécharge les fichiers déjà présents (bloc 1)")
    args = parser.parse_args()
    for nom in (BLOCS if args.bloc == "all" else [args.bloc]):
        sortie = Sortie(args.lignes)
        BLOCS[nom](sortie, args)
        if args.rapport:
            sortie.ecrire(nom)


if __name__ == "__main__":
    main()

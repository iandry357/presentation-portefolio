"""Collecte du BOFiP (jeu bofip-vigueur, data.economie.gouv.fr, Licence Ouverte v2.0) : séries RFPI et BIC, type Contenu,
préfixes retenus (config.PREFIXES_BOFIP). Sortie : DOSSIER_CORPUS/bofip_brut.csv (texte intégral dans « contenu »).
Un préfixe sans document arrête la collecte avant toute écriture."""
import logging

import polars as pl
import requests

from pipeline.referentiel.config import (
    CHAMPS_BOFIP, DOSSIER_CORPUS, FICHIER_BOFIP_BRUT, PARAMETRES_BOFIP, PREFIXES_BOFIP, SERIES_BOFIP, TIMEOUT, TYPE_BOFIP,
    URL_BOFIP_EXPORT,
)

logger = logging.getLogger(__name__)


def _telecharger(cible):
    """Export CSV des séries retenues, téléchargé en flux dans un fichier temporaire, renommé une fois complet."""
    params = {**PARAMETRES_BOFIP, "where": " or ".join(f'serie="{s}"' for s in SERIES_BOFIP), "select": CHAMPS_BOFIP}
    temporaire = cible.with_suffix(cible.suffix + ".tmp")
    try:
        with requests.get(URL_BOFIP_EXPORT, params=params, timeout=(TIMEOUT, 3 * TIMEOUT), stream=True) as r:
            r.raise_for_status()
            with open(temporaire, "wb") as f:
                for morceau in r.iter_content(chunk_size=1 << 20):
                    f.write(morceau)
        temporaire.replace(cible)
    finally:
        temporaire.unlink(missing_ok=True)


def _prefixe(identifiant):
    """Préfixe retenu auquel appartient l'identifiant (égal, ou suivi d'un tiret), ou None."""
    return next((p for p in PREFIXES_BOFIP if identifiant == p or identifiant.startswith(p + "-")), None)


def collecter(force=False):
    """Collecte complète ; renvoie le chemin du CSV des documents retenus. Réutilise le fichier s'il existe, sauf force."""
    chemin = DOSSIER_CORPUS / FICHIER_BOFIP_BRUT
    if chemin.exists() and not force:
        logger.info("%s existe déjà (--force pour recollecter)", chemin.name)
        return chemin
    DOSSIER_CORPUS.mkdir(parents=True, exist_ok=True)
    brut = chemin.with_name("bofip_series.csv")
    logger.info("Téléchargement des séries %s", ", ".join(SERIES_BOFIP))
    _telecharger(brut)

    df = pl.read_csv(brut, separator=";", infer_schema_length=0).with_columns(
        pl.col("contenu").fill_null(""), pl.col("identifiant_juridique").fill_null(""),
    )
    df = df.with_columns(
        pl.col("identifiant_juridique").map_elements(_prefixe, return_dtype=pl.Utf8).alias("prefixe"),
        pl.col("contenu").str.count_matches(r"\S+").alias("mots"),
    )
    retenu = df.filter((pl.col("type") == TYPE_BOFIP) & pl.col("prefixe").is_not_null())
    par_prefixe = retenu.group_by("prefixe").agg(pl.len().alias("documents"), pl.col("mots").sum()).sort("prefixe")
    absents = [p for p in PREFIXES_BOFIP if p not in par_prefixe["prefixe"].to_list()]
    if absents:
        raise ValueError("Préfixes BOFiP sans document : " + ", ".join(absents))
    vides = retenu.filter(pl.col("mots") == 0).height
    if vides:
        logger.warning("%d documents retenus sans texte (contenu vide)", vides)
    for ligne in par_prefixe.iter_rows(named=True):
        logger.info("%s : %d documents, %d mots", ligne["prefixe"], ligne["documents"], ligne["mots"])
    retenu.write_csv(chemin, separator=";")
    logger.info("%d documents, %d mots écrits dans %s", retenu.height, retenu["mots"].sum(), chemin.name)
    return chemin

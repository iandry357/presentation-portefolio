import polars as pl
from google.cloud import bigquery

from pipeline.organisation.config import (
    BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH, LIBELLES_SURFACE, TRANCHES_SURFACE,
)

# Utilitaires SQL partagés par les cubes du Croisé et des loyers (cube_croise.py, cube_loyers.py).


def client():
    return bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)


def table(nom):
    return f"`{GCP_PROJECT_ID}.{BQ_DATASET}.{nom}`"


def litteral(valeur):
    """Texte SQL entre apostrophes (échappées avec un antislash, comme en GoogleSQL)."""
    return "'" + str(valeur).replace("\\", "\\\\").replace("'", "\\'") + "'"


def tranche_surface(colonne):
    """Expression SQL : libellé de la tranche de surface (bornes basses incluses), NULL si surface absente ou nulle."""
    cas = " ".join(
        f"WHEN {colonne} < {borne} THEN {litteral(libelle)}"
        for borne, libelle in zip(TRANCHES_SURFACE, LIBELLES_SURFACE)
    )
    return f"CASE WHEN {colonne} IS NULL OR {colonne} <= 0 THEN NULL {cas} ELSE {litteral(LIBELLES_SURFACE[-1])} END"


def fenetre(colonne, debut, fin):
    """Condition SQL sur la période : début inclus ; fin incluse si elle est donnée (None : jusqu'à la dernière date)."""
    condition = f"{colonne} >= DATE {litteral(debut)}"
    return condition if fin is None else f"{condition} AND {colonne} <= DATE {litteral(fin)}"


def mois(colonne):
    """Expression SQL : mois d'une date au format AAAA-MM."""
    return f"FORMAT_DATE('%Y-%m', {colonne})"


def lignes(connexion, requete):
    return [dict(r) for r in connexion.query(requete).result()]


def une_ligne(connexion, requete):
    return dict(next(iter(connexion.query(requete).result())))


def afficher(titre, resultat):
    print(f"\n== {titre}")
    with pl.Config(tbl_rows=-1, tbl_cols=-1):
        print(pl.DataFrame(resultat, infer_schema_length=None) if resultat else "(aucune ligne)")

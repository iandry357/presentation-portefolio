import pandas as pd

from pipeline.config import DVF_SCHEMA

LOGEMENTS = ["Appartement", "Maison"]
LOCAL_COMMERCIAL = "Local industriel. commercial ou assimilé"


def transformer_dvf(df):
    """Une ligne par vente de logement à partir d'un fichier DVF annuel (colonnes en texte).
    Retourne (df, dict des mutations écartées par raison)."""
    ventes = df[df["nature_mutation"] == "Vente"]
    par_mutation = ventes["id_mutation"]
    nb_logements = ventes["type_local"].isin(LOGEMENTS).groupby(par_mutation).sum()
    a_commercial = (ventes["type_local"] == LOCAL_COMMERCIAL).groupby(par_mutation).any()

    gardees = nb_logements[(nb_logements == 1) & ~a_commercial].index
    ecartees = {
        "mutation_sans_logement": int((nb_logements == 0).sum()),
        "mutation_plusieurs_logements": int((nb_logements > 1).sum()),
        "mutation_avec_local_commercial": int(((nb_logements == 1) & a_commercial).sum()),
    }

    logements = ventes[ventes["id_mutation"].isin(gardees) & ventes["type_local"].isin(LOGEMENTS)]
    date = pd.to_datetime(logements["date_mutation"], errors="coerce")
    valeur = pd.to_numeric(logements["valeur_fonciere"], errors="coerce")
    surface = pd.to_numeric(logements["surface_reelle_bati"], errors="coerce")
    arrondissement = pd.to_numeric(logements["code_commune"], errors="coerce") - 75100

    sortie = pd.DataFrame({
        "id_mutation": logements["id_mutation"],
        "date_mutation": date.dt.strftime("%Y-%m-%d"),
        "annee": date.dt.year.astype("Int64"),
        "valeur_fonciere": valeur,
        "surface_reelle_bati": surface,
        "prix_m2": valeur / surface.where(surface > 0),
        "type_local": logements["type_local"],
        "nombre_pieces_principales": pd.to_numeric(
            logements["nombre_pieces_principales"], errors="coerce"
        ).round().astype("Int64"),
        "code_commune": logements["code_commune"],
        "arrondissement": arrondissement.where(arrondissement.between(1, 20)).astype("Int64"),
        "code_postal": logements["code_postal"],
        "longitude": pd.to_numeric(logements["longitude"], errors="coerce"),
        "latitude": pd.to_numeric(logements["latitude"], errors="coerce"),
    })
    return sortie[[nom for nom, _ in DVF_SCHEMA]], ecartees

"""Inspection du format DVF (une année) : colonnes, valeurs clés, structure des mutations. Lecture seule."""
import io

import pandas as pd
import requests

# ── Paramètres ──────────────────────────────────────────────
ANNEE = 2024
URL = "https://files.data.gouv.fr/geo-dvf/latest/csv/{annee}/departements/75.csv.gz"
TIMEOUT = 120
COLONNES_EXEMPLE = [
    "id_mutation", "date_mutation", "valeur_fonciere", "type_local", "surface_reelle_bati",
    "nombre_pieces_principales", "code_commune", "code_postal", "longitude", "latitude",
]


def main():
    r = requests.get(URL.format(annee=ANNEE), timeout=TIMEOUT)
    r.raise_for_status()
    df = pd.read_csv(io.BytesIO(r.content), compression="gzip", dtype=str)

    print(f"Lignes : {len(df)} ; mutations : {df['id_mutation'].nunique()}")
    print(f"Colonnes : {list(df.columns)}")
    print("\nnature_mutation :", df["nature_mutation"].value_counts(dropna=False).to_dict())
    print("type_local :", df["type_local"].value_counts(dropna=False).to_dict())
    print("code_departement :", df["code_departement"].value_counts(dropna=False).to_dict())
    print("code_commune :", sorted(df["code_commune"].dropna().unique())[:25])

    ventes = df[df["nature_mutation"] == "Vente"]
    logements = ventes[ventes["type_local"].isin(["Appartement", "Maison"])]
    par_mutation = logements.groupby("id_mutation").size()
    print(f"\nVentes : {ventes['id_mutation'].nunique()} mutations ; avec au moins 1 logement : {len(par_mutation)}")
    print("Nb de lignes logement par mutation :", par_mutation.value_counts().sort_index().head(10).to_dict())

    combinaisons = ventes.groupby("id_mutation")["type_local"].agg(
        lambda s: ",".join(sorted(s.dropna().unique())) or "(aucun)"
    )
    print("Combinaisons de type_local (top 10) :", combinaisons.value_counts().head(10).to_dict())

    exemple = par_mutation[par_mutation == 1].index[0]
    print("\nExemple de vente à un seul logement :")
    print(df[df["id_mutation"] == exemple][COLONNES_EXEMPLE].to_string())


if __name__ == "__main__":
    main()

"""
Lecture BigQuery du cube « bâti » de l'onglet « Bâtiments (BDNB) » (table agg_analyse_bati, construite par
realisations/immobilier/pipeline/bdnb_complement). Même cache que immobilier_bdnb_bigquery.py ; la table est lue en entier
(listes de prix au m²) puis pivotée en mémoire par immobilier_bdnb_analyse.pivoter.
"""

from app.services.immobilier_bdnb_bigquery import _lire_table

TABLE_ANALYSE_BATI = "agg_analyse_bati"

# Dimensions du cube : celles d'« Analyse » (ventes), puis les attributs du bâti (pipeline/bdnb_complement/cube_bati.py)
DIMENSIONS_BATI = [
    "trimestre", "arrondissement", "pieces", "tranche_surface", "etiquette", "rattachee",
    "epoque_ff", "taille_copro", "inondation", "patrimoine", "usage_batiment",
]


def fetch_analyse_bati() -> list[dict]:
    """Cube des ventes avec attributs du bâti : une ligne par cellule, avec la liste triée des prix au m² (en cache, ne pas modifier)."""
    return _lire_table(TABLE_ANALYSE_BATI, ", ".join(DIMENSIONS_BATI) + ", nb_ventes, prix_m2, date_maj")

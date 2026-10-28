"""
Registre des cubes de la nouvelle organisation de la page Immobilier (tables org_cube_*, construites par
realisations/immobilier/pipeline/organisation). Une entrée par cube : table, dimensions, mesure et colonnes d'effectif.
Ajouter un cube = une entrée ici : la lecture, le pivot et la route d'analyse sont génériques.
Noms à garder synchronisés avec pipeline/organisation/config.py.

mesure : "prix" (listes de prix au m² : médiane et quartiles) ou "comptage" (effectifs et parts).
compte : colonne de l'effectif principal (renvoyé sous le nom n) ; autres_comptes : effectifs supplémentaires.
"""

CUBES = {
    "dvf": {
        "table": "org_cube_dvf", "mesure": "prix", "compte": "nb_ventes", "autres_comptes": [],
        "dimensions": ["mois", "arrondissement", "type_local", "pieces", "tranche_surface"],
    },
    "batiment": {
        "table": "org_cube_batiment", "mesure": "comptage", "compte": "nb_immeubles", "autres_comptes": ["nb_logements"],
        "dimensions": ["arrondissement", "epoque_ff", "usage_batiment", "taille_copro", "inondation", "patrimoine"],
    },
    "croise_ventes": {
        "table": "org_cube_croise_ventes", "mesure": "prix", "compte": "nb_ventes", "autres_comptes": [],
        "dimensions": [
            "mois", "arrondissement", "pieces", "tranche_surface", "etiquette", "rattachee",
            "epoque_ff", "taille_copro", "inondation", "patrimoine", "usage_batiment",
        ],
    },
    "croise_dpe": {
        "table": "org_cube_croise_dpe", "mesure": "comptage", "compte": "nb_dpe", "autres_comptes": [],
        "dimensions": ["mois", "arrondissement", "pieces", "tranche_surface", "etiquette"],
    },
    "dpe": {
        "table": "org_cube_dpe", "mesure": "comptage", "compte": "nb_dpe", "autres_comptes": ["nb_remplacants"],
        "dimensions": [
            "mois", "arrondissement", "etiquette", "niveau_dpe", "type_batiment", "periode_construction", "chauffage", "actif",
        ],
    },
}


def colonnes(cube: str) -> str:
    """Colonnes à lire pour un cube (liste explicite, jamais SELECT *)."""
    definition = CUBES[cube]
    liste = [*definition["dimensions"], definition["compte"], *definition["autres_comptes"]]
    if definition["mesure"] == "prix":
        liste.append("prix_m2")
    liste.append("date_maj")
    return ", ".join(liste)


# Cube des loyers (org_cube_loyers) : hors du registre CUBES, son pivot calcule des loyers et des rendements.
# Chaque vente figure une fois par statut meublé : les lignes d'un seul statut sont lues par requête.
CUBE_LOYERS = {
    "table": "org_cube_loyers",
    "dimensions": ["mois", "annee_loyer", "arrondissement", "pieces", "epoque"],
    "colonnes": (
        "mois, annee_loyer, arrondissement, id_quartier, nom_quartier, pieces, epoque, epoque_ambigue, "
        "periode_heterogene, meuble, nb_ventes, prix_m2, loyer_reference, loyer_majore, loyer_minore, "
        "rendement_reference, rendement_majore, date_maj"
    ),
}

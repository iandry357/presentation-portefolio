from pathlib import Path

from dotenv import load_dotenv

# Même couture que pipeline/dvf_etalab/config.py : le .env de la V1 est dans pipeline/ et pipeline.config lit
# l'environnement dès l'import, il faut donc le charger avant. Seule dépendance vers la V1 : ces 3 constantes.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from pipeline.config import BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH  # noqa: E402

# Source : jeu « Logement - Encadrement des loyers » (opendata.paris.fr), licence ODbL
DATASET_ID = "logement-encadrement-des-loyers"
URL_BASE = f"https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/{DATASET_ID}"
URL_EXPORT = f"{URL_BASE}/exports/csv"
PARAMETRES_EXPORT = {"delimiter": ";", "with_bom": "false"}
LICENCE = "ODbL"
ATTRIBUTION = "Ville de Paris, Direction du Logement et de l'Habitat"
TIMEOUT = 120  # secondes, par requête

# Données locales (non versionnées, exclues du build Docker par .dockerignore) : même dossier que l'exploration R0
DOSSIER_LOYERS = Path(__file__).resolve().parent.parent / "data" / "referentiel" / "loyers"
FICHIER_CSV = f"{DATASET_ID}.csv"
FICHIER_REFERENCE = "loyers_reference.parquet"
FICHIER_QUARTIERS = "loyers_quartiers.parquet"
FICHIER_MANIFESTE = "manifeste.json"

# Contrôles d'intégrité (arrêt au premier écart). Une année complète = quartiers × pièces × époques × meublé.
NB_QUARTIERS = 80
PIECES = [1, 2, 3, 4]
PIECES_MAX = max(PIECES)  # plafond du jeu : 4 = « 4 pièces et plus » (même convention que PIECES_MAX du cube d'analyse)
EPOQUES = ["Avant 1946", "1946-1970", "1971-1990", "Apres 1990"]  # libellés du jeu, tels quels
MEUBLE = {"non meublé": False, "meublé": True}
VILLE = "PARIS"
LIGNES_PAR_ANNEE = NB_QUARTIERS * len(PIECES) * len(EPOQUES) * len(MEUBLE)
RATIO_MAJORE, RATIO_MINORE, TOLERANCE_RATIO = 1.2, 0.7, 0.005  # majoré = 1,2 × référence, minoré = 0,7 × référence

# Colonnes du CSV (ordre du fichier) et type : str, int ou float. Typage strict : une valeur illisible arrête le chargement.
COLONNES = [
    ("annee", "int"), ("id_zone", "int"), ("id_quartier", "int"), ("nom_quartier", "str"), ("piece", "int"),
    ("epoque", "str"), ("meuble_txt", "str"), ("ref", "float"), ("max", "float"), ("min", "float"), ("ville", "str"),
    ("code_grand_quartier", "str"), ("geo_shape", "str"), ("geo_point_2d", "str"),
]
# Table de référence : (colonne du CSV, colonne BigQuery) ; la colonne meuble (booléen) est dérivée de meuble_txt
COLONNES_REFERENCE = [
    ("annee", "annee"), ("id_quartier", "id_quartier"), ("piece", "pieces"), ("epoque", "epoque"),
    ("ref", "loyer_reference"), ("max", "loyer_majore"), ("min", "loyer_minore"),
]
# Table des quartiers : une ligne par quartier, géométrie GeoJSON convertie en GEOGRAPHY au chargement
COLONNES_QUARTIERS = ["id_quartier", "nom_quartier", "code_grand_quartier", "id_zone", "geo_shape"]

# Tables BigQuery (dataset BQ_DATASET). Les tables de travail sont recréées à chaque chargement.
TABLE_REFERENCE = "loyers_reference"
TABLE_QUARTIERS = "loyers_quartiers"
TABLE_LIVRAISONS = "loyers_livraisons"
TABLE_REFERENCE_TRAVAIL = "loyers_reference_travail"
TABLE_QUARTIERS_TRAVAIL = "loyers_quartiers_travail"
# Rattachement des ventes DVF aux quartiers (étape rattachement)
TABLE_RATTACHEMENT = "loyers_rattachement"
VUE_VENTES_LOYER = "loyers_ventes"


# --- Rattachement des ventes (R1b) ---
LIVRAISON = "2026-10"  # livraison DVF Etalab lue (table dvf_etalab) ; surchargée par --livraison
DEPARTEMENT = "75"  # surchargé par --departement
CLUSTER = ["livraison", "code_departement", "id_mutation"]
TABLE_RATTACHEMENT_TRAVAIL = "loyers_rattachement_travail"
# Tables lues (dataset BQ_DATASET)
TABLE_DVF = "dvf_etalab"
VUE_VENTES_BATIMENT = "dvf_etalab_ventes_batiment"
BDNB_DPE = "bdnb_dpe_logement"
BDNB_REL_DPE_BATIMENT = "bdnb_rel_dpe_batiment"
COLONNE_PERIODE = "periode_construction_dpe"  # période de construction d'un DPE dans bdnb_dpe_logement (à confirmer au premier rattachement)

PRIX_M2_MIN, PRIX_M2_MAX = 2000, 30000  # règle V1, mêmes valeurs que pipeline/analyse/config.py
MOIS_ARRETE = 7  # un arrêté s'applique du 1er juillet de l'année N au 30 juin de N+1
SEUIL_ACCORD_PERIODE = 0.75  # sous ce taux de DPE sur la période majoritaire du bâtiment : période hétérogène

# Période de construction DPE (BDNB) -> (époque de l'encadrement, époque ambiguë) ; voir decisions.md, « R0 — Époque du bâtiment »
PERIODES_EPOQUES = {
    "avant 1948": ("Avant 1946", True),
    "1948-1974": ("1946-1970", True),
    "1975-1977": ("1971-1990", False),
    "1978-1982": ("1971-1990", False),
    "1983-1988": ("1971-1990", False),
    "1989-2000": ("Apres 1990", True),
    "2001-2005": ("Apres 1990", False),
    "2006-2012": ("Apres 1990", False),
    "2013-2021": ("Apres 1990", False),
    "après 2021": ("Apres 1990", False),
}

# Statut de rattachement d'une vente (premier cas rencontré dans cet ordre)
STATUT_RATTACHEE = "rattachee"
STATUT_PIECES_INVALIDES = "pieces invalides"
STATUT_SANS_COORDONNEES = "sans coordonnees"
STATUT_HORS_QUARTIER = "hors quartier"
STATUT_SANS_BATIMENT = "sans batiment"
STATUT_SANS_PERIODE = "sans periode"
STATUT_EPOQUE_INDETERMINEE = "epoque indeterminee"


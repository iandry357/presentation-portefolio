import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# GCP / BigQuery
GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
GCP_SA_KEY_PATH = BASE_DIR / os.environ["GCP_SA_KEY_PATH"]
BQ_DATASET = os.environ["BQ_DATASET"]
BQ_TABLE_DPE = "dpe_logements"
BQ_TABLE_DVF = "dvf_mutations"

# DPE — ADEME dpe03existant
DPE_API = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant"
DPE_DEPARTEMENT = "75"
DPE_TAILLE_PAGE = 10000
DPE_PAGES_ECHANTILLON = 10
DPE_TIMEOUT = 120
DPE_MAX_TENTATIVES = 3
ETIQUETTES = ["A", "B", "C", "D", "E", "F", "G"]
DATE_REFORME = "2026-01-01"

# DVF — Etalab
DVF_URL = "https://files.data.gouv.fr/geo-dvf/latest/csv/{annee}/departements/75.csv.gz"
DVF_ANNEES = range(2021, 2026)
PRIX_M2_MIN = 2000
PRIX_M2_MAX = 30000
DVF_TIMEOUT = 120
DVF_MAX_TENTATIVES = 3

# Cache local — persistant via volume Docker
DATA_DIR = BASE_DIR / "data"
DPE_CACHE_DIR = DATA_DIR / "dpe"
DVF_CACHE_DIR = DATA_DIR / "dvf"

# Marqueur de valeur nulle dans les CSV chargés dans BigQuery
NULL_MARKER = "\\N"

# Champs demandés à l'API DPE
DPE_CHAMPS_API = [
    "numero_dpe", "numero_dpe_remplace", "date_etablissement_dpe", "date_reception_dpe",
    "modele_dpe", "version_dpe", "methode_application_dpe", "etiquette_dpe", "etiquette_ges",
    "conso_5_usages_par_m2_ep", "type_energie_principale_chauffage", "type_batiment",
    "periode_construction", "annee_construction", "surface_habitable_logement",
    "numero_etage_appartement", "adresse_ban", "identifiant_ban", "code_postal_ban",
    "code_insee_ban", "nom_commune_ban", "code_departement_ban",
    "coordonnee_cartographique_x_ban", "coordonnee_cartographique_y_ban",
]

# Schéma de la table dpe_logements (ordre des colonnes du CSV chargé)
DPE_SCHEMA = [
    ("numero_dpe", "STRING"),
    ("numero_dpe_remplace", "STRING"),
    ("date_etablissement_dpe", "DATE"),
    ("date_reception_dpe", "DATE"),
    ("modele_dpe", "STRING"),
    ("version_dpe", "FLOAT64"),
    ("methode_application_dpe", "STRING"),
    ("etiquette_dpe", "STRING"),
    ("etiquette_ges", "STRING"),
    ("conso_5_usages_par_m2_ep", "FLOAT64"),
    ("type_energie_principale_chauffage", "STRING"),
    ("type_batiment", "STRING"),
    ("periode_construction", "STRING"),
    ("annee_construction", "INT64"),
    ("surface_habitable_logement", "FLOAT64"),
    ("numero_etage_appartement", "INT64"),
    ("adresse_ban", "STRING"),
    ("identifiant_ban", "STRING"),
    ("code_postal_ban", "STRING"),
    ("code_insee_ban", "STRING"),
    ("nom_commune_ban", "STRING"),
    ("code_departement_ban", "STRING"),
    ("coordonnee_cartographique_x_ban", "FLOAT64"),
    ("coordonnee_cartographique_y_ban", "FLOAT64"),
    ("arrondissement", "INT64"),
    ("flag_chauffage_electrique", "BOOL"),
    ("flag_post_reforme_2026", "BOOL"),
]

# Schéma de la table dvf_mutations (ordre des colonnes du CSV chargé)
DVF_SCHEMA = [
    ("id_mutation", "STRING"),
    ("date_mutation", "DATE"),
    ("annee", "INT64"),
    ("valeur_fonciere", "FLOAT64"),
    ("surface_reelle_bati", "FLOAT64"),
    ("prix_m2", "FLOAT64"),
    ("type_local", "STRING"),
    ("nombre_pieces_principales", "INT64"),
    ("code_commune", "STRING"),
    ("arrondissement", "INT64"),
    ("code_postal", "STRING"),
    ("longitude", "FLOAT64"),
    ("latitude", "FLOAT64"),
]

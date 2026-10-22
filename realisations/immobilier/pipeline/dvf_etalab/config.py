from pathlib import Path

from dotenv import load_dotenv

# Même couture que pipeline/bdnb/config.py : le .env de la V1 est dans pipeline/ et pipeline.config lit
# l'environnement dès l'import, il faut donc le charger avant. Seule dépendance vers la V1 : ces 3 constantes.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from pipeline.config import BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH  # noqa: E402

# --- Paramètres d'exécution (surchargés par --livraison et --departement) ---
LIVRAISON = "2026-10"
DEPARTEMENT = "75"

# Données locales (non versionnées, exclues du build Docker par .dockerignore)
DOSSIER_DVF = Path(__file__).resolve().parent.parent / "data" / "bdnb" / "dvf_etalab"
TIMEOUT = 120  # secondes, par requête de téléchargement

# Livraisons Etalab (API data.gouv, jeu demandes-de-valeurs-foncieres-geolocalisees) : fichiers France entière.
# lignes : nombre de lignes attendu par département après filtre (contrôle, arrêt au premier écart).
BASE_URL = "https://static.data.gouv.fr/resources/demandes-de-valeurs-foncieres-geolocalisees"
LIVRAISONS = {
    "2026-10": {
        "publication": "2026-10-20",
        "fichiers": {
            "2021-s2": {"url": f"{BASE_URL}/20261020-113024/full-2021-s2.csv.gz",
                        "sha1": "077a1f07b802c32bb9d490b86f2496b1cec12950", "lignes": {"75": 47628}},
            "2022": {"url": f"{BASE_URL}/20261020-114218/full-2022.csv.gz",
                     "sha1": "a6e76cd85bf0bf09e52b0e72e0eca0c851925a5c", "lignes": {"75": 98308}},
            "2023": {"url": f"{BASE_URL}/20261020-114336/full-2023.csv.gz",
                     "sha1": "1fdaf0d76d52c4ca4b6e18fea382cab2faa6d06b", "lignes": {"75": 81001}},
            "2024": {"url": f"{BASE_URL}/20261020-114532/full-2024.csv.gz",
                     "sha1": "02e77911bdaf882bd63333b3032f1c37b4f4dc3f", "lignes": {"75": 74882}},
            "2025": {"url": f"{BASE_URL}/20261020-114721/full-2025.csv.gz",
                     "sha1": "3f01863b4913bf2d45e5331959e935e1a224b107", "lignes": {"75": 86190}},
            "2026-s1": {"url": f"{BASE_URL}/20261020-114825/full-2026-s1.csv.gz",
                        "sha1": "7cf0773e4df06028ab22a569425402739974d6a3", "lignes": {"75": 40058}},
        },
    },
}

# Tables BigQuery (dataset BQ_DATASET). La table de travail est recréée à chaque chargement.
TABLE_DVF = "dvf_etalab"
TABLE_TRAVAIL = "dvf_etalab_travail"
TABLE_LIVRAISONS = "dvf_etalab_livraisons"
CLUSTER = ["livraison", "code_departement", "id_mutation"]

# Colonnes ajoutées à celles du fichier
COLONNE_LIVRAISON = "livraison"
COLONNE_FICHIER = "fichier_source"

# Colonnes d'origine (ordre du fichier) et type : str, int, float ou date. Typage strict : une valeur illisible arrête le chargement.
FORMAT_DATE = "%Y-%m-%d"
COLONNES = [
    ("id_mutation", "str"), ("date_mutation", "date"), ("numero_disposition", "int"), ("nature_mutation", "str"),
    ("valeur_fonciere", "float"), ("adresse_numero", "int"), ("adresse_suffixe", "str"), ("adresse_nom_voie", "str"),
    ("adresse_code_voie", "str"), ("code_postal", "str"), ("code_commune", "str"), ("nom_commune", "str"),
    ("code_departement", "str"), ("ancien_code_commune", "str"), ("ancien_nom_commune", "str"),
    ("id_parcelle", "str"), ("ancien_id_parcelle", "str"), ("numero_volume", "str"),
    ("lot1_numero", "str"), ("lot1_surface_carrez", "float"), ("lot2_numero", "str"), ("lot2_surface_carrez", "float"),
    ("lot3_numero", "str"), ("lot3_surface_carrez", "float"), ("lot4_numero", "str"), ("lot4_surface_carrez", "float"),
    ("lot5_numero", "str"), ("lot5_surface_carrez", "float"), ("nombre_lots", "int"), ("code_type_local", "str"),
    ("type_local", "str"), ("surface_reelle_bati", "float"), ("nombre_pieces_principales", "int"),
    ("code_nature_culture", "str"), ("nature_culture", "str"), ("code_nature_culture_speciale", "str"),
    ("nature_culture_speciale", "str"), ("surface_terrain", "float"), ("longitude", "float"), ("latitude", "float"),
]

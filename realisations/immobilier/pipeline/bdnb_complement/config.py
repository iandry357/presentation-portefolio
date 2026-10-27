from pathlib import Path

from dotenv import load_dotenv

# Même couture que pipeline/bdnb/config.py : le .env de la V1 est dans pipeline/ et pipeline.config lit
# l'environnement dès l'import, il faut donc le charger avant. Seule dépendance vers la V1 : ces 3 constantes.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from pipeline.config import BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH  # noqa: E402

# Données locales (non versionnées, exclues du build Docker par .dockerignore)
DOSSIER_BDNB = Path(__file__).resolve().parent.parent / "data" / "bdnb"
DOSSIER_PARQUET = DOSSIER_BDNB / "parquet"
DOSSIER_CHARGEMENT = DOSSIER_BDNB / "chargement_complement"  # Parquet temporaires envoyés à BigQuery

# Une colonne dont le nom correspond n'est jamais chargée, même si elle figure dans une liste blanche
MOTIF_COLONNES_INTERDITES = r"denomination|siren|siret|l_nom|nom_copro|nom_pdl|nom_demandeur|numero_immat"

# Tables cibles BigQuery. colonnes : liste blanche (aucune autre colonne n'est chargée) ;
# cluster[0] : clé, une ligne par valeur (contrôlé) ; lignes : valeur attendue (relevée à l'étape 0, 2026-10-27).
TABLES = {
    "bdnb_ffo_bat": {
        "source": "batiment_groupe_ffo_bat",
        "colonnes": ["batiment_groupe_id", "annee_construction", "nb_niveau", "nb_log", "usage_niveau_1_txt"],
        "cluster": ["batiment_groupe_id"],
        "lignes": 70765,
    },
    "bdnb_bdtopo_bat": {
        "source": "batiment_groupe_bdtopo_bat",
        "colonnes": ["batiment_groupe_id", "hauteur_mean", "max_hauteur"],
        "cluster": ["batiment_groupe_id"],
        "lignes": 74009,
    },
    "bdnb_rnc": {
        "source": "batiment_groupe_rnc",
        "colonnes": ["batiment_groupe_id", "nb_log", "nb_lot_tot", "periode_construction_max"],
        "cluster": ["batiment_groupe_id"],
        "lignes": 43712,
    },
    "bdnb_risques": {
        "source": "batiment_groupe_risques",
        "colonnes": ["batiment_groupe_id", "alea_debordement"],
        "cluster": ["batiment_groupe_id"],
        "lignes": 74212,
    },
    "bdnb_urbanisme": {
        "source": "batiment_groupe_urbanisme",
        "colonnes": ["batiment_groupe_id", "monument_historique", "zone_plu_bati_patrimonial"],
        "cluster": ["batiment_groupe_id"],
        "lignes": 72341,
    },
    "bdnb_parcelle_sitadel": {
        "source": "parcelle_sitadel",
        "colonnes": [
            "parcelle_id", "nombre_dau", "annee_premiere_dau_identifiee", "annee_derniere_dau_identifiee",
            "travaux_sur_construction_existante", "demolition", "indicateur_extension",
            "indicateur_surelevation_ou_nivsupp", "nature_derniere_dau", "bdnb_obsolete", "annee_construction_obsolete",
        ],
        "cluster": ["parcelle_id"],
        "lignes": 11485,
    },
}

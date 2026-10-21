from pathlib import Path

from dotenv import load_dotenv

# Le .env de la V1 est dans pipeline/ et pipeline.config lit l'environnement dès l'import :
# il faut donc le charger avant. Seule dépendance vers la V1 : ces 3 constantes.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from pipeline.config import BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH  # noqa: E402

# Données locales (non versionnées, exclues du build Docker par .dockerignore)
DOSSIER_BDNB = Path(__file__).resolve().parent.parent / "data" / "bdnb"
DOSSIER_PARQUET = DOSSIER_BDNB / "parquet"
DOSSIER_CHARGEMENT = DOSSIER_BDNB / "chargement"  # Parquet temporaires envoyés à BigQuery

# Sélection DPE (décisions du cahier, section 4)
ARRETE_2021 = 1
SUFFIXE_TYPE_DPE = "logement"  # écarte les DPE "immeuble"
METHODE_DPE = "3cl"  # recherchée dans type_dpe
SURFACE_MIN = 0  # surface_habitable_logement strictement supérieure
COLONNES_ARRETE_2012 = [
    "classe_conso_energie_arrete_2012",
    "classe_emission_ges_arrete_2012",
    "conso_3_usages_ep_m2_arrete_2012",
    "emission_ges_3_usages_ep_m2_arrete_2012",
]
FORMAT_DATE = "%Y/%m/%d"  # appliqué aux 10 premiers caractères des dates BDNB

# Tables cibles BigQuery. lignes / colonnes : valeurs attendues (None = à relever au premier essai).
# Pour ajouter bdnb_dvf_statistique plus tard : une entrée ici (source batiment_groupe_dvf_open_statistique).
TABLES = {
    "bdnb_dpe_logement": {
        "source": "dpe_logement",
        "cluster": ["identifiant_dpe"],
        "dates": ["date_etablissement_dpe", "date_reception_dpe"],
        "lignes": 824036,
        "colonnes": 101,
    },
    "bdnb_rel_dpe_batiment": {
        "source": "rel_batiment_groupe_dpe_logement",
        "cluster": ["batiment_groupe_id"],
        "dates": [],
        "lignes": 834031,
        "colonnes": 8,
    },
    "bdnb_batiment_groupe": {
        "source": "batiment_groupe",
        "cluster": ["batiment_groupe_id"],
        "dates": [],
        "lignes": 74212,
        "colonnes": 9,
    },
    "bdnb_adresse": {
        "source": "adresse",
        "cluster": ["cle_interop_adr"],
        "dates": [],
        "lignes": 152698,
        "colonnes": 12,
    },
    "bdnb_rel_batiment_adresse": {
        "source": "rel_batiment_groupe_adresse",
        "cluster": ["batiment_groupe_id"],
        "dates": [],
        "lignes": 154537,
        "colonnes": 6,
    },
    "bdnb_dvf_representatif": {
        "source": "batiment_groupe_dvf_open_representatif",
        "cluster": ["batiment_groupe_id"],
        "dates": ["date_mutation"],
        "lignes": 48458,
        "colonnes": 18,
    },
}

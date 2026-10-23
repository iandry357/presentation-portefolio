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
    "bdnb_rel_batiment_parcelle": {
        "source": "rel_batiment_groupe_parcelle",
        "cluster": ["parcelle_id"],
        "dates": [],
        "lignes": 76780,
        "colonnes": 4,
    },
}


# Agrégats (phase 3)
DATE_VENTE_MIN = "2021-07-01"  # premiers DPE de l'arrêté 2021 : fin juin 2021
PRIX_M2_MIN = 2000  # bornes de prix_m2_local, identiques à la V1
PRIX_M2_MAX = 30000

# Postes de déperdition (clé : nom du poste dans l'agrégat, valeur : colonne de bdnb_dpe_logement)
POSTES_DEPERDITION = {
    "murs": "deperdition_mur",
    "baies_vitrees": "deperdition_baie_vitree",
    "plancher_bas": "deperdition_plancher_bas",
    "plancher_haut": "deperdition_plancher_haut",
    "ponts_thermiques": "deperdition_pont_thermique",
    "portes": "deperdition_porte",
}

AGG_PRIX_DPE = "agg_bdnb_prix_dpe"
AGG_PRIX_ECART = "agg_bdnb_prix_ecart"
AGG_PARC_PERIODE = "agg_bdnb_parc_periode"
AGG_PARC_ENERGIE = "agg_bdnb_parc_energie"
AGG_DEPERDITIONS = "agg_bdnb_deperditions"
AGG_GEOCODAGE = "agg_bdnb_geocodage"
AGG_STATS = "agg_bdnb_stats"

# Métadonnées (tables bdnb_sources et bdnb_entonnoir, construites par metadonnees.py)
TABLE_SOURCES = "bdnb_sources"
TABLE_ENTONNOIR = "bdnb_entonnoir"

# Sources de la BDNB, millésimes vérifiés le 2026-10-22 (cahier immobilier-bdnb.md, section 3).
# À mettre à jour à chaque nouveau millésime chargé.
SOURCES = [
    {"source": "BDNB (CSTB)", "millesime": "2026-02.b (v0.7.12)", "couverture": "Paris (75), publié le 2026-10-07"},
    {"source": "DPE ADEME (arrêté 2021)", "millesime": "2026-09", "couverture": "du 2021-06-30 au 2026-09-13"},
    {"source": "DVF open (Cerema)", "millesime": "2025-10-14", "couverture": "mutations du 2014-01-02 au 2025-06-30"},
    {"source": "BAN (adresses)", "millesime": "2026T1", "couverture": None},
    {"source": "Fichiers fonciers", "millesime": "2025-12-31", "couverture": None},
]


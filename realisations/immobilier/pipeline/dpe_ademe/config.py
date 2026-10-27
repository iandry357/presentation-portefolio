from pathlib import Path

from dotenv import load_dotenv

# Même couture que pipeline/analyse/config.py : le .env de la V1 est dans pipeline/ et pipeline.config lit
# l'environnement dès l'import, il faut donc le charger avant. Seule dépendance vers la V1 : ces 3 constantes.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from pipeline.config import BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH  # noqa: E402

# API ADEME dpe03existant (tous les DPE du département depuis DATE_DEBUT_COLLECTE ; le jeu remonte à 2021-07)
DPE_API = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant"
CHAMP_DEPARTEMENT = "code_departement_ban"
DEPARTEMENT = "75"               # surchargé par --departement
CHAMP_CLE = "numero_dpe"         # une ligne par valeur (contrôlé)
TAILLE_PAGE = 10000
TIMEOUT = 120                    # secondes, par requête
MAX_TENTATIVES = 3
PAUSE_TENTATIVE = 5              # secondes, multipliées par le numéro de la tentative
NB_PAGES_ESSAI = 2               # --essai : pages collectées, sans BigQuery
DATE_DEBUT_COLLECTE = "2025-05-01"  # début de la collecte (inclus) ; même valeur que DATE_DEBUT de pipeline/organisation/config.py ; surchargé par --depuis
NB_FLUX = 4                      # tranches mensuelles collectées en parallèle ; à réduire si l'API répond en erreur 429 ou délai dépassé
DATE_REFORME = "2026-01-01"      # DPE établis à partir de cette date : drapeau flag_post_reforme_2026 (comme la V1)

# Données locales (non versionnées, exclues du build Docker par .dockerignore) : cache distinct de celui de la V1 (data/dpe)
DOSSIER_CACHE = Path(__file__).resolve().parent.parent / "data" / "dpe_ademe"
FICHIER_CURSEUR = "curseur.txt"
FICHIER_TERMINE = "termine.txt"
FICHIER_SORTIE = "dpe_ademe.csv"
NULL_MARKER = "\\N"              # valeur nulle dans le CSV chargé dans BigQuery

# Champs collectés, par groupe : (champ de l'API, type BigQuery). Les 99 champs sont décidés avec l'utilisateur.
GROUPES = {
    "Identification et dates": [
        ("numero_dpe", "STRING"), ("numero_dpe_remplace", "STRING"),
        ("date_etablissement_dpe", "DATE"), ("date_reception_dpe", "DATE"),
        ("date_derniere_modification_dpe", "DATE"), ("date_visite_diagnostiqueur", "DATE"),
        ("date_fin_validite_dpe", "DATE"), ("modele_dpe", "STRING"), ("version_dpe", "FLOAT64"),
        ("methode_application_dpe", "STRING"),
    ],
    "Immeuble et copropriété": [
        ("numero_dpe_immeuble_associe", "STRING"), ("numero_immatriculation_copropriete", "STRING"),
    ],
    "Résultat": [
        ("etiquette_dpe", "STRING"), ("etiquette_ges", "STRING"), ("conso_5_usages_par_m2_ep", "FLOAT64"),
        ("conso_5_usages_ep", "FLOAT64"), ("conso_5_usages_par_m2_ef", "FLOAT64"),
        ("emission_ges_5_usages_par_m2", "FLOAT64"), ("emission_ges_5_usages", "FLOAT64"),
    ],
    "Logement et bâtiment": [
        ("type_batiment", "STRING"), ("periode_construction", "STRING"), ("annee_construction", "INT64"),
        ("typologie_logement", "STRING"), ("surface_habitable_logement", "FLOAT64"),
        ("surface_habitable_immeuble", "FLOAT64"), ("nombre_appartement", "INT64"),
        ("nombre_niveau_immeuble", "INT64"), ("nombre_niveau_logement", "INT64"),
        ("numero_etage_appartement", "INT64"), ("position_logement_dans_immeuble", "STRING"),
        ("hauteur_sous_plafond", "FLOAT64"), ("classe_altitude", "STRING"), ("zone_climatique", "STRING"),
        ("appartement_non_visite", "INT64"),
    ],
    "Localisation": [
        ("code_insee_ban", "STRING"), ("code_postal_ban", "STRING"), ("nom_commune_ban", "STRING"),
        ("code_departement_ban", "STRING"), ("adresse_ban", "STRING"), ("numero_voie_ban", "STRING"),
        ("nom_rue_ban", "STRING"), ("identifiant_ban", "STRING"),
        ("coordonnee_cartographique_x_ban", "FLOAT64"), ("coordonnee_cartographique_y_ban", "FLOAT64"),
        ("score_ban", "FLOAT64"), ("statut_geocodage", "STRING"),
    ],
    "Chauffage et eau chaude": [
        ("type_energie_principale_chauffage", "STRING"), ("type_generateur_chauffage_principal", "STRING"),
        ("type_installation_chauffage", "STRING"), ("type_installation_ecs", "STRING"),
        ("type_energie_principale_ecs", "STRING"), ("type_generateur_chauffage_principal_ecs", "STRING"),
        ("conso_chauffage_ep", "FLOAT64"), ("conso_ecs_ep", "FLOAT64"), ("conso_chauffage_ef", "FLOAT64"),
        ("conso_ecs_ef", "FLOAT64"), ("emission_ges_chauffage", "FLOAT64"), ("emission_ges_ecs", "FLOAT64"),
        ("type_energie_n1", "STRING"), ("type_energie_n2", "STRING"), ("type_energie_n3", "STRING"),
    ],
    "Enveloppe et confort": [
        ("deperditions_enveloppe", "FLOAT64"), ("deperditions_murs", "FLOAT64"),
        ("deperditions_planchers_hauts", "FLOAT64"), ("deperditions_planchers_bas", "FLOAT64"),
        ("deperditions_portes", "FLOAT64"), ("deperditions_baies_vitrees", "FLOAT64"),
        ("deperditions_ponts_thermiques", "FLOAT64"), ("deperditions_renouvellement_air", "FLOAT64"),
        ("qualite_isolation_enveloppe", "STRING"), ("qualite_isolation_murs", "STRING"),
        ("qualite_isolation_plancher_haut_comble_amenage", "STRING"),
        ("qualite_isolation_plancher_haut_comble_perdu", "STRING"),
        ("qualite_isolation_plancher_haut_toit_terrasse", "STRING"),
        ("qualite_isolation_plancher_bas", "STRING"), ("qualite_isolation_menuiseries", "STRING"),
        ("ubat_w_par_m2_k", "FLOAT64"), ("isolation_toiture", "INT64"), ("inertie_lourde", "INT64"),
        ("classe_inertie_batiment", "STRING"), ("logement_traversant", "INT64"),
        ("indicateur_confort_ete", "STRING"), ("protection_solaire_exterieure", "INT64"),
    ],
    "Coûts": [
        ("cout_total_5_usages", "FLOAT64"), ("cout_chauffage", "FLOAT64"), ("cout_ecs", "FLOAT64"),
        ("cout_refroidissement", "FLOAT64"), ("cout_eclairage", "FLOAT64"), ("cout_auxiliaires", "FLOAT64"),
    ],
    "Ventilation, froid, renouvelables": [
        ("type_ventilation", "STRING"), ("type_generateur_froid", "STRING"),
        ("type_energie_climatisation", "STRING"), ("surface_climatisee", "FLOAT64"),
        ("categorie_enr", "STRING"), ("presence_production_pv", "INT64"),
        ("surface_totale_capteurs_pv", "FLOAT64"), ("production_electricite_pv_kwhep_par_an", "FLOAT64"),
        ("electricite_pv_autoconsommee", "FLOAT64"),
        ("systeme_production_electricite_origine_renouvelable", "STRING"),
    ],
}

# Colonnes ajoutées par la transformation (mêmes règles que la V1)
COLONNES_CALCULEES = [
    ("arrondissement", "INT64"), ("flag_chauffage_electrique", "BOOL"), ("flag_post_reforme_2026", "BOOL"),
]

CHAMPS_API = [nom for champs in GROUPES.values() for nom, _ in champs]
if len(CHAMPS_API) != len(set(CHAMPS_API)):
    raise ValueError("config : champ en double dans GROUPES")
SCHEMA = [(nom, type_bq) for champs in GROUPES.values() for nom, type_bq in champs] + COLONNES_CALCULEES

# Valeurs affichées par --essai, pour fixer les règles avant la collecte complète
CHAMPS_VALEURS_ESSAI = ["type_batiment", "methode_application_dpe", "typologie_logement"]

# Tables BigQuery (dataset BQ_DATASET). La table de travail est recréée à chaque chargement.
TABLE_DPE = "org_dpe_ademe"
TABLE_TRAVAIL = "org_dpe_ademe_travail"
COLONNE_PARTITION = "date_etablissement_dpe"   # partition par mois
CLUSTER = ["arrondissement"]

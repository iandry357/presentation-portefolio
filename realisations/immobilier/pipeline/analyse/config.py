from pathlib import Path

from dotenv import load_dotenv

# Même couture que pipeline/dvf_etalab/config.py : le .env de la V1 est dans pipeline/ et pipeline.config lit
# l'environnement dès l'import, il faut donc le charger avant. Seule dépendance vers la V1 : ces 3 constantes.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from pipeline.config import BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH  # noqa: E402

# --- Paramètres d'exécution ---
LIVRAISON = "2026-10"            # livraison DVF Etalab lue (table dvf_etalab)
DEPARTEMENT = "75"
DATE_DEBUT_FENETRE = "2025-01-01"
DATE_FIN_FENETRE = "2026-06-30"  # fin de la livraison DVF 2026-10

# Typologie ADEME (même source et mêmes champs que scripts/explore_dpe_typologie.py)
API_ADEME = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant"
CHAMP_DEPARTEMENT_ADEME = "code_departement_ban"
CHAMPS_ADEME = ["numero_dpe", "typologie_logement", "date_etablissement_dpe"]
TAILLE_PAGE = 10000
TIMEOUT = 120  # secondes, par requête
MAX_TENTATIVES = 3
DOSSIER_TYPOLOGIE = Path(__file__).resolve().parent.parent / "data" / "bdnb" / "typologie_dpe"

# Axes du cube
PIECES_MAX = 6                   # 6ok = « 6 et plus »
TRANCHES_SURFACE = [25, 40, 60, 80, 120]   # bornes en m², borne basse incluse
LIBELLES_SURFACE = ["1 moins de 25", "2 de 25 à 40", "3 de 40 à 60", "4 de 60 à 80", "5 de 80 à 120", "6 120 et plus"]
ETIQUETTE_INCONNUE = "inconnue"  # ventes non rattachées à un bâtiment (ou bâtiment sans classe)

# Garde-fous
SEUIL_CELLULE = 5                # une cellule de moins de 5 observations est masquée si l'accès est verrouillé
PRIX_M2_MIN = 2000               # règle V1 : ventes hors bornes écartées
PRIX_M2_MAX = 30000

# Sélection DPE de la BDNB (pipeline/bdnb/config.py)
ARRETE_2021 = 1
SUFFIXE_TYPE_DPE = "logement"
METHODE_DPE = "3cl"

# Tables lues (dataset BQ_DATASET)
VUE_VENTES = "dvf_etalab_ventes_logement"
VUE_VENTES_BATIMENT = "dvf_etalab_ventes_batiment"
BDNB_DPE = "bdnb_dpe_logement"
BDNB_REL_DPE_BATIMENT = "bdnb_rel_dpe_batiment"
BDNB_REL_BATIMENT_ADRESSE = "bdnb_rel_batiment_adresse"

# Tables écrites (recréées à chaque exécution)
TABLE_TYPOLOGIE = "dpe_typologie_ademe"
TABLE_VENTES = "agg_analyse_ventes"
TABLE_DPE = "agg_analyse_dpe"

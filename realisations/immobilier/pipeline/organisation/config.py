from pathlib import Path

from dotenv import load_dotenv

# Même couture que pipeline/analyse/config.py : le .env de la V1 est dans pipeline/ et pipeline.config lit
# l'environnement dès l'import, il faut donc le charger avant. Seule dépendance vers la V1 : ces 3 constantes.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from pipeline.config import BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH  # noqa: E402

# --- Paramètres d'exécution ---
LIVRAISON = "2026-10"            # livraison DVF Etalab lue (table dvf_etalab) ; surchargée par --livraison
DEPARTEMENT = "75"               # surchargé par --departement

# Période de la nouvelle organisation : paramètre central, lu par toutes les tables construites ici.
# Le backend et la page Sources la relisent dans la table TABLE_PARAMETRES, jamais en dur.
DATE_DEBUT = "2025-05-01"        # début commun (inclus) ; surchargé par --debut
DATE_FIN = None                  # None : dernière date présente dans la livraison ; surchargé par --fin

# Axes des cubes
PIECES_MAX = 6                   # 6 = « 6 et plus »
TRANCHES_SURFACE = [25, 40, 60, 80, 120]   # bornes en m², borne basse incluse
LIBELLES_SURFACE = ["1 moins de 25", "2 de 25 à 40", "3 de 40 à 60", "4 de 60 à 80", "5 de 80 à 120", "6 120 et plus"]
PRIX_M2_MIN = 2000               # règle V1 : ventes hors bornes écartées du cube (jamais du tableau brut)
PRIX_M2_MAX = 30000

# Règle V1 d'une vente de logement (mêmes valeurs que pipeline/dvf_etalab/config.py) :
# une mutation de nature « Vente », un seul logement, aucun local commercial
NATURE_VENTE = "Vente"
TYPES_LOGEMENT = ["Appartement", "Maison"]
TYPE_LOCAL_COMMERCIAL = "Local industriel. commercial ou assimilé"

# Tables lues (dataset BQ_DATASET)
TABLE_DVF = "dvf_etalab"
VUE_VENTES = "dvf_etalab_ventes_logement"   # vue V1 : sert de contrôle (même nombre de lignes que VUE_DVF_BRUT)
BDNB_BATIMENT_GROUPE = "bdnb_batiment_groupe"
BDNB_ATTRIBUTS_BATIMENT = "bdnb_batiment_attributs"
BDNB_REL_BATIMENT_ADRESSE = "bdnb_rel_batiment_adresse"
BDNB_ADRESSE = "bdnb_adresse"

# Objets écrits (recréés à chaque exécution)
VUE_DVF_BRUT = "org_dvf_brut"
VUE_BATIMENT_BRUT = "org_batiment_brut"
TABLE_CUBE_DVF = "org_cube_dvf"
TABLE_CUBE_BATIMENT = "org_cube_batiment"
TABLE_PARAMETRES = "org_parametres"

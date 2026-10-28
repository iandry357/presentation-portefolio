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
ETIQUETTE_INCONNUE = "inconnue"  # ventes non rattachées à un bâtiment (ou bâtiment sans classe), comme pipeline/analyse/config.py
TOLERANCE_DEBUT_JOURS = 7        # cohérence : écart toléré entre la période paramétrée et le premier jour réellement chargé (week-ends, jours fériés)

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
BDNB_DPE = "bdnb_dpe_logement"
BDNB_REL_DPE_BATIMENT = "bdnb_rel_dpe_batiment"
VUE_VENTES_BATIMENT = "dvf_etalab_ventes_batiment"   # vue V1 des ventes rattachées à un bâtiment
VUE_VENTES_LOYER = "loyers_ventes"                    # vue des ventes rattachées avec loyers de référence
TABLE_TYPOLOGIE = "dpe_typologie_ademe"               # pièces des DPE (typologie ADEME), construite par pipeline/analyse

# Objets écrits (recréés à chaque exécution)
VUE_DVF_BRUT = "org_dvf_brut"
VUE_BATIMENT_BRUT = "org_batiment_brut"
VUE_DPE_BRUT = "org_dpe_brut"
TABLE_CUBE_DVF = "org_cube_dvf"
TABLE_CUBE_BATIMENT = "org_cube_batiment"
TABLE_PARAMETRES = "org_parametres"
TABLE_CUBE_CROISE_VENTES = "org_cube_croise_ventes"
TABLE_CUBE_CROISE_DPE = "org_cube_croise_dpe"
TABLE_CUBE_LOYERS = "org_cube_loyers"

# Page Sources et Qualité : tables écrites par sources.py et qualite.py (recréées à chaque exécution)
TABLE_SOURCES = "org_sources"
TABLE_QUALITE = "org_qualite"

# Autres tables lues par ces deux modules
TABLE_DPE_ADEME = "org_dpe_ademe"             # écrite par pipeline/dpe_ademe ; peut ne pas exister encore
TABLE_BDNB_SOURCES = "bdnb_sources"           # millésimes BDNB (pipeline/bdnb/config.py), repris pour BAN, Fichiers fonciers et DVF open
TABLE_LOYERS_REFERENCE = "loyers_reference"
TABLE_REFERENTIEL = "referentiel_corpus"

# Fiches de la page Sources : champs fixes ; périodes, volumes et dates de chargement sont mesurés par sources.py.
# mesure : table ou vue lue, colonne et type ("date" : période du minimum au maximum ; "annee" : arrêtés du minimum au maximum) ;
# None : pas de mesure. chargee : table dont la date de modification donne la date de chargement (None : pas de chargement).
# fenetre : la période paramétrée (org_parametres) s'applique à cette source.
SOURCES = [
    {
        "source": "DVF Etalab", "editeur": "DGFiP, géolocalisé par Etalab", "version": "livraison 2026-10",
        "publiee": "2026-10-20", "utilisee_par": "DVF, Croisé, Exploration",
        "mesure": {"table": VUE_DVF_BRUT, "colonne": "date_mutation", "type": "date"}, "chargee": TABLE_DVF, "fenetre": True,
        "limites": "Ventes déclarées, avec plusieurs mois de décalage. Seules les ventes d’un seul logement, sans local commercial, sont retenues.",
    },
    {
        "source": "DPE ADEME", "editeur": "ADEME", "version": "collecte depuis le 2025-05-01",
        "publiee": None, "utilisee_par": "DPE",
        "mesure": {"table": TABLE_DPE_ADEME, "colonne": "date_etablissement_dpe", "type": "date"}, "chargee": TABLE_DPE_ADEME,
        "fenetre": True,
        "limites": "Un DPE qui en remplace un autre en indique l’ancien numéro ; l’ancien DPE est le plus souvent absent du jeu.",
    },
    {
        "source": "DPE dans la BDNB", "editeur": "ADEME, assemblé par la BDNB (CSTB)", "version": "millésime 2026-09",
        "publiee": None, "utilisee_par": "Croisé",
        "mesure": {"table": BDNB_DPE, "colonne": "date_etablissement_dpe", "type": "date"}, "chargee": BDNB_DPE, "fenetre": True,
        "limites": "Arrêté 2021, logement, méthode 3CL, rattaché à un immeuble ; s’arrête au millésime. Population différente de la partie DPE (ADEME).",
    },
    {
        "source": "BDNB bâtiments", "editeur": "CSTB", "version": "2026-02.b (v0.7.12)",
        "publiee": "2026-10-07", "utilisee_par": "Bâtiment, Croisé",
        "mesure": None, "chargee": BDNB_ATTRIBUTS_BATIMENT, "fenetre": False,
        "limites": "État du parc au millésime, sans date de transaction. Année de construction absente pour une partie des immeubles.",
    },
    {
        "source": "Loyers (encadrement)", "editeur": "Ville de Paris, Direction du Logement et de l’Habitat",
        "version": "référentiel des loyers", "publiee": None, "utilisee_par": "Exploration, Croisé",
        "mesure": {"table": TABLE_LOYERS_REFERENCE, "colonne": "annee", "type": "annee"}, "chargee": TABLE_LOYERS_REFERENCE,
        "fenetre": True,
        "limites": "Un loyer n’est associé qu’aux ventes rattachées à un quartier, une époque et un nombre de pièces.",
    },
    {
        "source": "Corpus juridique et fiscal", "editeur": "Légifrance (PISTE) et BOFiP", "version": "textes en vigueur à la collecte",
        "publiee": None, "utilisee_par": "Exploration (assistant)",
        "mesure": None, "chargee": TABLE_REFERENTIEL, "fenetre": False,
        "limites": "Réponses limitées aux textes collectés ; ne remplace pas un conseil juridique ou fiscal.",
    },
    {
        "source": "Services en ligne", "editeur": "IGN, cadastre, Géorisques", "version": "consulté à la demande",
        "publiee": None, "utilisee_par": "Exploration (carte)",
        "mesure": None, "chargee": None, "fenetre": False,
        "limites": "Pas de copie locale : disponibilité non garantie.",
    },
]

# Sources reprises telles quelles de TABLE_BDNB_SOURCES : (nom dans bdnb_sources, parties qui les utilisent)
SOURCES_BDNB_REPRISES = [
    ("BAN (adresses)", "Bâtiment"),
    ("Fichiers fonciers", "Bâtiment"),
    ("DVF open (Cerema)", "Qualité du rattachement"),
]

# Cube DPE de la partie DPE (table org_dpe_ademe), recréé à chaque exécution
TABLE_CUBE_DPE = "org_cube_dpe"

# Niveau d'un DPE d'après methode_application_dpe (quatre valeurs sur les 218 309 DPE de 2025-05 à 2026-10). Une méthode absente de
# cette liste arrête la construction : le niveau en dépend.
NIVEAUX_DPE = {
    "dpe appartement individuel": "logement individuel",
    "dpe maison individuelle": "logement individuel",
    "dpe appartement généré à partir des données DPE immeuble": "logement déduit de l'immeuble",
    "dpe immeuble collectif": "immeuble",
}

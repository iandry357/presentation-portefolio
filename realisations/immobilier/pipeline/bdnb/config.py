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


# Postes de déperdition (clé : nom du poste dans l'agrégat, valeur : colonne de bdnb_dpe_logement)
POSTES_DEPERDITION = {
    "murs": "deperdition_mur",
    "baies_vitrees": "deperdition_baie_vitree",
    "plancher_bas": "deperdition_plancher_bas",
    "plancher_haut": "deperdition_plancher_haut",
    "ponts_thermiques": "deperdition_pont_thermique",
    "portes": "deperdition_porte",
}

AGG_PARC_PERIODE = "agg_bdnb_parc_periode"
AGG_PARC_ENERGIE = "agg_bdnb_parc_energie"
AGG_DEPERDITIONS = "agg_bdnb_deperditions"
AGG_GEOCODAGE = "agg_bdnb_geocodage"
AGG_STATS = "agg_bdnb_stats"

# Métadonnées (tables bdnb_sources et bdnb_entonnoir, construites par metadonnees.py)
TABLE_SOURCES = "bdnb_sources"
TABLE_ENTONNOIR = "bdnb_entonnoir"

# Sources de la BDNB, millésimes vérifiés le 2026-10-24 (cahier immobilier-bdnb.md, section 3).
# À mettre à jour à chaque nouveau millésime chargé.
SOURCES = [
    {"source": "BDNB (CSTB)", "millesime": "2026-02.b (v0.7.12)", "couverture": "Paris (75), publié le 2026-10-07"},
    {"source": "DPE ADEME (arrêté 2021)", "millesime": "2026-09", "couverture": "du 2021-06-30 au 2026-09-13"},
    {"source": "DVF open (Cerema)", "millesime": "2025-10-14", "couverture": "ventes de référence de la BDNB (une par immeuble), utilisées pour contrôler le rattachement ; mutations du 2014-01-02 au 2025-06-30"},
    {"source": "DVF Etalab (géolocalisé)", "millesime": "2026-10", "couverture": "mutations du 2021-07-01 au 2026-06-30, publié le 2026-10-20"},
    {"source": "BAN (adresses)", "millesime": "2026T1", "couverture": None},
    {"source": "Fichiers fonciers", "millesime": "2025-12-31", "couverture": None},
]

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
        "limites": "Une ligne par version de DPE : les DPE remplacés restent présents.",
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


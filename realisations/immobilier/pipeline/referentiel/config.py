import os
import re
from pathlib import Path

from dotenv import load_dotenv

# Même couture que pipeline/loyers/config.py : le .env de la V1 est dans pipeline/ (PISTE_* y sont propres à Immobilier)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from pipeline.config import BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH  # noqa: E402

# --- PISTE / Légifrance ---
PISTE_ENV = os.getenv("PISTE_ENV", "sandbox")  # surchargé par --piste-env
PISTE_CLIENT_ID = os.getenv("PISTE_CLIENT_ID")
PISTE_CLIENT_SECRET = os.getenv("PISTE_CLIENT_SECRET")
TIMEOUT = 60  # secondes, par requête
DELAI_APPELS = 0.5  # pause entre deux appels getArticle
CGI_TEXT_ID = "LEGITEXT000006069577"
CCH_TEXT_ID = "LEGITEXT000006074096"
LIBELLE_CGI = "Code général des impôts"
LIBELLE_CCH = "Code de la construction et de l'habitation"
# Pages officielles d'un article (à vérifier à la main sur un article de chaque domaine après la première collecte)
URL_LEGIFRANCE_CODES = "https://www.legifrance.gouv.fr/codes/article_lc/"
URL_LEGIFRANCE_LODA = "https://www.legifrance.gouv.fr/loda/article_lc/"
URL_LEGIFRANCE_JORF = "https://www.legifrance.gouv.fr/jorf/article_jo/"


# Données locales (non versionnées) : même dossier que l'exploration R0
DOSSIER_REFERENTIEL = Path(__file__).resolve().parent.parent / "data" / "referentiel"
DOSSIER_CORPUS = DOSSIER_REFERENTIEL / "corpus"
FICHIER_PISTE_BRUT = "piste_brut.json"
FICHIER_BOFIP_BRUT = "bofip_brut.csv"
FICHIER_CHUNKS = "chunks.json"

# Thèmes d'un chunk (métadonnée obligatoire) ; « changements_recents » : lois de finances, qui datent un changement
THEMES = ["decence", "gel_loyers", "travaux", "revenus_fonciers", "lmnp", "plus_values", "aides", "changements_recents"]
STATUT_EN_VIGUEUR = "en vigueur"
STATUT_EN_DISCUSSION = "en discussion"  # réservé au projet de loi « relance logement » (backlog, hors corpus V1)
ETATS_EN_VIGUEUR = ("VIGUEUR", "ABROGE_DIFF")  # ABROGE_DIFF : encore en vigueur jusqu'à dateFin (ex. article 31 du CGI)
ETAT_A_VENIR = "VIGUEUR_DIFF"  # version à venir, conservée avec sa date de début (backlog 10)

# --- Textes consolidés retrouvés par recherche de titre (fond LODA_DATE) ---
# titre_regex : appliqué au titre sans balises <mark> ; exclut les textes qui « modifient » le texte visé.
# articles : numéro -> thème (liste explicite validée le 2026-10-25) ; None : tous les articles en vigueur du texte.
TEXTES_LEGI = {
    "loi 89-462": {
        "requete": "tendant à améliorer les rapports locatifs", "nature": "LOI",
        "titre_regex": r"^Loi n°\s*89-462 du 6 juillet 1989",
        "type_texte": "loi", "libelle": "Loi n° 89-462 du 6 juillet 1989",
        "articles": {
            "3": "decence", "3-2": "decence", "3-3": "decence", "6": "decence", "20-1": "decence",
            "17": "gel_loyers", "17-1": "gel_loyers", "17-2": "gel_loyers", "23-1": "travaux",
        },
    },
    "décret 2002-120": {
        "requete": "caractéristiques du logement décent", "nature": "DECRET",
        "titre_regex": r"^Décret n°\s*2002-120 du 30 janvier 2002",
        "type_texte": "décret", "libelle": "Décret n° 2002-120 du 30 janvier 2002",
        "articles": {"2": "decence", "3": "decence", "3 bis": "decence", "3 ter": "decence", "4": "decence"},
    },
    "décret 2020-26": {
        "requete": "2020-26", "nature": "DECRET",
        "titre_regex": r"^Décret n°\s*2020-26 du 14 janvier 2020",
        "type_texte": "décret", "libelle": "Décret n° 2020-26 du 14 janvier 2020", "articles": None, "theme": "aides",
    },
    "arrêté du 14 janvier 2020": {
        "requete": "14 janvier 2020 prime de transition énergétique", "nature": "ARRETE",
        "titre_regex": r"^Arrêté du 14 janvier 2020 relatif",
        "type_texte": "arrêté", "libelle": "Arrêté du 14 janvier 2020", "articles": None, "theme": "aides",
    },
    "arrêté du 17 novembre 2020": {
        "requete": "17 novembre 2020 caractéristiques techniques", "nature": "ARRETE",
        "titre_regex": r"^Arrêté du 17 novembre 2020 relatif",
        "type_texte": "arrêté", "libelle": "Arrêté du 17 novembre 2020", "articles": None, "theme": "aides",
    },
}
TITRE_REGEX_COMPILES = {nom: re.compile(cfg["titre_regex"]) for nom, cfg in TEXTES_LEGI.items()}

# Code de la construction et de l'habitation : numéros explicites ; seuls les articles en vigueur sont gardés
ARTICLES_CCH = {
    "L173-1-1": "decence",
    **{num: "decence" for num in (
        "L126-26", "L126-26-1", "L126-27", "L126-28", "L126-28-1", "L126-29", "L126-30", "L126-31", "L126-32", "L126-33",
        "D126-19", "R126-30", "R126-31", "R126-32", "R126-33", "R126-34",
    )},
}

# Code général des impôts : articles cibles (numéros tels que dans PISTE) et thème du texte en vigueur
ARTICLES_CGI = {
    "156": "revenus_fonciers", "31": "revenus_fonciers", "32": "revenus_fonciers",
    "50-0": "lmnp", "39 C": "lmnp", "35": "lmnp", "155": "lmnp", "150 U": "plus_values",
}
# Lois de finances : articles de loi liés aux articles cibles par lienModifications, reconnus à l'intitulé « de finances »
ANNEE_LF_MIN = 2022  # versions du CGI lues à partir du 1er janvier de cette année
THEME_LOIS_FINANCES = "changements_recents"
MOTS_MAX_CHUNK = 500  # au-delà, sous-découpage par alinéa numéroté (I., 1°, a)) ; la référence est conservée

# --- BOFiP (data.economie.gouv.fr, Licence Ouverte v2.0) ---
URL_BOFIP = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/bofip-vigueur"
URL_BOFIP_EXPORT = f"{URL_BOFIP}/exports/csv"
SERIES_BOFIP = ["RFPI", "BIC"]
TYPE_BOFIP = "Contenu"
PARAMETRES_BOFIP = {"delimiter": ";", "with_bom": "false"}
CHAMPS_BOFIP = "type,titre,debut_de_validite,serie,division,identifiant_juridique,permalien,contenu"
# Préfixes d'identifiant retenus (rapport 3e) : revenus fonciers et location meublée ; plus-values et dispositifs historiques exclus
PREFIXES_BOFIP = {
    "BOI-RFPI-BASE-10": "revenus_fonciers", "BOI-RFPI-BASE-20": "revenus_fonciers", "BOI-RFPI-BASE-30": "revenus_fonciers",
    "BOI-RFPI-CHAMP-10": "revenus_fonciers",
    "BOI-RFPI-DECLA-10": "revenus_fonciers", "BOI-RFPI-DECLA-20": "revenus_fonciers", "BOI-RFPI-DECLA-30": "revenus_fonciers",
    "BOI-BIC-CHAMP-40": "lmnp", "BOI-BIC-DEF-10": "lmnp", "BOI-BIC-DEF-20": "lmnp", "BOI-BIC-DECLA-20": "lmnp",
    "BOI-BAREME-000044": "lmnp",
}
MOTS_CHUNK_BOFIP = 300  # taille visée d'un chunk, découpage par paragraphe numéroté

# --- Stockage ---
COLLECTION_CHROMA = "referentiel_immobilier"  # séparée de referentiel_patrimoine
TABLE_CORPUS = "referentiel_corpus"  # traçabilité : un chunk par ligne (dataset BQ_DATASET), recréée à chaque chargement

# --- ChromaDB et embedding-service (OVH) : mêmes variables que pipeline gestion-patrimoine, à définir dans pipeline/.env ---
CHROMA_HOST = os.getenv("CHROMA_HOST")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_USER = os.getenv("CHROMA_USER")
CHROMA_PASSWORD = os.getenv("CHROMA_PASSWORD")
OVH_ORCHESTRATOR_URL = os.getenv("OVH_ORCHESTRATOR_URL")
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL")
EMBEDDING_SERVICE_KEY = "embedding-service"  # clé du registry.yaml de l'orchestrateur
WAKE_TIMEOUT_SEC = 120
WAKE_POLL_INTERVAL_SEC = 3
TAILLE_LOT_EMBEDDING = 8  # mistral-embed : limite de tokens par requête non documentée (16 384 en 2024 d'après un cookbook)
COLLECTION_CHROMA_TRAVAIL = f"{COLLECTION_CHROMA}_travail"  # remplie puis renommée : l'ancienne collection reste intacte en cas d'échec

# --- Embeddings Mistral (remplacent l'embedding-service partagé, jugé insuffisant par la mesure : backlog 40) ---
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_URL_EMBEDDINGS = "https://api.mistral.ai/v1/embeddings"
MISTRAL_MODELE_EMBEDDING = "mistral-embed"
MISTRAL_ESSAIS = 5  # tentatives après une limite de débit (429), pause de 1 s, 2 s, 4 s...

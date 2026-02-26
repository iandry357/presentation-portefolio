from app.core.config import settings

# ============================================================================
# Credentials (depuis Settings / .env)
# ============================================================================

CLIENT_ID     = settings.FRANCE_TRAVAIL_CLIENT_ID
CLIENT_SECRET = settings.FRANCE_TRAVAIL_CLIENT_SECRET

# ============================================================================
# OAuth2 - Token
# ============================================================================

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
TOKEN_REALM = "/partenaire"
TOKEN_SCOPES = "api_offresdemploiv2 o2dsoffre api_romeov2"

# ============================================================================
# Endpoints API
# ============================================================================

BASE_URL      = "https://api.francetravail.io/partenaire"
OFFRES_URL    = f"{BASE_URL}/offresdemploi/v2/offres/search"
OFFRE_URL     = f"{BASE_URL}/offresdemploi/v2/offres"       # + /{ft_id}
ROMEO_URL     = f"{BASE_URL}/romeo/v2/predictionMetiers"

# ============================================================================
# ROMEO - Identification appelant
# ============================================================================

ROMEO_NOM_APPELANT  = "portfolio-iandry"
ROMEO_NB_RESULTATS  = 5
ROMEO_SEUIL_SCORE   = 0.6

# ============================================================================
# Collecte - Zone géographique
# ============================================================================

# Code région Île-de-France par défaut
# Pour couvrir tout le territoire, passer None
DEFAULT_REGION = "11"

# ============================================================================
# Collecte - Limites et pagination
# ============================================================================

OFFRES_MAX_RESULTS  = 50   # nb max d'offres par appel (range France Travail)
OFFRES_RANGE_START  = 0

# ============================================================================
# Scoring
# ============================================================================

# Seuil minimum de score pgvector pour passer à l'enrichissement Crew
SCORING_THRESHOLD   = 0.6

# Nombre d'offres max retenues après scoring pour enrichissement
SCORING_TOP_K       = 20

# ============================================================================
# Enrichissement Crew
# ============================================================================

RECALCUL_MAX        = 3     # nombre max de recalculs par offre

# ============================================================================
# Rate limits France Travail (appels/seconde)
# ============================================================================

RATE_LIMIT_OFFRES   = 10
RATE_LIMIT_ROMEO    = 3
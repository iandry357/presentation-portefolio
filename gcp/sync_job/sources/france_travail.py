"""
Source France Travail — collecte et normalisation vers schéma BigQuery.

Responsabilités :
  - Authentification OAuth France Travail
  - Collecte offres par codes ROME avec fenêtre temporelle configurable
  - Normalisation vers le schéma offres_brutes
  - Parsing salaire best-effort
"""

import hashlib
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ============================================================================
# Constantes API France Travail
# ============================================================================

TOKEN_URL    = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
TOKEN_REALM  = "/partenaire"
TOKEN_SCOPES = "api_offresdemploiv2 o2dsoffre"
OFFRES_URL   = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"

RATE_LIMIT_OFFRES = 10   # appels/seconde max

# ============================================================================
# Token cache (in-memory, durée de vie du job)
# ============================================================================

_token: Optional[str] = None
_token_expires_at: Optional[datetime] = None


def _get_token(client_id: str, client_secret: str) -> str:
    """Retourne un token valide, le renouvelle si expiré."""
    global _token, _token_expires_at

    now = datetime.now(timezone.utc)
    if _token and _token_expires_at and now < _token_expires_at:
        return _token

    logger.info("Renouvellement token France Travail...")

    resp = httpx.post(
        TOKEN_URL,
        params={"realm": TOKEN_REALM},
        data={
            "grant_type":    "client_credentials",
            "client_id":     client_id,
            "client_secret": client_secret,
            "scope":         TOKEN_SCOPES,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    _token = data["access_token"]
    expires_in = data.get("expires_in", 1499)
    _token_expires_at = now + timedelta(seconds=expires_in - 60)

    logger.info(f"Token obtenu, expire dans {expires_in}s")
    return _token


# ============================================================================
# Collecte offres
# ============================================================================

def fetch_offers(
    client_id: str,
    client_secret: str,
    rome_codes: list[str],
    region: str,
    date_min: str,
    date_max: str,
    range_start: int = 0,
    range_end: int = 99,
) -> list[dict]:
    """
    Récupère les offres pour une liste de codes ROME sur une fenêtre temporelle.
    Retourne la liste brute des résultats France Travail.
    """
    token = _get_token(client_id, client_secret)

    params = {
        "codeROME": ",".join(rome_codes),
        "region":   region,
        "range":    f"{range_start}-{range_end}",
        "minCreationDate": date_min,
        "maxCreationDate": date_max,
    }

    resp = httpx.get(
        OFFRES_URL,
        params=params,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=30,
    )

    if resp.status_code == 204:
        logger.info(f"Aucune offre pour ROME={rome_codes} [{date_min} → {date_max}]")
        return []

    resp.raise_for_status()
    data = resp.json()
    offers = data.get("resultats", [])
    logger.info(f"{len(offers)} offre(s) récupérée(s) pour ROME={rome_codes}")
    return offers

def fetch_offers_by_keywords(
    client_id: str,
    client_secret: str,
    keywords: str,
    region: str,
    date_min: str,
    date_max: str,
    range_start: int = 0,
    range_end: int = 99,
) -> list[dict]:
    """
    Récupère les offres par mots-clés (bras 2).
    Retourne la liste brute des résultats France Travail.
    """
    token = _get_token(client_id, client_secret)

    params = {
        "motsCles": keywords,
        "region":   region,
        "range":    f"{range_start}-{range_end}",
        "minCreationDate": date_min,
        "maxCreationDate": date_max,
    }

    resp = httpx.get(
        OFFRES_URL,
        params=params,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=30,
    )

    if resp.status_code == 204:
        logger.info(f"Aucune offre pour motsCles='{keywords}' [{date_min} → {date_max}]")
        return []

    resp.raise_for_status()
    data = resp.json()
    offers = data.get("resultats", [])
    logger.info(f"{len(offers)} offre(s) récupérée(s) pour motsCles='{keywords}'")
    return offers

# ============================================================================
# Parsing salaire
# ============================================================================

# Formats connus :
#   "Annuel de 45000.0 Euros à 65000.0 Euros sur 12.0 mois"
#   "Mensuel de 3500.0 Euros à 4000.0 Euros sur 13.0 mois"
#   "Horaire de 12.5 Euros à 15.0 Euros"

_SALAIRE_PATTERN = re.compile(
    r"(Annuel|Mensuel|Horaire)\s+de\s+([\d.,]+)\s+Euros?\s+à\s+([\d.,]+)",
    re.IGNORECASE,
)
_MOIS_PATTERN = re.compile(r"sur\s+([\d.,]+)\s+mois", re.IGNORECASE)# Formats connus :
#   "Annuel de 45000.0 Euros à 65000.0 Euros sur 12.0 mois"
#   "Mensuel de 3500.0 Euros à 4000.0 Euros sur 13.0 mois"
#   "Horaire de 12.5 Euros à 15.0 Euros"
#   "Annuel de 40000.0 Euros à 50000.0 Euros"
#   "58 - 68 k€ brut annuel"
#   "55 000 - 68 000 €"
#   "43800€ à 67500€"

_SALAIRE_FT = re.compile(
    r"(Annuel|Mensuel|Horaire)\s+de\s+([\d.,]+)\s+Euros?\s+[àa]\s+([\d.,]+)",
    re.IGNORECASE,
)
_MOIS_PATTERN = re.compile(r"sur\s+([\d.,]+)\s+mois", re.IGNORECASE)
_SALAIRE_K = re.compile(
    r"([\d.,]+)\s*[-–]\s*([\d.,]+)\s*k€",
    re.IGNORECASE,
)
_SALAIRE_RANGE = re.compile(
    r"([\d\s.,]+)\s*[-–àa]\s*([\d\s.,]+)\s*€",
    re.IGNORECASE,
)


def _clean_number(s: str) -> float:
    """Nettoie et convertit une chaîne numérique en float."""
    return float(s.replace(" ", "").replace(",", "."))


def _parse_salaire(libelle: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    """
    Extrait salaire_min et salaire_max depuis le libellé brut.
    Normalise tout en annuel brut.
    Retourne (None, None) si parsing échoue.
    """
    if not libelle:
        return None, None

    try:
        # Format France Travail standard
        match = _SALAIRE_FT.search(libelle)
        if match:
            periodicite = match.group(1).lower()
            s_min = _clean_number(match.group(2))
            s_max = _clean_number(match.group(3))
            if periodicite == "mensuel":
                mois_match = _MOIS_PATTERN.search(libelle)
                nb_mois = float(mois_match.group(1)) if mois_match else 12.0
                s_min = s_min * nb_mois
                s_max = s_max * nb_mois
            elif periodicite == "horaire":
                s_min = s_min * 35 * 52
                s_max = s_max * 35 * 52
            return round(s_min, 2), round(s_max, 2)

        # Format "58 - 68 k€"
        match = _SALAIRE_K.search(libelle)
        if match:
            s_min = _clean_number(match.group(1)) * 1000
            s_max = _clean_number(match.group(2)) * 1000
            return round(s_min, 2), round(s_max, 2)

        # Format "55 000 - 68 000 €" ou "43800€ à 67500€"
        match = _SALAIRE_RANGE.search(libelle)
        if match:
            s_min = _clean_number(match.group(1))
            s_max = _clean_number(match.group(2))
            # Sanity check — valeurs plausibles pour un salaire annuel
            if s_min > 500 and s_max > 500:
                return round(s_min, 2), round(s_max, 2)

    except (ValueError, AttributeError) as e:
        logger.debug(f"Parsing salaire échoué pour '{libelle}' : {e}")

    return None, None


# ============================================================================
# Normalisation vers schéma BigQuery
# ============================================================================

def _extract_departement(code_postal: Optional[str]) -> Optional[str]:
    """Extrait le département depuis le code postal (2 ou 3 premiers chiffres)."""
    if not code_postal:
        return None
    cp = code_postal.strip()
    if cp.startswith("97") or cp.startswith("98"):
        return cp[:3]
    return cp[:2]


def _make_id_unique(ft_id: str) -> str:
    return f"france_travail_api_{ft_id}"


def normalize(offer: dict) -> Optional[dict]:
    """
    Normalise une offre brute France Travail vers le schéma BigQuery offres_brutes.
    Retourne None si les champs obligatoires sont manquants.
    """
    ft_id = offer.get("id")
    titre = offer.get("intitule")

    if not ft_id or not titre:
        logger.warning(f"Offre ignorée — id ou intitule manquant : {offer}")
        return None

    # Dates
    date_creation_raw = offer.get("dateCreation", "")
    try:
        date_pub = datetime.fromisoformat(
            date_creation_raw.replace("Z", "+00:00")
        ).date()
    except (ValueError, AttributeError):
        date_pub = date.today()

    # Lieu
    lieu = offer.get("lieuTravail", {})

    # Entreprise
    entreprise = offer.get("entreprise", {})

    # Salaire
    salaire = offer.get("salaire", {})
    salaire_libelle = salaire.get("libelle") or None
    salaire_min, salaire_max = _parse_salaire(salaire_libelle)

    # Compétences — libellés uniquement
    competences_raw = offer.get("competences", [])
    competences = [c["libelle"] for c in competences_raw if c.get("libelle")]

    return {
        "id_unique":                _make_id_unique(ft_id),
        "source":                   "france_travail_api",
        "id_source":                ft_id,
        "date_publication":         date_pub.isoformat(),
        "date_collecte":            datetime.now(timezone.utc).isoformat(),
        "titre":                    titre,
        "description":              offer.get("description") or None,
        "entreprise_nom":           entreprise.get("nom") or None,
        "localisation_libelle":     lieu.get("libelle") or None,
        "localisation_commune":     lieu.get("commune") or None,
        "localisation_departement": _extract_departement(lieu.get("codePostal")),
        "localisation_lat":         lieu.get("latitude"),
        "localisation_lng":         lieu.get("longitude"),
        "type_contrat":             offer.get("typeContrat") or None,
        "type_contrat_libelle":     offer.get("typeContratLibelle") or None,
        "experience_libelle":       offer.get("experienceLibelle") or None,
        "salaire_libelle":          salaire_libelle,
        "salaire_min":              salaire_min,
        "salaire_max":              salaire_max,
        "salaire_present":          salaire_libelle is not None,
        "code_rome":                offer.get("romeCode") or None,
        "libelle_rome":             offer.get("romeLibelle") or None,
        "secteur_activite":         offer.get("secteurActivite") or None,
        "secteur_activite_libelle": offer.get("secteurActiviteLibelle") or None,
        "naf_code":                 offer.get("codeNAF") or None,
        "competences":              competences,
        "url_offre":                offer.get("origineOffre", {}).get("urlOrigine") or None,
        "alternance":               offer.get("alternance"),
    }
import httpx
import logging
from datetime import datetime, timedelta
from typing import Optional
from app.core import france_travail_config as ft

logger = logging.getLogger(__name__)


# ============================================================================
# Token cache (in-memory, par instance)
# ============================================================================

_token: Optional[str] = None
_token_expires_at: Optional[datetime] = None


async def _get_token() -> str:
    """Retourne un token valide, le renouvelle si expiré."""
    global _token, _token_expires_at

    now = datetime.utcnow()
    if _token and _token_expires_at and now < _token_expires_at:
        return _token

    logger.info("Renouvellement du token France Travail...")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            ft.TOKEN_URL,
            params={"realm": ft.TOKEN_REALM},
            data={
                "grant_type":    "client_credentials",
                "client_id":     ft.CLIENT_ID,
                "client_secret": ft.CLIENT_SECRET,
                "scope":         ft.TOKEN_SCOPES,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    _token = data["access_token"]
    expires_in = data.get("expires_in", 1499)
    # Marge de 60s pour éviter d'utiliser un token sur le point d'expirer
    _token_expires_at = now + timedelta(seconds=expires_in - 60)

    logger.info(f"Token France Travail obtenu, expire dans {expires_in}s")
    return _token


async def _headers() -> dict:
    token = await _get_token()
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# ROMEO - Prédiction codes ROME depuis texte profil
# ============================================================================

async def predict_rome_codes(profile_text: str) -> list[dict]:
    """
    Envoie le texte du profil à ROMEO et retourne les codes ROME prédits.

    Retourne une liste de dicts :
    [{"codeRome": "M1805", "libelleRome": "...", "scorePrediction": 0.85}, ...]
    """
    payload = {
        "appellations": [
            {
                "intitule":    profile_text,
                "identifiant": "profil-iandry",
            }
        ],
        "options": {
            "nomAppelant":          ft.ROMEO_NOM_APPELANT,
            "nbResultats":          ft.ROMEO_NB_RESULTATS,
            "seuilScorePrediction": ft.ROMEO_SEUIL_SCORE,
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            ft.ROMEO_URL,
            json=payload,
            headers=await _headers(),
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for prediction in data:
        for metier in prediction.get("metiersRome", []):
            results.append({
                "codeRome":       metier["codeRome"],
                "libelleRome":    metier["libelleRome"],
                "scorePrediction": metier["scorePrediction"],
            })

    logger.info(f"ROMEO : {len(results)} code(s) ROME retourné(s)")
    return results


# ============================================================================
# Offres - Recherche
# ============================================================================

async def search_offers(
    rome_codes: list[str],
    region: Optional[str] = None,
    range_start: int = 0,
    range_end: int = 49,
) -> list[dict]:
    """
    Recherche des offres par codes ROME et zone géographique.

    Retourne la liste brute des offres retournées par France Travail.
    """
    region = region or ft.DEFAULT_REGION

    params = {
        "codeROME": ",".join(rome_codes),
        "region":   region,
        "range":    f"{range_start}-{range_end}",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            ft.OFFRES_URL,
            params=params,
            headers=await _headers(),
        )

        # 204 = aucun résultat
        if resp.status_code == 204:
            logger.info("Aucune offre retournée par France Travail")
            return []

        resp.raise_for_status()
        data = resp.json()

    offers = data.get("resultats", [])
    logger.info(f"France Travail : {len(offers)} offre(s) collectée(s)")
    return offers


# ============================================================================
# Offres - Détail par ft_id
# ============================================================================

async def get_offer_detail(ft_id: str) -> Optional[dict]:
    """
    Retourne le détail complet d'une offre par son identifiant France Travail.
    Retourne None si l'offre n'existe plus (404).
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{ft.OFFRE_URL}/{ft_id}",
            headers=await _headers(),
        )

        if resp.status_code == 404:
            logger.warning(f"Offre {ft_id} introuvable sur France Travail")
            return None

        resp.raise_for_status()
        return resp.json()
"""
Informations d'un point de la carte (vue « Carte » de la page Immobilier), par des API ouvertes de l'IGN, sans clé : adresse la plus
proche (géocodage inverse de la Géoplateforme), parcelle cadastrale qui contient le point et sa surface (API Carto, cadastre), zone du
plan local d'urbanisme (API Carto, Géoportail de l'urbanisme). Cache par coordonnées arrondies et limite de débit en mémoire, par instance.
"""
import asyncio
import json
import logging
import time
from collections import deque
from typing import Optional


import httpx

logger = logging.getLogger(__name__)

# Paramètres
URL_GEOCODAGE_INVERSE = "https://data.geopf.fr/geocodage/reverse"
URL_CADASTRE = "https://apicarto.ign.fr/api/cadastre/parcelle"
URL_URBANISME = "https://apicarto.ign.fr/api/gpu/zone-urba"

DELAI_SEC = 8
NB_TENTATIVES = 2                  # nouvelle tentative sur coupure, 429 ou erreur serveur
PAUSE_TENTATIVE_SEC = 0.5
DECIMALES_CACHE = 5                # environ 1 m : un arrondi plus large déplacerait le point et fausserait la distance à la parcelle
ZONES_MAX = 3                      # zones d'urbanisme gardées (plusieurs documents peuvent se recouvrir)
DUREE_CACHE_SEC = 3600
TAILLE_CACHE_MAX = 2000
CLICS_MAX_PAR_MINUTE = 120         # recherches à l'API par instance du backend (le cache n'en consomme pas)


class GeoplateformeIndisponible(Exception):
    """Les trois appels aux API de l'IGN ont échoué."""



class LimiteAtteinte(Exception):
    """Trop de recherches à l'API en une minute sur cette instance."""


_cache: dict[tuple[float, float], tuple[float, tuple]] = {}
_clics: deque[float] = deque()


def _verifier_limite() -> None:
    maintenant = time.monotonic()
    while _clics and maintenant - _clics[0] > 60:
        _clics.popleft()
    if len(_clics) >= CLICS_MAX_PAR_MINUTE:
        raise LimiteAtteinte()
    _clics.append(maintenant)


async def _requete(client: httpx.AsyncClient, nom: str, url: str, params: dict) -> list[dict]:
    """Entités d'une réponse GeoJSON (liste vide s'il n'y en a pas) ; nouvelle tentative sur coupure, 429 ou erreur serveur."""
    for tentative in range(1, NB_TENTATIVES + 1):
        try:
            r = await client.get(url, params=params)
            r.raise_for_status()
            return r.json().get("features") or []
        except httpx.HTTPStatusError as e:
            logger.warning(f"[immobilier_geoplateforme] {nom} : HTTP {e.response.status_code}, tentative {tentative}/{NB_TENTATIVES}")
            if e.response.status_code < 500 and e.response.status_code != 429:
                break
        except (httpx.TransportError, ValueError) as e:
            logger.warning(f"[immobilier_geoplateforme] {nom} : {type(e).__name__}, tentative {tentative}/{NB_TENTATIVES}")
        if tentative < NB_TENTATIVES:
            await asyncio.sleep(PAUSE_TENTATIVE_SEC)
    raise GeoplateformeIndisponible(nom)


def _geometrie(lat: float, lon: float) -> str:
    """Point GeoJSON (longitude, latitude) attendu par l'API Carto."""
    return json.dumps({"type": "Point", "coordinates": [lon, lat]})


async def _adresse(client: httpx.AsyncClient, lat: float, lon: float) -> Optional[dict]:
    entites = await _requete(client, "adresse", URL_GEOCODAGE_INVERSE, {"lon": lon, "lat": lat, "index": "address", "limit": 1})
    return entites[0]["properties"] if entites else None


async def _parcelle(client: httpx.AsyncClient, lat: float, lon: float) -> Optional[dict]:
    """Parcelle qui contient le point (test d'appartenance), None si le point est sur la voie publique."""
    entites = await _requete(client, "parcelle", URL_CADASTRE, {"geom": _geometrie(lat, lon)})
    return entites[0]["properties"] if entites else None


async def _zones(client: httpx.AsyncClient, lat: float, lon: float) -> list[dict]:
    entites = await _requete(client, "urbanisme", URL_URBANISME, {"geom": _geometrie(lat, lon)})
    return [e["properties"] for e in entites[:ZONES_MAX]]


async def renseigner_point(lat: float, lon: float) -> tuple[Optional[dict], Optional[dict], list[dict], bool]:
    """(adresse, parcelle, zones, complet) : propriétés brutes (les contours ne sont pas conservés).
    complet est faux si un des trois appels a échoué (résultat alors non mis en cache) ;
    lève GeoplateformeIndisponible si les trois échouent, LimiteAtteinte si la limite de débit est dépassée."""
    cle = (round(lat, DECIMALES_CACHE), round(lon, DECIMALES_CACHE))
    en_cache = _cache.get(cle)
    if en_cache and en_cache[0] > time.monotonic():
        return en_cache[1]
    _verifier_limite()

    async with httpx.AsyncClient(timeout=DELAI_SEC) as client:
        resultats = await asyncio.gather(
            _adresse(client, lat, lon), _parcelle(client, lat, lon), _zones(client, lat, lon), return_exceptions=True,
        )
    echecs = [isinstance(r, GeoplateformeIndisponible) for r in resultats]
    for r in resultats:
        if isinstance(r, Exception) and not isinstance(r, GeoplateformeIndisponible):
            raise r
    if all(echecs):
        raise GeoplateformeIndisponible()

    resultat = (
        None if echecs[0] else resultats[0],
        None if echecs[1] else resultats[1],
        [] if echecs[2] else resultats[2],
        not any(echecs),
    )
    if resultat[3]:
        if len(_cache) >= TAILLE_CACHE_MAX:
            _cache.pop(next(iter(_cache)))
        _cache[cle] = (time.monotonic() + DUREE_CACHE_SEC, resultat)
    return resultat


async def plus_proches(lat: float, lon: float) -> tuple[Optional[dict], Optional[dict], bool]:
    """(adresse, parcelle, complet) : propriétés brutes de l'adresse et de la parcelle les plus proches du point.
    complet est faux si un des deux géocodages a échoué (résultat alors non mis en cache) ;
    lève GeoplateformeIndisponible si les deux échouent, LimiteAtteinte si la limite de débit est dépassée."""
    cle = (round(lat, DECIMALES_CACHE), round(lon, DECIMALES_CACHE))
    en_cache = _cache.get(cle)
    if en_cache and en_cache[0] > time.monotonic():
        return en_cache[1]
    _verifier_limite()

    async with httpx.AsyncClient(timeout=DELAI_SEC) as client:
        adresse, parcelle = await asyncio.gather(
            _interroger(client, "address", lat, lon), _interroger(client, "parcel", lat, lon), return_exceptions=True,
        )
    echecs = [isinstance(r, GeoplateformeIndisponible) for r in (adresse, parcelle)]
    for r in (adresse, parcelle):
        if isinstance(r, Exception) and not isinstance(r, GeoplateformeIndisponible):
            raise r
    if all(echecs):
        raise GeoplateformeIndisponible()

    resultat = (None if echecs[0] else adresse, None if echecs[1] else parcelle, not any(echecs))
    if resultat[2]:
        if len(_cache) >= TAILLE_CACHE_MAX:
            _cache.pop(next(iter(_cache)))
        _cache[cle] = (time.monotonic() + DUREE_CACHE_SEC, resultat)
    return resultat

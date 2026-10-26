"""
Route GET /immobilier/georisques (vue « Risques » de la page Immobilier).
Un clic sur la carte -> rapport de risques de l'API Géorisques (ouverte, sans clé) pour ce point.
Aucun stockage : chaque appel interroge l'API.
"""
import asyncio
import logging
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/immobilier/georisques", tags=["Immobilier Géorisques"])

# Paramètres
URL_RAPPORT = "https://georisques.gouv.fr/api/v1/resultats_rapport_risque"
# Géorisques coupe la connexion aux User-Agent inconnus et aux réponses compressées demandées par httpx (vérifié par sonde)
EN_TETES = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept-Encoding": "identity",
}


DELAI_SEC = 10
NB_TENTATIVES = 5                   # Géorisques coupe des connexions au hasard (mesuré : environ 45 % de réussite)
PAUSE_TENTATIVE_SEC = 1
LAT_MIN, LAT_MAX = 48.80, 48.92      # emprise de Paris
LON_MIN, LON_MAX = 2.20, 2.50


class Risque(BaseModel):
    famille: str                          # naturel | technologique
    libelle: str
    statut_commune: Optional[str] = None  # tel que renvoyé par Géorisques, ex. « Risque Existant - faible »
    statut_adresse: Optional[str] = None  # « Risque non Connu » / « Risque non Concerne » : rien d'identifié à ce point


class GeorisquesReponse(BaseModel):
    adresse: Optional[str] = None         # adresse la plus proche du point cliqué
    url_rapport: Optional[str] = None
    risques: List[Risque]


@router.get("", response_model=GeorisquesReponse)
async def georisques(
    lat: float = Query(ge=LAT_MIN, le=LAT_MAX),
    lon: float = Query(ge=LON_MIN, le=LON_MAX),
):
    data = None
    async with httpx.AsyncClient(timeout=DELAI_SEC, headers=EN_TETES) as client:
        for tentative in range(1, NB_TENTATIVES + 1):
            try:
                r = await client.get(URL_RAPPORT, params={"latlon": f"{lon},{lat}"})
                r.raise_for_status()
                data = r.json()
                break
            except httpx.RemoteProtocolError:
                logger.warning(f"[immobilier_georisques] Connexion coupée, tentative {tentative}/{NB_TENTATIVES}")
                await asyncio.sleep(PAUSE_TENTATIVE_SEC)
            except Exception as e:
                logger.error(f"[immobilier_georisques] Erreur : {e}", exc_info=True)
                break
    if data is None:
        raise HTTPException(status_code=502, detail="API Géorisques momentanément indisponible")


    risques = []
    for famille, bloc in (("naturel", data.get("risquesNaturels")), ("technologique", data.get("risquesTechnologiques"))):
        for risque in (bloc or {}).values():
            if risque.get("present"):
                risques.append(Risque(
                    famille=famille,
                    libelle=risque["libelle"],
                    statut_commune=risque.get("libelleStatutCommune"),
                    statut_adresse=risque.get("libelleStatutAdresse"),
                ))
    return GeorisquesReponse(
        adresse=(data.get("adresse") or {}).get("libelle"),
        url_rapport=data.get("url"),
        risques=risques,
    )

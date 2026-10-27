"""
Route GET /immobilier/point (vue « Carte » de la page Immobilier).
Un clic sur la carte -> adresse la plus proche, parcelle cadastrale qui contient le point (avec sa surface) et zone du plan local
d'urbanisme, par les API ouvertes de l'IGN. Aucun stockage ; informations publiques de cadastre, d'adresse et d'urbanisme.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from app.services.immobilier_geoplateforme import GeoplateformeIndisponible, LimiteAtteinte, renseigner_point

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/immobilier/point", tags=["Immobilier carte"])

# Paramètres
LAT_MIN, LAT_MAX = 48.80, 48.92    # emprise de Paris (comme la route Géorisques)
LON_MIN, LON_MAX = 2.20, 2.50


class AdresseProche(BaseModel):
    libelle: str
    distance_m: Optional[int] = None


class ParcelleDuPoint(BaseModel):
    id: str                               # 14 caractères, même format que bdnb_rel_batiment_parcelle
    section: Optional[str] = None
    numero: Optional[str] = None
    contenance_m2: Optional[int] = None   # surface cadastrale de la parcelle


class ZoneUrbanisme(BaseModel):
    code: Optional[str] = None            # ex. « US »
    libelle: Optional[str] = None         # ex. « Zone urbaine Sauvegardée »
    type_zone: Optional[str] = None       # U, AU, A ou N


class PointReponse(BaseModel):
    adresse: Optional[AdresseProche] = None
    parcelle: Optional[ParcelleDuPoint] = None   # absente si le point n'est dans aucune parcelle (voie publique)
    zones_urbanisme: List[ZoneUrbanisme] = []
    donnees_partielles: bool = False      # un des trois appels aux API de l'IGN a échoué


def _entier(valeur) -> Optional[int]:
    return round(valeur) if isinstance(valeur, (int, float)) else None


@router.get("", response_model=PointReponse)
async def point(
    response: Response,
    lat: float = Query(ge=LAT_MIN, le=LAT_MAX),
    lon: float = Query(ge=LON_MIN, le=LON_MAX),
):
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    try:
        adresse, parcelle, zones, complet = await renseigner_point(lat, lon)
    except LimiteAtteinte:
        raise HTTPException(status_code=429, detail="Trop de recherches en peu de temps, réessayez dans une minute")
    except GeoplateformeIndisponible:
        raise HTTPException(status_code=502, detail="Services de l'IGN momentanément indisponibles")

    return PointReponse(
        adresse=AdresseProche(libelle=adresse["label"], distance_m=_entier(adresse.get("distance"))) if adresse else None,
        parcelle=ParcelleDuPoint(
            id=parcelle["idu"],
            section=parcelle.get("section"),
            numero=parcelle.get("numero"),
            contenance_m2=_entier(parcelle.get("contenance")),
        ) if parcelle else None,
        zones_urbanisme=[
            ZoneUrbanisme(code=z.get("libelle"), libelle=z.get("libelong"), type_zone=z.get("typezone")) for z in zones
        ],
        donnees_partielles=not complet,
    )


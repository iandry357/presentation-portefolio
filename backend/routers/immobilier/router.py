"""
Routes FastAPI /immobilier/*.
Pages publiques : parc DPE et prix DVF (tables agrégées BigQuery, mises en cache).
Prix : cellules de moins de SEUIL_VENTES ventes masquées si l'accès est verrouillé.
Changements : liste des DPE refaits (privé, garde stricte).
"""
import logging
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from app.core.access_control import get_access_state, require_access
from app.services.immobilier_bigquery import fetch_agg_dpe, fetch_agg_dvf, fetch_changements
from routers.immobilier.schemas import (
    ChangementLigne, ChangementsResponse, DpeLigne, DpeResponse, PrixLigne, PrixResponse, StatsResponse,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/immobilier", tags=["Immobilier"])

# Paramètres
SEUIL_VENTES = 5              # cellules prix de moins de N ventes masquées si l'accès est verrouillé
TAILLE_DEFAUT = 20            # changements par page
TAILLE_MAX = 100
ETIQUETTES_PASSOIRES = ("F", "G")


def _lecture(ligne: dict) -> str:
    """Électrique + DPE post-réforme : recalcul 2026 probable ; sinon simplement refait."""
    if ligne["flag_chauffage_electrique"] and ligne["flag_post_reforme_2026"]:
        return "recalcul_2026_probable"
    return "refait"


async def _lire_agregats(*fetchers):
    try:
        return [await run_in_threadpool(f) for f in fetchers]
    except Exception as e:
        logger.error(f"[immobilier] Erreur lecture BigQuery : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lecture BigQuery")


# ============================================================================
# GET /immobilier/stats — En-tête (public)
# ============================================================================

@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    dpe, dvf = await _lire_agregats(fetch_agg_dpe, fetch_agg_dvf)
    return StatsResponse(
        nb_dpe=sum(l["nb_dpe"] for l in dpe),
        nb_passoires=sum(l["nb_dpe"] for l in dpe if l["etiquette_dpe"] in ETIQUETTES_PASSOIRES),
        nb_remplacants=sum(l["nb_remplacants"] for l in dpe),
        nb_ventes=sum(l["nb_ventes"] for l in dvf),
        date_maj_dpe=max((l["date_maj"] for l in dpe), default=None),
        date_maj_dvf=max((l["date_maj"] for l in dvf), default=None),
    )


# ============================================================================
# GET /immobilier/dpe — Parc DPE (public)
# ============================================================================

@router.get("/dpe", response_model=DpeResponse)
async def get_dpe(
    arrondissement: Optional[int] = Query(default=None, ge=1, le=20),
    chauffage: Optional[Literal["electrique", "autre"]] = Query(default=None),
):
    (lignes,) = await _lire_agregats(fetch_agg_dpe)
    if arrondissement is not None:
        lignes = [l for l in lignes if l["arrondissement"] == arrondissement]
    if chauffage == "electrique":
        lignes = [l for l in lignes if l["flag_chauffage_electrique"]]
    elif chauffage == "autre":
        lignes = [l for l in lignes if not l["flag_chauffage_electrique"]]
    return DpeResponse(lignes=[DpeLigne(**l) for l in lignes])


# ============================================================================
# GET /immobilier/prix — Prix DVF (public, seuil si verrouillé)
# ============================================================================

@router.get("/prix", response_model=PrixResponse)
async def get_prix(
    arrondissement: Optional[int] = Query(default=None, ge=1, le=20),
    type_local: Optional[Literal["Appartement", "Maison"]] = Query(default=None),
    deverrouille: bool = Depends(get_access_state),
):
    (lignes,) = await _lire_agregats(fetch_agg_dvf)
    if arrondissement is not None:
        lignes = [l for l in lignes if l["arrondissement"] == arrondissement]
    if type_local:
        lignes = [l for l in lignes if l["type_local"] == type_local]

    nb_masquees = 0
    if not deverrouille:
        gardees = [l for l in lignes if l["nb_ventes"] >= SEUIL_VENTES]
        nb_masquees = len(lignes) - len(gardees)
        lignes = gardees

    return PrixResponse(
        seuil_applique=not deverrouille,
        seuil=SEUIL_VENTES,
        nb_masquees=nb_masquees,
        lignes=[PrixLigne(**l) for l in lignes],
    )


# ============================================================================
# GET /immobilier/changements — DPE refaits (privé)
# ============================================================================

@router.get("/changements", response_model=ChangementsResponse, dependencies=[Depends(require_access)])
async def get_changements(
    arrondissement: Optional[int] = Query(default=None, ge=1, le=20),
    etiquette: Optional[Literal["A", "B", "C", "D", "E", "F", "G"]] = Query(default=None),
    chauffage: Optional[Literal["electrique", "autre"]] = Query(default=None),
    post_reforme: Optional[bool] = Query(default=None),
    date_min: Optional[date] = Query(default=None),
    date_max: Optional[date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    taille: int = Query(default=TAILLE_DEFAUT, ge=1, le=TAILLE_MAX),
):
    filtres = (arrondissement, etiquette, chauffage, post_reforme, date_min, date_max)
    try:
        resultat = await run_in_threadpool(fetch_changements, *filtres, page, taille)
        if not resultat["lignes"] and page > 1:
            page = 1   # page au-delà des résultats : retour à la première
            resultat = await run_in_threadpool(fetch_changements, *filtres, page, taille)
    except Exception as e:
        logger.error(f"[immobilier] Erreur lecture changements BigQuery : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lecture BigQuery")

    total = resultat["total"]
    return ChangementsResponse(
        total=total,
        page=page,
        nb_pages=(total + taille - 1) // taille,
        taille=taille,
        nb_recalcul_probable=resultat["nb_recalcul_probable"],
        lignes=[ChangementLigne(**l, lecture=_lecture(l)) for l in resultat["lignes"]],
    )

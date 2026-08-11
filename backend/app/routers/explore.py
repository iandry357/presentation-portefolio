"""
Router /explore — lecture paginée des offres depuis BigQuery.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.bigquery_client import fetch_offers, fetch_filter_options
from app.schemas.explore import ExploreResponse, FilterOptions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/explore", tags=["explore"])


@router.get("", response_model=ExploreResponse)
async def get_explore_offers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    source: Optional[str] = Query(default=None),
    type_contrat: Optional[str] = Query(default=None),
    localisation_libelle: Optional[str] = Query(default=None),
    periode_jours: Optional[int] = Query(default=None, ge=1, le=365),
    titre: Optional[str] = Query(default=None),
    entreprise_nom: Optional[str] = Query(default=None),
    recherche_mot_cle: Optional[str] = Query(default=None),
):
    try:
        result = fetch_offers(
            page=page,
            page_size=page_size,
            source=source,
            type_contrat=type_contrat,
            localisation_libelle=localisation_libelle,
            periode_jours=periode_jours,
            titre=titre,
            entreprise_nom=entreprise_nom,
            recherche_mot_cle=recherche_mot_cle,
        )
        return result
    except Exception as e:
        logger.error(f"[explore] Erreur lecture BigQuery : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lecture BigQuery")


@router.get("/filters", response_model=FilterOptions)
async def get_filter_options():
    try:
        return fetch_filter_options()
    except Exception as e:
        logger.error(f"[explore] Erreur filtres BigQuery : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lecture filtres")
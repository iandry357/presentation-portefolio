"""
Route GET /immobilier/bdnb/bati/analyse (cube des ventes avec attributs du bâti de l'onglet « Bâtiments (BDNB) »).
Agrégats uniquement, aucune donnée d'immeuble ni d'adresse : groupes de moins de SEUIL_BATI ventes masqués si l'accès est verrouillé.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.concurrency import run_in_threadpool

from app.core.access_control import get_access_state
from app.services.immobilier_bdnb_analyse import modalites, modalites_par_dimension, pivoter, resume
from app.services.immobilier_bdnb_bati import DIMENSIONS_BATI, fetch_analyse_bati
from routers.immobilier.bdnb_schemas import AnalyseCellule, AnalyseMeta, AnalyseResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/immobilier/bdnb/bati", tags=["Immobilier BDNB bâti"])

# Paramètres
SEUIL_BATI = 5        # groupes de moins de N ventes masqués si l'accès est verrouillé (comme « Analyse »)
PRIX_M2_MIN = 2000    # bornes de prix du cube (pipeline/analyse/config.py, copiées comme dans bdnb_router.py)
PRIX_M2_MAX = 30000


@router.get("/analyse", response_model=AnalyseResponse)
async def get_analyse_bati(
    response: Response,
    axe: List[str] = Query(...),
    trimestre: Optional[List[str]] = Query(None),
    arrondissement: Optional[List[str]] = Query(None),
    pieces: Optional[List[str]] = Query(None),
    tranche_surface: Optional[List[str]] = Query(None),
    etiquette: Optional[List[str]] = Query(None),
    rattachee: Optional[List[str]] = Query(None),
    epoque_ff: Optional[List[str]] = Query(None),
    taille_copro: Optional[List[str]] = Query(None),
    inondation: Optional[List[str]] = Query(None),
    patrimoine: Optional[List[str]] = Query(None),
    usage_batiment: Optional[List[str]] = Query(None),
    deverrouille: bool = Depends(get_access_state),
):
    response.headers["X-Robots-Tag"] = "noindex, nofollow"

    try:
        lignes = await run_in_threadpool(fetch_analyse_bati)
    except Exception as e:
        logger.error(f"[immobilier_bati] Erreur lecture BigQuery : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lecture BigQuery")
    if not lignes:
        raise HTTPException(status_code=503, detail="Données BDNB indisponibles (cube bâti)")

    if not 1 <= len(axe) <= 2 or len(set(axe)) != len(axe) or any(a not in DIMENSIONS_BATI for a in axe):
        raise HTTPException(
            status_code=422, detail=f"Axes du cube bâti : 1 ou 2 parmi {', '.join(DIMENSIONS_BATI)}, sans doublon",
        )

    filtres: dict[str, set[str]] = {}
    demandes = {
        "trimestre": trimestre, "arrondissement": arrondissement, "pieces": pieces, "tranche_surface": tranche_surface,
        "etiquette": etiquette, "rattachee": rattachee, "epoque_ff": epoque_ff, "taille_copro": taille_copro,
        "inondation": inondation, "patrimoine": patrimoine, "usage_batiment": usage_batiment,
    }
    for dimension, valeurs in demandes.items():
        if not valeurs:
            continue
        inconnues = set(valeurs) - modalites(lignes, dimension)
        if inconnues:
            raise HTTPException(status_code=422, detail=f"Valeurs inconnues pour {dimension} : {sorted(inconnues)}")
        filtres[dimension] = set(valeurs)

    cellules, nb_masquees = pivoter(lignes, "ventes", axe, filtres, SEUIL_BATI, masquer=not deverrouille)
    return AnalyseResponse(
        meta=AnalyseMeta(
            source="ventes_bati",
            axes=axe,
            seuil_applique=not deverrouille,
            seuil=SEUIL_BATI,
            nb_masquees=nb_masquees,
            prix_m2_min=PRIX_M2_MIN,
            prix_m2_max=PRIX_M2_MAX,
            modalites=modalites_par_dimension(lignes, DIMENSIONS_BATI),
            **resume(lignes),
        ),
        cellules=[AnalyseCellule(**c) for c in cellules],
    )

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from ..schemas.market import (
    ExcludedCompaniesResponse,
    ExcludedCompanyAdd,
    MarketQueryParams,
    MarketQueryResult,
    PERIODES,
    SOURCES,
    ExcludedCompanyBatchAdd,
)
from ..services import excluded_companies as excl_svc
from ..services.market_queries import CATALOGUE, execute_query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market", tags=["market"])


# ── Catalogue ─────────────────────────────────────────────────────────────────

@router.get("/catalogue")
def get_catalogue():
    """Retourne la liste des requêtes disponibles avec leurs métadonnées."""
    return {"queries": CATALOGUE}

# ── Entreprises exclues ───────────────────────────────────────────────────────

@router.get("/excluded-companies", response_model=ExcludedCompaniesResponse)
def get_excluded():
    entreprises = excl_svc.get_excluded()
    return ExcludedCompaniesResponse(entreprises=entreprises, total=len(entreprises))


@router.post("/excluded-companies", response_model=ExcludedCompaniesResponse)
def add_excluded(body: ExcludedCompanyAdd):
    try:
        entreprises = excl_svc.add_excluded(body.nom)
    except Exception as e:
        logger.error(f"[market] Erreur ajout entreprise exclue : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors de la mise à jour GCS")
    return ExcludedCompaniesResponse(entreprises=entreprises, total=len(entreprises))

@router.post("/excluded-companies/batch", response_model=ExcludedCompaniesResponse)
def add_excluded_batch(body: ExcludedCompanyBatchAdd):
    try:
        entreprises = excl_svc.add_excluded_batch(body.noms)
    except Exception as e:
        logger.error(f"[market] Erreur ajout batch entreprises exclues : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors de la mise à jour GCS")
    return ExcludedCompaniesResponse(entreprises=entreprises, total=len(entreprises))

@router.delete("/excluded-companies/{nom}", response_model=ExcludedCompaniesResponse)
def remove_excluded(nom: str):
    try:
        entreprises = excl_svc.remove_excluded(nom)
    except Exception as e:
        logger.error(f"[market] Erreur suppression entreprise exclue : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors de la mise à jour GCS")
    return ExcludedCompaniesResponse(entreprises=entreprises, total=len(entreprises))

# ── Exécution requête ─────────────────────────────────────────────────────────

@router.get("/{query_id}", response_model=MarketQueryResult)
def run_query(
    query_id: str,
    periode: PERIODES = Query(default="30j"),
    source:  SOURCES  = Query(default="toutes"),
):
    if query_id not in CATALOGUE:
        raise HTTPException(status_code=404, detail=f"Requête inconnue : {query_id}")

    params = MarketQueryParams(periode=periode, source=source)
    meta   = CATALOGUE[query_id]

    # Vérification cohérence source / source_requise
    if "source_requise" in meta and source not in ("toutes", meta["source_requise"]):
        raise HTTPException(
            status_code=400,
            detail=f"{query_id} est disponible uniquement pour la source '{meta['source_requise']}'",
        )

    try:
        lignes = execute_query(query_id, periode=periode, source=source)
    except NotImplementedError:
        raise HTTPException(status_code=501, detail=f"Requête {query_id} non encore implémentée")
    except Exception as e:
        logger.error(f"[market] Erreur exécution {query_id} : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lors de l'exécution de la requête")

    return MarketQueryResult(
        query_id=query_id,
        titre=meta["titre"],
        description=meta["description"],
        colonnes=meta["colonnes"],
        lignes=lignes,
        total=len(lignes),
        params=params,
    )


"""
Routes FastAPI /immobilier/bdnb/* (onglet « Bâtiments (BDNB) » de la page Immobilier).
Toutes publiques, sur des tables agrégées BigQuery mises en cache ; aucune donnée de bâtiment ni d'adresse.
Prix : classes de moins de SEUIL_VENTES ventes masquées si l'accès est verrouillé.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.core.access_control import get_access_state
from app.services.immobilier_bdnb_bigquery import (
    fetch_deperditions, fetch_entonnoir, fetch_geocodage, fetch_parc_energie, fetch_parc_periode,
    fetch_prix_dpe, fetch_prix_ecart, fetch_sources, fetch_stats,
)
from routers.immobilier.bdnb_schemas import (
    BdnbStatsResponse, DeperditionLigne, EcartPrix, EntonnoirLigne, GeocodageLigne, ParcEnergieLigne,
    ParcPeriodeLigne, ParcResponse, PrixDpeLigne, PrixDpeResponse, SourceLigne, SourcesResponse,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/immobilier/bdnb", tags=["Immobilier BDNB"])

# Paramètres
SEUIL_VENTES = 5              # classes de moins de N ventes masquées si l'accès est verrouillé
SOURCE_BDNB = "BDNB (CSTB)"   # libellé de la source BDNB dans SOURCES (pipeline/bdnb/config.py)


async def _lire(*fetchers):
    try:
        return [await run_in_threadpool(f) for f in fetchers]
    except Exception as e:
        logger.error(f"[immobilier_bdnb] Erreur lecture BigQuery : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lecture BigQuery")


def _premiere_ligne(lignes: list[dict], nom: str) -> dict:
    """Ligne unique d'une table à une ligne ; 503 si la table est vide (agrégats pas encore construits)."""
    if not lignes:
        raise HTTPException(status_code=503, detail=f"Données BDNB indisponibles ({nom})")
    return lignes[0]


def _ecart_pct(median_fg: Optional[float], median_d: Optional[float]) -> Optional[float]:
    """Écart brut des prix médians F+G par rapport à D, en %, arrondi à 0,1."""
    if median_fg is None or not median_d:
        return None
    return round((median_fg / median_d - 1) * 100, 1)


# ============================================================================
# GET /immobilier/bdnb/stats — Bandeau (public)
# ============================================================================

@router.get("/stats", response_model=BdnbStatsResponse)
async def get_stats():
    stats, sources = await _lire(fetch_stats, fetch_sources)
    millesime = next((s["millesime"] for s in sources if s["source"] == SOURCE_BDNB), None)
    return BdnbStatsResponse(**_premiere_ligne(stats, "agg_bdnb_stats"), millesime=millesime)


# ============================================================================
# GET /immobilier/bdnb/prix-dpe — Prix et performance énergétique (public, seuil si verrouillé)
# ============================================================================

@router.get("/prix-dpe", response_model=PrixDpeResponse)
async def get_prix_dpe(deverrouille: bool = Depends(get_access_state)):
    classes, ecarts = await _lire(fetch_prix_dpe, fetch_prix_ecart)
    ecart = _premiere_ligne(ecarts, "agg_bdnb_prix_ecart")
    classes = sorted(classes, key=lambda l: l["classe_dpe"])

    nb_masquees = 0
    if not deverrouille:
        gardees = [l for l in classes if l["nb_ventes"] >= SEUIL_VENTES]
        nb_masquees = len(classes) - len(gardees)
        classes = gardees

    ecart_prix = None
    if deverrouille or min(ecart["nb_fg"], ecart["nb_d"]) >= SEUIL_VENTES:
        ecart_prix = EcartPrix(
            nb_fg=ecart["nb_fg"],
            prix_m2_median_fg=ecart["prix_m2_median_fg"],
            nb_d=ecart["nb_d"],
            prix_m2_median_d=ecart["prix_m2_median_d"],
            ecart_pct=_ecart_pct(ecart["prix_m2_median_fg"], ecart["prix_m2_median_d"]),
        )

    return PrixDpeResponse(
        seuil_applique=not deverrouille,
        seuil=SEUIL_VENTES,
        nb_masquees=nb_masquees,
        date_vente_min=ecart["date_vente_min"],
        prix_m2_min=ecart["prix_m2_min"],
        prix_m2_max=ecart["prix_m2_max"],
        classes=[PrixDpeLigne(**l) for l in classes],
        ecart=ecart_prix,
    )


# ============================================================================
# GET /immobilier/bdnb/parc — Profil du parc (public)
# ============================================================================

@router.get("/parc", response_model=ParcResponse)
async def get_parc():
    periodes, energies, deperditions, stats = await _lire(
        fetch_parc_periode, fetch_parc_energie, fetch_deperditions, fetch_stats,
    )
    # Les 6 postes portent sur les mêmes logements : on compte ceux d'un seul poste
    poste_reference = deperditions[0]["poste"] if deperditions else None
    return ParcResponse(
        periodes=[ParcPeriodeLigne(**l) for l in periodes],
        energies=[ParcEnergieLigne(**l) for l in energies],
        deperditions=[DeperditionLigne(**l) for l in deperditions],
        nb_dpe=_premiere_ligne(stats, "agg_bdnb_stats")["nb_dpe"],
        nb_logements_deperditions=sum(l["nb_logements"] for l in deperditions if l["poste"] == poste_reference),
    )


# ============================================================================
# GET /immobilier/bdnb/sources — Sources et qualité (public)
# ============================================================================

@router.get("/sources", response_model=SourcesResponse)
async def get_sources():
    sources, entonnoir, geocodage = await _lire(fetch_sources, fetch_entonnoir, fetch_geocodage)
    return SourcesResponse(
        sources=[SourceLigne(**l) for l in sorted(sources, key=lambda l: l["source"])],
        entonnoir=[EntonnoirLigne(**l) for l in sorted(entonnoir, key=lambda l: l["etape"])],
        geocodage=[GeocodageLigne(**l) for l in sorted(geocodage, key=lambda l: -l["nb_liens"])],
        date_maj=max((l["date_maj"] for l in sources), default=None),
    )

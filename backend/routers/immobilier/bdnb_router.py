"""
Routes FastAPI /immobilier/bdnb/* (onglet « Bâtiments (BDNB) » de la page Immobilier).
Toutes publiques, sur des tables agrégées BigQuery mises en cache ; aucune donnée de bâtiment ni d'adresse.
Prix : classes de moins de SEUIL_VENTES ventes masquées si l'accès est verrouillé.
"""
import logging
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.concurrency import run_in_threadpool

from app.core.access_control import get_access_state
from app.services.immobilier_bdnb_analyse import (
    DIMENSIONS, DIMENSIONS_LOYERS, modalites, modalites_par_dimension, pivoter, pivoter_loyers, prix_groupe,
    recouvrement_typologie, resume,
)
from app.services.immobilier_bdnb_bigquery import (
    fetch_analyse_dpe, fetch_analyse_ventes, fetch_deperditions, fetch_entonnoir, fetch_geocodage,
    fetch_loyers_ventes, fetch_parc_energie, fetch_parc_periode, fetch_qualite, fetch_sources, fetch_stats,
)
from routers.immobilier.bdnb_schemas import (
    AnalyseCellule, AnalyseMeta, AnalyseResponse, BdnbStatsResponse, DeperditionLigne, EcartPrix, EntonnoirLigne,
    GeocodageLigne, LoyersCellule, LoyersMeta, LoyersResponse, ParcEnergieLigne, ParcPeriodeLigne, ParcResponse,
    PrixDpeLigne, PrixDpeResponse, QualiteMethode, QualiteRattachement, SourceLigne, SourcesResponse,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/immobilier/bdnb", tags=["Immobilier BDNB"])

# Paramètres
SEUIL_VENTES = 5              # classes de moins de N ventes masquées si l'accès est verrouillé
SOURCE_BDNB = "BDNB (CSTB)"   # libellé de la source BDNB dans SOURCES (pipeline/bdnb/config.py)
SEUIL_ANALYSE = 5             # analyse : groupes de moins de N observations masqués si l'accès est verrouillé
PRIX_M2_MIN = 2000            # bornes de prix du cube des ventes (pipeline/analyse/config.py)
PRIX_M2_MAX = 30000
DEPARTEMENT_QUALITE = "75"    # département dont la validation du rattachement est affichée
CLASSES_DPE = {"A", "B", "C", "D", "E", "F", "G"}   # étiquettes comparées (« inconnue » écartée)
CLASSES_PASSOIRES = {"F", "G"}
CLASSE_REFERENCE = {"D"}
SEUIL_LOYERS = 5              # loyers : groupes de moins de N ventes masqués si l'accès est verrouillé
SOURCE_LOYERS = "Ville de Paris, Direction du Logement et de l'Habitat (encadrement des loyers)"
LICENCE_LOYERS = "ODbL"

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


def _precision_pct(ok: int, erreur: int) -> Optional[float]:
    """Rattachements corrects parmi les rattachements retenus, en %, arrondi à 0,1."""
    return round(100 * ok / (ok + erreur), 1) if ok + erreur else None


def _qualite(lignes: list[dict]) -> Optional[QualiteRattachement]:
    """Validation du rattachement des ventes pour la dernière livraison du département ; colonne « confirmé » fusionnée."""
    lignes = [l for l in lignes if l["code_departement"] == DEPARTEMENT_QUALITE]
    if not lignes:
        return None
    livraison = max(l["livraison"] for l in lignes)
    cumul: dict[str, dict[str, int]] = {}
    for l in lignes:
        if l["livraison"] != livraison:
            continue
        c = cumul.setdefault(l["methode"], {"nb_ventes": 0, "nb_ok": 0, "nb_erreur": 0})
        c["nb_ventes"] += l["retrouvees"]
        c["nb_ok"] += l["ok"]
        c["nb_erreur"] += l["erreur"]
    nb_ok = sum(c["nb_ok"] for c in cumul.values())
    nb_erreur = sum(c["nb_erreur"] for c in cumul.values())
    return QualiteRattachement(
        livraison=livraison,
        nb_controle=sum(c["nb_ventes"] for c in cumul.values()),
        nb_ok=nb_ok,
        nb_erreur=nb_erreur,
        precision_pct=_precision_pct(nb_ok, nb_erreur),
        methodes=[
            QualiteMethode(methode=m, precision_pct=_precision_pct(c["nb_ok"], c["nb_erreur"]), **c)
            for m, c in cumul.items()
        ],
    )


# ============================================================================
# GET /immobilier/bdnb/stats — Bandeau (public)
# ============================================================================

@router.get("/stats", response_model=BdnbStatsResponse)
async def get_stats():
    stats, sources, ventes = await _lire(fetch_stats, fetch_sources, fetch_analyse_ventes)
    millesime = next((s["millesime"] for s in sources if s["source"] == SOURCE_BDNB), None)
    periode = resume(ventes) or {}
    return BdnbStatsResponse(
        **_premiere_ligne(stats, "agg_bdnb_stats"),
        nb_transactions=sum(l["nb_ventes"] for l in ventes),
        trimestre_min=periode.get("trimestre_min"),
        trimestre_max=periode.get("trimestre_max"),
        millesime=millesime,
    )


# ============================================================================
# GET /immobilier/bdnb/prix-dpe — Prix et performance énergétique (public, seuil si verrouillé)
# ============================================================================

@router.get("/prix-dpe", response_model=PrixDpeResponse)
async def get_prix_dpe(deverrouille: bool = Depends(get_access_state)):
    (lignes,) = await _lire(fetch_analyse_ventes)
    periode = resume(lignes)
    if periode is None:
        raise HTTPException(status_code=503, detail="Données BDNB indisponibles (cube d'analyse)")

    cellules, nb_masquees = pivoter(
        lignes, "ventes", ["etiquette"], {"etiquette": CLASSES_DPE}, SEUIL_VENTES, masquer=not deverrouille,
    )

    ecart_prix = None
    nb_fg, median_fg = prix_groupe(lignes, {"etiquette": CLASSES_PASSOIRES})
    nb_d, median_d = prix_groupe(lignes, {"etiquette": CLASSE_REFERENCE})
    if deverrouille or min(nb_fg, nb_d) >= SEUIL_VENTES:
        ecart_prix = EcartPrix(
            nb_fg=nb_fg, prix_m2_median_fg=median_fg, nb_d=nb_d, prix_m2_median_d=median_d,
            ecart_pct=_ecart_pct(median_fg, median_d),
        )

    return PrixDpeResponse(
        seuil_applique=not deverrouille,
        seuil=SEUIL_VENTES,
        nb_masquees=nb_masquees,
        trimestre_min=periode["trimestre_min"],
        trimestre_max=periode["trimestre_max"],
        prix_m2_min=PRIX_M2_MIN,
        prix_m2_max=PRIX_M2_MAX,
        classes=[
            PrixDpeLigne(classe_dpe=c["modalites"][0], nb_ventes=c["n"], prix_m2_median=c["mediane"])
            for c in cellules
        ],
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
    sources, entonnoir, geocodage, qualite = await _lire(fetch_sources, fetch_entonnoir, fetch_geocodage, fetch_qualite)
    return SourcesResponse(
        sources=[SourceLigne(**l) for l in sorted(sources, key=lambda l: l["source"])],
        entonnoir=[EntonnoirLigne(**l) for l in sorted(entonnoir, key=lambda l: l["etape"])],
        geocodage=[GeocodageLigne(**l) for l in sorted(geocodage, key=lambda l: -l["nb_liens"])],
        qualite=_qualite(qualite),
        date_maj=max((l["date_maj"] for l in sources), default=None),
    )



# ============================================================================
# GET /immobilier/bdnb/analyse — Cube ventes / DPE (public, seuil si verrouillé)
# ============================================================================

@router.get("/analyse", response_model=AnalyseResponse)
async def get_analyse(
    response: Response,
    source: Literal["ventes", "dpe"],
    axe: List[str] = Query(...),
    trimestre: Optional[List[str]] = Query(None),
    arrondissement: Optional[List[str]] = Query(None),
    pieces: Optional[List[str]] = Query(None),
    tranche_surface: Optional[List[str]] = Query(None),
    etiquette: Optional[List[str]] = Query(None),
    rattachee: Optional[List[str]] = Query(None),
    deverrouille: bool = Depends(get_access_state),
):
    response.headers["X-Robots-Tag"] = "noindex, nofollow"

    (lignes,) = await _lire(fetch_analyse_ventes if source == "ventes" else fetch_analyse_dpe)
    if not lignes:
        raise HTTPException(status_code=503, detail="Données BDNB indisponibles (cube d'analyse)")

    dimensions = DIMENSIONS[source]
    if not 1 <= len(axe) <= 2 or len(set(axe)) != len(axe) or any(a not in dimensions for a in axe):
        raise HTTPException(
            status_code=422, detail=f"Axes pour {source} : 1 ou 2 parmi {', '.join(dimensions)}, sans doublon",
        )

    filtres: dict[str, set[str]] = {}
    demandes = {
        "trimestre": trimestre, "arrondissement": arrondissement, "pieces": pieces,
        "tranche_surface": tranche_surface, "etiquette": etiquette, "rattachee": rattachee,
    }
    for dimension, valeurs in demandes.items():
        if not valeurs:
            continue
        if dimension not in dimensions:
            raise HTTPException(status_code=422, detail=f"Filtre « {dimension} » indisponible pour {source}")
        inconnues = set(valeurs) - modalites(lignes, dimension)
        if inconnues:
            raise HTTPException(status_code=422, detail=f"Valeurs inconnues pour {dimension} : {sorted(inconnues)}")
        filtres[dimension] = set(valeurs)

    cellules, nb_masquees = pivoter(lignes, source, axe, filtres, SEUIL_ANALYSE, masquer=not deverrouille)
    recouvrement = None
    if source == "dpe" and ("pieces" in axe or "pieces" in filtres):
        recouvrement = recouvrement_typologie(lignes, filtres)

    return AnalyseResponse(
        meta=AnalyseMeta(
            source=source,
            axes=axe,
            seuil_applique=not deverrouille,
            seuil=SEUIL_ANALYSE,
            nb_masquees=nb_masquees,
            prix_m2_min=PRIX_M2_MIN if source == "ventes" else None,
            prix_m2_max=PRIX_M2_MAX if source == "ventes" else None,
            recouvrement_typologie=recouvrement,
            modalites=modalites_par_dimension(lignes, dimensions),
            **resume(lignes),
        ),
        cellules=[AnalyseCellule(**c) for c in cellules],
    )


# ============================================================================
# GET /immobilier/bdnb/loyers — Ventes et loyers de référence (public, seuil si verrouillé)
# ============================================================================

@router.get("/loyers", response_model=LoyersResponse)
async def get_loyers(
    response: Response,
    axe: List[str] = Query(...),
    meuble: bool = False,
    trimestre: Optional[List[str]] = Query(None),
    annee_loyer: Optional[List[str]] = Query(None),
    arrondissement: Optional[List[str]] = Query(None),
    pieces: Optional[List[str]] = Query(None),
    epoque: Optional[List[str]] = Query(None),
    deverrouille: bool = Depends(get_access_state),
):
    response.headers["X-Robots-Tag"] = "noindex, nofollow"

    (cube,) = await _lire(fetch_loyers_ventes)
    if not cube:
        raise HTTPException(status_code=503, detail="Données BDNB indisponibles (cube des loyers)")
    # Chaque vente figure une fois par statut meublé : un seul statut par requête, sinon les ventes seraient comptées deux fois
    lignes = [l for l in cube if l["meuble"] == meuble]

    if not 1 <= len(axe) <= 2 or len(set(axe)) != len(axe) or any(a not in DIMENSIONS_LOYERS for a in axe):
        raise HTTPException(
            status_code=422, detail=f"Axes des loyers : 1 ou 2 parmi {', '.join(DIMENSIONS_LOYERS)}, sans doublon",
        )

    filtres: dict[str, set[str]] = {}
    demandes = {
        "trimestre": trimestre, "annee_loyer": annee_loyer, "arrondissement": arrondissement,
        "pieces": pieces, "epoque": epoque,
    }
    for dimension, valeurs in demandes.items():
        if not valeurs:
            continue
        inconnues = set(valeurs) - modalites(lignes, dimension)
        if inconnues:
            raise HTTPException(status_code=422, detail=f"Valeurs inconnues pour {dimension} : {sorted(inconnues)}")
        filtres[dimension] = set(valeurs)

    cellules, nb_masquees = pivoter_loyers(lignes, axe, filtres, SEUIL_LOYERS, masquer=not deverrouille)
    return LoyersResponse(
        meta=LoyersMeta(
            axes=axe,
            meuble=meuble,
            seuil_applique=not deverrouille,
            seuil=SEUIL_LOYERS,
            nb_masquees=nb_masquees,
            prix_m2_min=PRIX_M2_MIN,
            prix_m2_max=PRIX_M2_MAX,
            annees_loyer=sorted({l["annee_loyer"] for l in lignes}),
            source_loyers=SOURCE_LOYERS,
            licence_loyers=LICENCE_LOYERS,
            modalites=modalites_par_dimension(lignes, DIMENSIONS_LOYERS),
            **resume(lignes),
        ),
        cellules=[LoyersCellule(**c) for c in cellules],
    )

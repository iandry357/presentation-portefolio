"""
Routes FastAPI /immobilier/org/* (nouvelle organisation de la page Immobilier).
Lot « métadonnées » : période paramétrée, fiches de sources, indicateurs de qualité (petites tables BigQuery, en cache).
Toutes publiques : aucune donnée de transaction, de bâtiment ni d'adresse.
"""
import logging

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.concurrency import run_in_threadpool

from app.core.access_control import get_access_state
from app.services.immobilier_org_analyse import (
    modalites, modalites_par_dimension, pivoter, pivoter_loyers, prix_groupe, recouvrement_typologie, resume, resume_loyers,
)
from app.services.immobilier_org_bigquery import fetch_cube, fetch_loyers, fetch_parametres, fetch_qualite, fetch_sources
from app.services.immobilier_org_cubes import CUBE_LOYERS, CUBES
from routers.immobilier.org_schemas import (
    AnalyseCellule, AnalyseMeta, AnalyseResponse, EcartPrix, LoyersCellule, LoyersMeta, LoyersResponse, ParametresResponse,
    PrixDpeLigne, PrixDpeResponse, QualiteLigne, QualiteResponse, SourceLigne, SourcesResponse,
)



logger = logging.getLogger(__name__)
router = APIRouter(prefix="/immobilier/org", tags=["Immobilier organisation"])

NOINDEX = "noindex, nofollow"
SEUIL_ANALYSE = 5      # groupes de moins de N observations masqués si l'accès est verrouillé (comme les analyses existantes)
PRIX_M2_MIN = 2000     # bornes de prix des cubes de ventes (pipeline/organisation/config.py, copiées comme dans bati_router.py)
PRIX_M2_MAX = 30000
SEUIL_LOYERS = 5       # loyers : groupes de moins de N ventes masqués si l'accès est verrouillé
SOURCE_LOYERS = "Ville de Paris, Direction du Logement et de l'Habitat (encadrement des loyers)"
LICENCE_LOYERS = "ODbL"
CLASSES_DPE = {"A", "B", "C", "D", "E", "F", "G"}   # étiquettes comparées (« inconnue » écartée)
CLASSES_PASSOIRES = {"F", "G"}
CLASSE_REFERENCE = {"D"}


def _ecart_pct(mediane_fg, mediane_d):
    """Écart brut des prix médians F+G par rapport à D, en %, arrondi à 0,1."""
    if mediane_fg is None or not mediane_d:
        return None
    return round((mediane_fg / mediane_d - 1) * 100, 1)


async def _lire(fetcher, nom: str) -> list[dict]:
    try:
        lignes = await run_in_threadpool(fetcher)
    except Exception as e:
        logger.error(f"[immobilier_org] Erreur lecture BigQuery : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lecture BigQuery")
    if not lignes:
        raise HTTPException(status_code=503, detail=f"Données indisponibles ({nom})")
    return lignes


def _derniere_maj(lignes: list[dict]):
    """Date de mise à jour la plus récente des lignes (chaînes ISO : l'ordre alphabétique est l'ordre chronologique)."""
    return max((l["date_maj"] for l in lignes if l.get("date_maj")), default=None)


# ============================================================================
# GET /immobilier/org/parametres — Période paramétrée (public)
# ============================================================================

@router.get("/parametres", response_model=ParametresResponse)
async def get_parametres(response: Response):
    response.headers["X-Robots-Tag"] = NOINDEX
    lignes = await _lire(fetch_parametres, "org_parametres")
    return ParametresResponse(**lignes[0])


# ============================================================================
# GET /immobilier/org/sources — Fiches de sources (public)
# ============================================================================

@router.get("/sources", response_model=SourcesResponse)
async def get_sources(response: Response):
    response.headers["X-Robots-Tag"] = NOINDEX
    lignes = await _lire(fetch_sources, "org_sources")
    return SourcesResponse(
        sources=[SourceLigne(**{k: v for k, v in l.items() if k != "date_maj"}) for l in sorted(lignes, key=lambda l: l["source"])],
        date_maj=_derniere_maj(lignes),
    )


# ============================================================================
# GET /immobilier/org/qualite — Indicateurs de qualité (public)
# ============================================================================

@router.get("/qualite", response_model=QualiteResponse)
async def get_qualite(response: Response):
    response.headers["X-Robots-Tag"] = NOINDEX
    lignes = await _lire(fetch_qualite, "org_qualite")
    return QualiteResponse(
        indicateurs=[
            QualiteLigne(**{k: v for k, v in l.items() if k != "date_maj"})
            for l in sorted(lignes, key=lambda l: (l["partie"], l["indicateur"]))
        ],
        date_maj=_derniere_maj(lignes),
    )


# ============================================================================
# GET /immobilier/org/analyse/{cube} — Analyse d'un cube du registre (public, seuil si verrouillé)
# ============================================================================

@router.get("/analyse/{cube}", response_model=AnalyseResponse)
async def get_analyse(
    cube: str,
    response: Response,
    axe: List[str] = Query(...),
    filtre: Optional[List[str]] = Query(None),
    deverrouille: bool = Depends(get_access_state),
):
    """axe : 1 ou 2 dimensions du cube ; filtre : « dimension:valeur », répétable (valeurs d'une même dimension = OU)."""
    response.headers["X-Robots-Tag"] = NOINDEX
    if cube not in CUBES:
        raise HTTPException(status_code=404, detail=f"Cube inconnu : {cube} (cubes : {', '.join(CUBES)})")
    definition = CUBES[cube]
    dimensions = definition["dimensions"]
    lignes = await _lire(lambda: fetch_cube(cube), definition["table"])

    if not 1 <= len(axe) <= 2 or len(set(axe)) != len(axe) or any(a not in dimensions for a in axe):
        raise HTTPException(
            status_code=422, detail=f"Axes du cube {cube} : 1 ou 2 parmi {', '.join(dimensions)}, sans doublon",
        )

    filtres: dict[str, set[str]] = {}
    for texte in filtre or []:
        dimension, separateur, valeur = texte.partition(":")
        if not separateur or dimension not in dimensions:
            raise HTTPException(status_code=422, detail=f"Filtre « {texte} » : attendu dimension:valeur, dimension parmi {', '.join(dimensions)}")
        filtres.setdefault(dimension, set()).add(valeur)
    for dimension, valeurs in filtres.items():
        inconnues = valeurs - modalites(lignes, dimension)
        if inconnues:
            raise HTTPException(status_code=422, detail=f"Valeurs inconnues pour {dimension} : {sorted(inconnues)}")

    cellules, nb_masquees = pivoter(cube, lignes, axe, filtres, SEUIL_ANALYSE, masquer=not deverrouille)
    avec_prix = definition["mesure"] == "prix"
    typologie = (
        recouvrement_typologie(lignes, filtres) if cube == "croise_dpe" and ("pieces" in axe or "pieces" in filtres) else None
    )
    return AnalyseResponse(
        meta=AnalyseMeta(
            cube=cube,
            mesure=definition["mesure"],
            axes=axe,
            seuil_applique=not deverrouille,
            seuil=SEUIL_ANALYSE,
            nb_masquees=nb_masquees,
            prix_m2_min=PRIX_M2_MIN if avec_prix else None,
            prix_m2_max=PRIX_M2_MAX if avec_prix else None,
            recouvrement_typologie=typologie,
            modalites=modalites_par_dimension(lignes, dimensions),
            **resume(cube, lignes),
        ),
        cellules=[AnalyseCellule(**c) for c in cellules],
    )


# ============================================================================
# GET /immobilier/org/loyers — Ventes et loyers de référence (public, seuil si verrouillé)
# ============================================================================

@router.get("/loyers", response_model=LoyersResponse)
async def get_loyers(
    response: Response,
    axe: List[str] = Query(...),
    meuble: bool = False,
    filtre: Optional[List[str]] = Query(None),
    deverrouille: bool = Depends(get_access_state),
):
    """axe : 1 ou 2 dimensions du cube des loyers ; filtre : « dimension:valeur », répétable ; meuble : statut des loyers."""
    response.headers["X-Robots-Tag"] = NOINDEX
    cube = await _lire(fetch_loyers, CUBE_LOYERS["table"])
    # Chaque vente figure une fois par statut meublé : un seul statut par requête, sinon les ventes seraient comptées deux fois
    lignes = [l for l in cube if l["meuble"] == meuble]
    dimensions = CUBE_LOYERS["dimensions"]

    if not 1 <= len(axe) <= 2 or len(set(axe)) != len(axe) or any(a not in dimensions for a in axe):
        raise HTTPException(
            status_code=422, detail=f"Axes des loyers : 1 ou 2 parmi {', '.join(dimensions)}, sans doublon",
        )
    filtres: dict[str, set[str]] = {}
    for texte in filtre or []:
        dimension, separateur, valeur = texte.partition(":")
        if not separateur or dimension not in dimensions:
            raise HTTPException(status_code=422, detail=f"Filtre « {texte} » : attendu dimension:valeur, dimension parmi {', '.join(dimensions)}")
        filtres.setdefault(dimension, set()).add(valeur)
    for dimension, valeurs in filtres.items():
        inconnues = valeurs - modalites(lignes, dimension)
        if inconnues:
            raise HTTPException(status_code=422, detail=f"Valeurs inconnues pour {dimension} : {sorted(inconnues)}")

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
            modalites=modalites_par_dimension(lignes, dimensions),
            **resume_loyers(lignes),
        ),
        cellules=[LoyersCellule(**c) for c in cellules],
    )


# ============================================================================
# GET /immobilier/org/ecart-prix — Prix et performance énergétique (public, seuil si verrouillé)
# ============================================================================

@router.get("/ecart-prix", response_model=PrixDpeResponse)
async def get_ecart_prix(response: Response, deverrouille: bool = Depends(get_access_state)):
    """Prix médian au m² par étiquette du bâtiment, et écart brut des passoires (F+G) par rapport à D (cube croise_ventes)."""
    response.headers["X-Robots-Tag"] = NOINDEX
    lignes = await _lire(lambda: fetch_cube("croise_ventes"), CUBES["croise_ventes"]["table"])

    cellules, nb_masquees = pivoter(
        "croise_ventes", lignes, ["etiquette"], {"etiquette": CLASSES_DPE}, SEUIL_ANALYSE, masquer=not deverrouille,
    )
    ecart = None
    nb_fg, mediane_fg = prix_groupe(lignes, {"etiquette": CLASSES_PASSOIRES})
    nb_d, mediane_d = prix_groupe(lignes, {"etiquette": CLASSE_REFERENCE})
    if deverrouille or min(nb_fg, nb_d) >= SEUIL_ANALYSE:
        ecart = EcartPrix(
            nb_fg=nb_fg, prix_m2_median_fg=mediane_fg, nb_d=nb_d, prix_m2_median_d=mediane_d,
            ecart_pct=_ecart_pct(mediane_fg, mediane_d),
        )
    periode = resume("croise_ventes", lignes)
    return PrixDpeResponse(
        seuil_applique=not deverrouille,
        seuil=SEUIL_ANALYSE,
        nb_masquees=nb_masquees,
        mois_min=periode["mois_min"],
        mois_max=periode["mois_max"],
        prix_m2_min=PRIX_M2_MIN,
        prix_m2_max=PRIX_M2_MAX,
        classes=[
            PrixDpeLigne(classe_dpe=c["modalites"][0], nb_ventes=c["n"], prix_m2_median=c["mediane"]) for c in cellules
        ],
        ecart=ecart,
    )

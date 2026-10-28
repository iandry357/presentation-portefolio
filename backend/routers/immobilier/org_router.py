"""
Routes FastAPI /immobilier/org/* (nouvelle organisation de la page Immobilier).
Lot « métadonnées » : période paramétrée, fiches de sources, indicateurs de qualité (petites tables BigQuery, en cache).
Toutes publiques : aucune donnée de transaction, de bâtiment ni d'adresse.
"""
import logging

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.concurrency import run_in_threadpool

from app.core.access_control import get_access_state, require_access
from app.services import immobilier_org_brut as brut
from app.services.immobilier_org_analyse import (
    modalites, modalites_par_dimension, pivoter, pivoter_loyers, prix_groupe, recouvrement_typologie, resume, resume_loyers,
)
from app.services.immobilier_org_bigquery import fetch_cube, fetch_loyers, fetch_parametres, fetch_qualite, fetch_sources
from app.services.immobilier_org_cubes import CUBE_LOYERS, CUBES
from routers.immobilier.org_schemas import (
    AnalyseCellule, AnalyseMeta, AnalyseResponse, BrutApercuResponse, BrutCatalogueResponse, BrutColonne, BrutJeu,
    EcartPrix, LoyersCellule, LoyersMeta, LoyersResponse, ParametresResponse,
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


# ============================================================================
# GET /immobilier/org/brut/* — Tableaux bruts (privé : garde stricte, 403 sans code)
# ============================================================================

async def _bq_brut(fonction, *args):
    try:
        return await run_in_threadpool(fonction, *args)
    except brut.ErreurBrut:
        raise
    except Exception as e:
        logger.error(f"[immobilier_org] Erreur lecture BigQuery (tableau brut) : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lecture BigQuery")


async def _preparer_brut(jeu: str, arrondissement: int, debut: Optional[date], fin: Optional[date], colonnes: Optional[List[str]]):
    """Valide la demande et retourne (colonnes choisies, début, fin, nombre de lignes) ; 422 si le jeu, une colonne, la période
    ou la taille (plafond) est refusé. Un jeu sans date ignore la période."""
    try:
        choisies = brut.choisir_colonnes(jeu, colonnes)
        if brut.colonne_date(jeu) is None:
            debut = fin = None
        else:
            if debut is None:
                debut = date.fromisoformat((await _lire(fetch_parametres, "org_parametres"))[0]["date_debut"])
            if fin is not None and fin < debut:
                raise brut.ErreurBrut(f"Période incohérente : fin {fin} avant début {debut}")
        nb_lignes = await _bq_brut(brut.compter, jeu, arrondissement, debut, fin)
        if nb_lignes > brut.PLAFOND_LIGNES:
            raise brut.ErreurBrut(
                f"{nb_lignes} lignes pour un plafond de {brut.PLAFOND_LIGNES} : réduire la période"
            )
    except brut.ErreurBrut as e:
        raise HTTPException(status_code=422, detail=str(e))
    return choisies, debut, fin, nb_lignes


@router.get("/brut/catalogue", response_model=BrutCatalogueResponse, dependencies=[Depends(require_access)])
async def get_brut_catalogue(response: Response):
    """Jeux, colonnes (défaut, sensible, description), plafond et période par défaut."""
    response.headers["X-Robots-Tag"] = NOINDEX
    parametres = (await _lire(fetch_parametres, "org_parametres"))[0]
    return BrutCatalogueResponse(
        plafond_lignes=brut.PLAFOND_LIGNES,
        lignes_apercu=brut.LIGNES_APERCU,
        formats=brut.FORMATS,
        format_defaut=brut.FORMAT_DEFAUT,
        date_debut_defaut=parametres["date_debut"],
        jeux=[
            BrutJeu(
                jeu=cle, libelle=d["libelle"], source=d["source"], colonne_date=d["colonne_date"],
                colonnes=[BrutColonne(**c) for c in d["colonnes"]],
            )
            for cle, d in brut.JEUX.items()
        ],
    )


@router.get("/brut/{jeu}", response_model=BrutApercuResponse, dependencies=[Depends(require_access)])
async def get_brut_apercu(
    jeu: str,
    response: Response,
    arrondissement: int = Query(..., ge=1, le=20),
    debut: Optional[date] = None,
    fin: Optional[date] = None,
    colonnes: Optional[List[str]] = Query(None),
):
    """Aperçu (premières lignes) et nombre total de lignes ; début par défaut = début de la période paramétrée."""
    response.headers["X-Robots-Tag"] = NOINDEX
    choisies, debut, fin, nb_lignes = await _preparer_brut(jeu, arrondissement, debut, fin, colonnes)
    lignes = await _bq_brut(brut.lire, jeu, arrondissement, debut, fin, choisies, brut.LIGNES_APERCU)
    return BrutApercuResponse(
        jeu=jeu,
        arrondissement=arrondissement,
        date_debut=debut.isoformat() if debut else None,
        date_fin=fin.isoformat() if fin else None,
        nb_lignes=nb_lignes,
        plafond_lignes=brut.PLAFOND_LIGNES,
        colonnes=[BrutColonne(**c) for c in choisies],
        lignes=lignes,
    )


@router.get("/brut/{jeu}/export", dependencies=[Depends(require_access)])
async def get_brut_export(
    jeu: str,
    arrondissement: int = Query(..., ge=1, le=20),
    debut: Optional[date] = None,
    fin: Optional[date] = None,
    colonnes: Optional[List[str]] = Query(None),
    format_csv: str = Query(brut.FORMAT_DEFAUT, alias="format", pattern="^(excel|standard)$"),
    libelles: bool = False,
):
    """CSV du jeu (au plus PLAFOND_LIGNES lignes, sinon 422) : en-têtes aux noms techniques, ou aux libellés si libelles."""
    choisies, debut, fin, _ = await _preparer_brut(jeu, arrondissement, debut, fin, colonnes)
    lignes = await _bq_brut(brut.lire, jeu, arrondissement, debut, fin, choisies, brut.PLAFOND_LIGNES)
    return Response(
        content=brut.csv_bytes(lignes, choisies, format_csv, libelles),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="immobilier_{jeu}_arr{arrondissement:02d}.csv"',
            "X-Robots-Tag": NOINDEX,
            "Cache-Control": "no-store",
        },
    )

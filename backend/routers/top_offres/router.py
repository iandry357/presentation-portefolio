"""
Routes FastAPI /top-offres/*.
Lecture : statistiques publiques (mart_stats) et top du jour privé (mart_top_du_jour, BigQuery),
filtré par les décisions de l'utilisateur et les offres déjà traitées de job_offers (PostgreSQL).
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_control import require_access
from app.core.database import get_db
from app.core.normalisation import normaliser
from app.models.job_offer import JobOffer
from app.models.top_offres import TopOffreDecision, TopOffreTypeEntreprise
from app.services.top_offres_bigquery import (
    fetch_cibles, fetch_entreprises, fetch_offer, fetch_offres_entreprise, fetch_stats, fetch_top_candidates,
)
from routers.top_offres.schemas import (
    DecisionCreate, DecisionResponse, EntrepriseStat, EntreprisesResponse, OffreEntreprise, OffreProche,
    OffresEntrepriseResponse, StatLigne, StatsResponse, TopCompteurs, TopOffre, TopResponse,
    TypeEntrepriseResponse, TypeEntrepriseUpdate,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/top-offres", tags=["Top Offres"])

# Paramètres
JOURS_TOP_DEFAUT = 7
JOURS_STATS_DEFAUT = 30
TOP_N_DEFAUT = 20
JOURS_ENTREPRISES_DEFAUT = 30
ENTREPRISES_N_DEFAUT = 50
STATUTS_TRAITES = ["postule", "enregistre"]   # offres de job_offers déjà traitées par l'utilisateur
SOURCE_FT_BQ = "france_travail_api"           # valeur de `source` dans BigQuery
PREFIXE_ID_FT = "france_travail_api_"         # id_unique = préfixe + identifiant France Travail
SOURCE_FT_JOB_OFFERS = "france_travail"       # valeur de `source_offer` dans job_offers
MAX_DOUBLONS = 5                              # offres proches renvoyées au plus


# ============================================================================
# Lectures PostgreSQL
# ============================================================================

async def _ids_decides(db: AsyncSession) -> Set[str]:
    """id_unique des offres sur lesquelles l'utilisateur a pris une décision."""
    result = await db.execute(select(TopOffreDecision.id_unique))
    return {row[0] for row in result.all()}


async def _cles_traitees(db: AsyncSession) -> Set[Tuple[str, str]]:
    """(titre, entreprise) normalisés des offres postulées / enregistrées de job_offers.
    Les offres sans entreprise sont ignorées : le rapprochement serait trop ambigu."""
    result = await db.execute(
        select(JobOffer.title, JobOffer.company_name).where(JobOffer.status.in_(STATUTS_TRAITES))
    )
    cles: Set[Tuple[str, str]] = set()
    for titre, entreprise in result.all():
        cle = (normaliser(titre), normaliser(entreprise))
        if cle[0] and cle[1]:
            cles.add(cle)
    return cles


async def _types_corriges(db: AsyncSession) -> Dict[str, str]:
    """Types d'entreprise corrigés par l'utilisateur, par nom normalisé."""
    result = await db.execute(
        select(TopOffreTypeEntreprise.nom_normalise, TopOffreTypeEntreprise.type_entreprise)
    )
    return {nom: type_entreprise for nom, type_entreprise in result.all()}


# ============================================================================
# GET /top-offres/stats — Statistiques publiques
# ============================================================================

@router.get("/stats", response_model=StatsResponse)
async def get_stats(jours: int = Query(default=JOURS_STATS_DEFAUT, ge=1, le=365)):
    try:
        lignes = await run_in_threadpool(fetch_stats, jours)
    except Exception as e:
        logger.error(f"[top_offres] Erreur lecture statistiques BigQuery : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lecture BigQuery")

    # Les libellés des cibles sont facultatifs : une erreur n'empêche pas les statistiques
    try:
        cibles = await run_in_threadpool(fetch_cibles)
    except Exception as e:
        logger.warning(f"[top_offres] Libellés des cibles indisponibles : {e}")
        cibles = {}

    return StatsResponse(jours=jours, lignes=[StatLigne(**ligne) for ligne in lignes], cibles=cibles)


# ============================================================================
# GET /top-offres/top — Top du jour (privé)
# ============================================================================

@router.get("/top", response_model=TopResponse, dependencies=[Depends(require_access)])
async def get_top(
    db: AsyncSession = Depends(get_db),
    jours: int = Query(default=JOURS_TOP_DEFAUT, ge=1, le=90),
    limite: int = Query(default=TOP_N_DEFAUT, ge=1, le=50),
    inclure_exclues: bool = Query(default=False),
    une_par_entreprise: bool = Query(default=True),
):
    try:
        candidates = await run_in_threadpool(fetch_top_candidates, jours, inclure_exclues)
    except Exception as e:
        logger.error(f"[top_offres] Erreur lecture top BigQuery : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lecture BigQuery")

    decides = await _ids_decides(db)
    traitees = await _cles_traitees(db)
    corriges = await _types_corriges(db)

    listes: Dict[str, list] = {"a_lire": [], "zone_grise": []}
    groupes_vus: Set[str] = set()

    # Les candidates arrivent triées score DESC, similarite DESC
    for c in candidates:
        if c["id_unique"] in decides:
            continue
        if (c.get("titre_normalise") or "", c.get("entreprise_normalise") or "") in traitees:
            continue
        if une_par_entreprise:
            cle_groupe = c.get("entreprise_normalise") or c["groupe_doublon"]
            if cle_groupe in groupes_vus:
                continue
            groupes_vus.add(cle_groupe)

        type_corrige = corriges.get(c.get("entreprise_normalise") or "")
        listes[c["liste"]].append(TopOffre(**{
            **c,
            "alertes": c.get("alertes") or [],
            "type_entreprise": type_corrige or c.get("type_entreprise") or "non_identifie",
            "type_entreprise_corrige": type_corrige is not None,
            "entreprise_exclue": bool(c.get("entreprise_exclue")),
        }))

    compteurs = TopCompteurs(a_lire=len(listes["a_lire"]), zone_grise=len(listes["zone_grise"]))
    return TopResponse(
        jours=jours,
        a_lire=listes["a_lire"][:limite],
        zone_grise=listes["zone_grise"][:limite],
        compteurs=compteurs,
    )

# ============================================================================
# Entreprises (privé)
# ============================================================================

# Clés de tri ; à égalité, l'ordre alphabétique du nom normalisé (le tri de Python est stable)
CLES_TRI_ENTREPRISES = {
    "nom": lambda e: e.entreprise_normalise,
    "secteur": lambda e: normaliser(e.secteur),
    "type": lambda e: e.type_entreprise,
    "offres": lambda e: (e.nb_offres, e.nb_coeur, e.score_max or 0),
    "coeur": lambda e: (e.nb_coeur, e.nb_a_lire, e.score_max or 0, e.nb_offres),
    "adjacent": lambda e: (e.nb_adjacent, e.nb_coeur, e.score_max or 0),
    "hors_cible": lambda e: (e.nb_hors_cible, e.nb_coeur, e.score_max or 0),
    "a_lire": lambda e: (e.nb_a_lire, e.nb_coeur, e.score_max or 0),
    "score_max": lambda e: (e.score_max or 0, e.nb_coeur, e.nb_offres),
    "derniere_offre": lambda e: e.derniere_offre or "",
}


@router.get("/entreprises", response_model=EntreprisesResponse, dependencies=[Depends(require_access)])
async def get_entreprises(
    db: AsyncSession = Depends(get_db),
    jours: int = Query(default=JOURS_ENTREPRISES_DEFAUT, ge=1, le=90),
    tri: str = Query(
        default="coeur",
        pattern="^(nom|secteur|type|offres|coeur|adjacent|hors_cible|a_lire|score_max|derniere_offre)$",
    ),
    ordre: str = Query(default="desc", pattern="^(asc|desc)$"),
    type_entreprise: Optional[str] = Query(default=None),
    secteur: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    inclure_exclues: bool = Query(default=False),
    limite: int = Query(default=ENTREPRISES_N_DEFAUT, ge=1, le=200),
):
    try:
        lignes = await run_in_threadpool(fetch_entreprises, jours, inclure_exclues)
    except Exception as e:
        logger.error(f"[top_offres] Erreur lecture entreprises BigQuery : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lecture BigQuery")

    corriges = await _types_corriges(db)

    # Options du filtre secteur : tous les secteurs de la période, avant les autres filtres
    secteurs = sorted({
        ligne["secteur"] for ligne in lignes
        if ligne.get("secteur") and ligne["secteur"] != "NON DETERMINE"
    })

    recherche = normaliser(q) if q else ""
    recherche_secteur = normaliser(secteur) if secteur else ""

    entreprises: List[EntrepriseStat] = []
    for ligne in lignes:
        cle = ligne["entreprise_normalise"]
        type_corrige = corriges.get(cle)
        type_affiche = type_corrige or ligne.get("type_entreprise") or "non_identifie"

        if type_entreprise and type_affiche != type_entreprise:
            continue
        if recherche_secteur and recherche_secteur not in normaliser(ligne.get("secteur")):
            continue
        if recherche and recherche not in cle:
            continue

        entreprises.append(EntrepriseStat(**{
            **ligne,
            "type_entreprise": type_affiche,
            "type_entreprise_corrige": type_corrige is not None,
            "entreprise_exclue": bool(ligne.get("entreprise_exclue")),
        }))

    entreprises.sort(key=lambda e: e.entreprise_normalise)
    entreprises.sort(key=CLES_TRI_ENTREPRISES[tri], reverse=(ordre == "desc"))

    # Tri par secteur : les entreprises sans secteur restent en fin de liste, quel que soit le sens
    if tri == "secteur":
        avec_secteur = [e for e in entreprises if e.secteur and e.secteur != "NON DETERMINE"]
        sans_secteur = [e for e in entreprises if not (e.secteur and e.secteur != "NON DETERMINE")]
        entreprises = avec_secteur + sans_secteur

    return EntreprisesResponse(
        jours=jours,
        total=len(entreprises),
        entreprises=entreprises[:limite],
        secteurs=secteurs,
    )


@router.get(
    "/entreprises/offres",
    response_model=OffresEntrepriseResponse,
    dependencies=[Depends(require_access)],
)
async def get_offres_entreprise(
    entreprise: str = Query(..., min_length=1),
    jours: int = Query(default=JOURS_ENTREPRISES_DEFAUT, ge=1, le=90),
):
    """Offres scorées d'une entreprise (à la demande, au dépliage d'une ligne)."""
    cle = normaliser(entreprise)
    if not cle:
        raise HTTPException(status_code=422, detail="Nom d'entreprise invalide")

    try:
        offres = await run_in_threadpool(fetch_offres_entreprise, cle, jours)
    except Exception as e:
        logger.error(f"[top_offres] Erreur lecture offres de l'entreprise : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lecture BigQuery")

    return OffresEntrepriseResponse(
        entreprise_normalise=cle,
        jours=jours,
        offres=[OffreEntreprise(**offre) for offre in offres],
    )


# ============================================================================
# Décisions « intéressé / pas intéressé » (privé)
# ============================================================================

def _ft_id_depuis_offre(offre: dict) -> Optional[str]:
    """Identifiant France Travail d'une offre du mart (id_unique = 'france_travail_api_<ft_id>')."""
    if offre.get("source") != SOURCE_FT_BQ:
        return None
    id_unique = offre["id_unique"]
    return id_unique[len(PREFIXE_ID_FT):] if id_unique.startswith(PREFIXE_ID_FT) else None


async def _chercher_doublons(db: AsyncSession, offre: dict) -> List[OffreProche]:
    """Offres de job_offers proches de l'offre du top : même identifiant France Travail, sinon
    mêmes titre et entreprise normalisés (entreprise vide : pas de rapprochement)."""
    doublons: List[OffreProche] = []
    deja: Set[int] = set()

    ft_id = _ft_id_depuis_offre(offre)
    if ft_id:
        result = await db.execute(
            select(JobOffer.id, JobOffer.title, JobOffer.company_name, JobOffer.status)
            .where(JobOffer.ft_id == ft_id)
        )
        for job_id, titre, entreprise, statut in result.all():
            doublons.append(OffreProche(
                job_offer_id=job_id, title=titre, company_name=entreprise, status=statut, critere="ft_id",
            ))
            deja.add(job_id)

    titre_norm = offre.get("titre_normalise") or ""
    entreprise_norm = offre.get("entreprise_normalise") or ""
    if titre_norm and entreprise_norm:
        result = await db.execute(
            select(JobOffer.id, JobOffer.title, JobOffer.company_name, JobOffer.status)
        )
        for job_id, titre, entreprise, statut in result.all():
            if job_id in deja:
                continue
            if normaliser(titre) == titre_norm and normaliser(entreprise) == entreprise_norm:
                doublons.append(OffreProche(
                    job_offer_id=job_id, title=titre, company_name=entreprise, status=statut,
                    critere="titre_entreprise",
                ))
                deja.add(job_id)

    return doublons[:MAX_DOUBLONS]


def _date_publication(offre: dict) -> datetime:
    """Date de publication de l'offre du mart (UTC) ; à défaut date de collecte, puis maintenant."""
    for cle in ("date_publication", "date_collecte"):
        valeur = offre.get(cle)
        if not valeur:
            continue
        try:
            date_offre = datetime.fromisoformat(valeur)
        except ValueError:
            continue
        return date_offre if date_offre.tzinfo else date_offre.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _creer_brouillon(offre: dict, ft_id: Optional[str]) -> JobOffer:
    """Ligne job_offers au statut brouillon : métadonnées du mart ; la description et la présentation
    de l'entreprise sont saisies à la main ensuite (modale « Modifier »)."""
    source = offre.get("source") or "manuel"
    raw_data = {
        "intitule": offre["titre"],
        "description": "",
        "typeContratLibelle": offre.get("type_contrat_libelle") or "",
        "experienceLibelle": "",
        "salaire": {"libelle": offre.get("salaire_libelle") or ""},
        "dureeTravailLibelleConverti": "",
        "secteurActiviteLibelle": "",
        "entreprise": {"nom": offre.get("entreprise_nom") or "", "description": ""},
        "competences": [],
        "qualitesProfessionnelles": [],
        "contexteTravail": {"horaires": ""},
    }
    return JobOffer(
        ft_id=ft_id,
        source_offer=SOURCE_FT_JOB_OFFERS if source == SOURCE_FT_BQ else source,
        title=offre["titre"][:255],
        description=None,
        company_name=(offre.get("entreprise_nom") or None),
        company_description=None,
        location_label=offre.get("localisation_libelle"),
        contract_type=(offre.get("type_contrat_libelle") or "")[:50] or None,
        salary_label=offre.get("salaire_libelle"),
        offer_url=offre.get("url_offre"),
        raw_data=raw_data,
        status="brouillon",
        label="basique",
        ft_published_at=_date_publication(offre),
    )


@router.post("/decisions", response_model=DecisionResponse, dependencies=[Depends(require_access)])
async def create_decision(body: DecisionCreate, db: AsyncSession = Depends(get_db)):
    try:
        offre = await run_in_threadpool(fetch_offer, body.id_unique)
    except Exception as e:
        logger.error(f"[top_offres] Erreur lecture offre BigQuery : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur lecture BigQuery")
    if not offre:
        raise HTTPException(status_code=404, detail="Offre introuvable dans le top du jour")

    decision = await db.get(TopOffreDecision, body.id_unique)

    if decision and decision.decision == "interesse":
        if body.decision == "interesse":
            # Un seul brouillon par offre : rien à recréer
            return DecisionResponse(
                resultat="decision_enregistree", decision="interesse", job_offer_id=decision.job_offer_id,
            )
        raise HTTPException(
            status_code=409,
            detail="Un brouillon est lié à cette offre : gérez-le depuis /jobs",
        )

    job_offer_id: Optional[int] = None
    if body.decision == "interesse":
        if body.utiliser_job_offer_id is not None:
            existante = await db.get(JobOffer, body.utiliser_job_offer_id)
            if not existante:
                raise HTTPException(status_code=404, detail="Offre de /jobs introuvable")
            job_offer_id = existante.id
        else:
            doublons = await _chercher_doublons(db, offre)
            if doublons and not body.confirmer:
                return DecisionResponse(resultat="doublon_detecte", doublons=doublons)
            ft_id = _ft_id_depuis_offre(offre)
            if any(d.critere == "ft_id" for d in doublons):
                ft_id = None   # index unique sur job_offers.ft_id : le brouillon forcé n'en porte pas
            brouillon = _creer_brouillon(offre, ft_id)
            db.add(brouillon)
            await db.flush()
            job_offer_id = brouillon.id

    if decision:
        decision.decision = body.decision
        decision.job_offer_id = job_offer_id
    else:
        db.add(TopOffreDecision(
            id_unique=body.id_unique,
            decision=body.decision,
            job_offer_id=job_offer_id,
            groupe_doublon=offre["groupe_doublon"],
            titre_normalise=offre.get("titre_normalise") or "",
            entreprise_normalise=offre.get("entreprise_normalise") or "",
        ))
    await db.commit()

    return DecisionResponse(
        resultat="decision_enregistree", decision=body.decision, job_offer_id=job_offer_id,
    )


@router.delete("/decisions", dependencies=[Depends(require_access)])
async def delete_decision(
    id_unique: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    """Annule une décision « pas intéressé » : l'offre réapparaît dans le top."""
    decision = await db.get(TopOffreDecision, id_unique)
    if not decision:
        raise HTTPException(status_code=404, detail="Décision introuvable")
    if decision.decision == "interesse":
        raise HTTPException(
            status_code=409,
            detail="Un brouillon est lié à cette offre : gérez-le depuis /jobs",
        )
    await db.delete(decision)
    await db.commit()
    return {"ok": True}


# ============================================================================
# Types d'entreprise corrigés (privé)
# ============================================================================

@router.get(
    "/types-entreprise",
    response_model=List[TypeEntrepriseResponse],
    dependencies=[Depends(require_access)],
)
async def list_types_entreprise(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TopOffreTypeEntreprise).order_by(TopOffreTypeEntreprise.nom_normalise)
    )
    return result.scalars().all()


@router.put(
    "/types-entreprise/{nom}",
    response_model=TypeEntrepriseResponse,
    dependencies=[Depends(require_access)],
)
async def set_type_entreprise(
    nom: str,
    body: TypeEntrepriseUpdate,
    db: AsyncSession = Depends(get_db),
):
    nom_normalise = normaliser(nom)
    if not nom_normalise:
        raise HTTPException(status_code=422, detail="Nom d'entreprise invalide")

    ligne = await db.get(TopOffreTypeEntreprise, nom_normalise)
    if ligne:
        ligne.type_entreprise = body.type_entreprise
        ligne.commentaire = body.commentaire
    else:
        ligne = TopOffreTypeEntreprise(
            nom_normalise=nom_normalise,
            type_entreprise=body.type_entreprise,
            commentaire=body.commentaire,
        )
        db.add(ligne)
    await db.commit()
    await db.refresh(ligne)
    return ligne


@router.delete("/types-entreprise/{nom}", dependencies=[Depends(require_access)])
async def delete_type_entreprise(nom: str, db: AsyncSession = Depends(get_db)):
    """Supprime la correction : le type affiché redevient l'automatique."""
    ligne = await db.get(TopOffreTypeEntreprise, normaliser(nom))
    if not ligne:
        raise HTTPException(status_code=404, detail="Correction introuvable")
    await db.delete(ligne)
    await db.commit()
    return {"ok": True}

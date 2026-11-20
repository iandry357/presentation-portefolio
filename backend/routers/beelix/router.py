"""
Routes FastAPI /beelix/* — signaux de prospection pour une commerciale.
BigQuery beelix_veille (offres_signaux, articles_bruts) pour les vues, ChromaDB pour le RAG.
"""
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from google.cloud import bigquery
from google.oauth2 import service_account

from app.core.config import settings
from routers.beelix.schemas import (
    BeelixStats,
    SecteurItem, SecteursResponse,
    CompteItem, ComptesResponse,
    OffreItem, OffresResponse,
    ConcurrentItem, ConcurrenceResponse,
    BesoinItem, BesoinsResponse,
    TendancePoint, TendanceResponse,
    NewsItem, NewsResponse,
    RagRequest, RagResponse, RagSource,
)
from routers.beelix import rag as rag_service

from app.services.orchestrator_client import wake, heartbeat

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/beelix", tags=["Beelix"])

BQ_PROJECT_ID = "gen-lang-client-0989575872"
BQ_DATASET    = "beelix_veille"
T_OFFRES      = f"`{BQ_PROJECT_ID}.{BQ_DATASET}.offres_signaux`"
T_NEWS        = f"`{BQ_PROJECT_ID}.{BQ_DATASET}.articles_bruts`"

# Secteurs cibles de Beelix — à garder aligné avec realisations/beelix/pipeline/config.py
SECTEURS_CIBLES = [
    "banque_finance_assurance",
    "energie",
    "automobile",
    "medias_telecoms",
    "defense",
    "luxe_retail",
]
SECTEUR_CONCURRENCE = "concurrence"

# Familles de profils détectées dans les titres (RE2, sur le titre en minuscules) ; le premier motif l'emporte
FAMILLES = [
    ("Data Scientist", r"data scien|scientifique des donn"),
    ("Data Engineer", r"data engineer|ing[ée]nieur(e)? (de |des )?donn|ing[ée]nieur(e)? data|dataops|big data"),
    ("IA / Machine Learning", r"\bia\b|\bai\b|machine learning|\bml\b|deep learning|\bllm|\bnlp\b|mlops|computer vision|intelligence artificielle|genai|g[ée]n[ée]rative"),
    ("Data Analyst / BI", r"data analy|analyste|business intelligence|\bbi\b|power ?bi|reporting"),
    ("Architecte", r"architect"),
    ("Cloud / DevOps", r"devops|cloud|\bsre\b|kubernetes|platform engineer"),
    ("Chef de projet / PO", r"chef de projet|project manager|product owner|\bpo\b|product manager|scrum"),
    ("Développeur", r"d[ée]veloppeu|developer|software engineer|full ?stack|backend|frontend"),
]
FAMILLE_AUTRE = "Autre"


def _famille_sql() -> str:
    """Expression CASE qui range un titre dans une famille de profils."""
    branches = "\n".join(
        f"            WHEN REGEXP_CONTAINS(LOWER(titre), r'{motif}') THEN '{famille}'"
        for famille, motif in FAMILLES
    )
    return f"CASE\n{branches}\n            ELSE '{FAMILLE_AUTRE}'\n        END"


# ─────────────────────────────────────────
# BigQuery client (compte de service SG)
# ─────────────────────────────────────────
def _get_bq_client() -> bigquery.Client:
    if not settings.GCP_SERVICE_ACCOUNT_JSON_SG:
        raise RuntimeError("GCP_SERVICE_ACCOUNT_JSON_SG non configuré")
    sa_info = json.loads(settings.GCP_SERVICE_ACCOUNT_JSON_SG)
    credentials = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return bigquery.Client(project=BQ_PROJECT_ID, credentials=credentials)


def _query(sql: str, params: Optional[list] = None) -> list:
    """Exécute une requête paramétrée et renvoie les lignes."""
    client = _get_bq_client()
    job_config = bigquery.QueryJobConfig(query_parameters=params or [])
    return list(client.query(sql, job_config=job_config).result())


def _secteurs(secteur: Optional[str], autorises: List[str]) -> List[str]:
    """Liste des secteurs filtrés : un secteur autorisé, ou les secteurs cibles par défaut."""
    if secteur is None:
        return SECTEURS_CIBLES
    if secteur not in autorises:
        raise HTTPException(status_code=400, detail=f"Secteur inconnu : {secteur}")
    return [secteur]


def _texte(valeur) -> Optional[str]:
    return str(valeur) if valeur is not None else None


# ─────────────────────────────────────────
# Stats
# ─────────────────────────────────────────
@router.get("/stats", response_model=BeelixStats)
def get_stats():
    """Compteurs globaux : période réelle, cibles, concurrence, actualités."""
    try:
        row = _query(
            f"""
            SELECT
                MIN(DATE(date_collecte)) AS periode_debut,
                MAX(DATE(date_collecte)) AS periode_fin,
                COUNT(*) AS total_offres,
                COUNTIF(secteur IN UNNEST(@cibles)) AS offres_cibles,
                COUNT(DISTINCT IF(secteur IN UNNEST(@cibles), entreprise_normalise, NULL)) AS comptes_cibles,
                COUNTIF(secteur = @concurrence) AS offres_concurrence,
                COUNT(DISTINCT IF(secteur = @concurrence, entreprise_normalise, NULL)) AS nb_concurrents,
                MAX(charge_le) AS charge_le
            FROM {T_OFFRES}
            """,
            [
                bigquery.ArrayQueryParameter("cibles", "STRING", SECTEURS_CIBLES),
                bigquery.ScalarQueryParameter("concurrence", "STRING", SECTEUR_CONCURRENCE),
            ],
        )[0]
        try:
            total_news = _query(
                f"""
                SELECT COUNT(*) AS total
                FROM {T_NEWS}
                WHERE COALESCE(JSON_VALUE(metadata, '$.chunk_index'), '0') = '0'
                """
            )[0].total
        except Exception:
            total_news = 0
        return BeelixStats(
            periode_debut=_texte(row.periode_debut),
            periode_fin=_texte(row.periode_fin),
            total_offres=row.total_offres,
            offres_cibles=row.offres_cibles,
            comptes_cibles=row.comptes_cibles,
            offres_concurrence=row.offres_concurrence,
            nb_concurrents=row.nb_concurrents,
            total_news=total_news,
            charge_le=_texte(row.charge_le),
        )
    except Exception as e:
        logger.error(f"❌ /beelix/stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# Secteurs
# ─────────────────────────────────────────
@router.get("/secteurs", response_model=SecteursResponse)
def get_secteurs():
    """Une ligne par secteur : offres, entreprises, cible ou non."""
    try:
        rows = _query(
            f"""
            SELECT
                secteur,
                ANY_VALUE(secteur_libelle) AS libelle,
                COUNT(*) AS nb_offres,
                COUNT(DISTINCT entreprise_normalise) AS nb_entreprises
            FROM {T_OFFRES}
            GROUP BY secteur
            ORDER BY nb_offres DESC
            """
        )
        return SecteursResponse(items=[
            SecteurItem(
                secteur=r.secteur,
                libelle=r.libelle or r.secteur,
                nb_offres=r.nb_offres,
                nb_entreprises=r.nb_entreprises,
                cible=r.secteur in SECTEURS_CIBLES,
            )
            for r in rows
        ])
    except Exception as e:
        logger.error(f"❌ /beelix/secteurs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# Comptes qui recrutent
# ─────────────────────────────────────────
@router.get("/comptes", response_model=ComptesResponse)
def get_comptes(
    secteur: Optional[str] = Query(None, description="Secteur cible ; absent = les 6 secteurs Beelix"),
    limit: int = Query(20, ge=1, le=100),
):
    """Entreprises des secteurs cibles, classées par nombre d'offres."""
    secteurs = _secteurs(secteur, SECTEURS_CIBLES)
    try:
        rows = _query(
            f"""
            SELECT
                entreprise_normalise,
                ANY_VALUE(entreprise_nom) AS entreprise_nom,
                ANY_VALUE(secteur) AS secteur,
                ANY_VALUE(secteur_libelle) AS secteur_libelle,
                ANY_VALUE(naf_libelle) AS naf_libelle,
                COUNT(*) AS nb_offres,
                MAX(COALESCE(date_publication, DATE(date_collecte))) AS derniere_offre,
                ARRAY_AGG(titre IGNORE NULLS ORDER BY date_collecte DESC LIMIT 3) AS titres_recents,
                COUNT(*) OVER () AS total
            FROM {T_OFFRES}
            WHERE secteur IN UNNEST(@secteurs)
              AND COALESCE(entreprise_normalise, '') != ''
            GROUP BY entreprise_normalise
            ORDER BY nb_offres DESC, derniere_offre DESC
            LIMIT @limit
            """,
            [
                bigquery.ArrayQueryParameter("secteurs", "STRING", secteurs),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
            ],
        )
        return ComptesResponse(
            secteur=secteur,
            total=rows[0].total if rows else 0,
            items=[
                CompteItem(
                    entreprise_nom=r.entreprise_nom or r.entreprise_normalise,
                    entreprise_normalise=r.entreprise_normalise,
                    secteur=r.secteur,
                    secteur_libelle=r.secteur_libelle or r.secteur,
                    naf_libelle=r.naf_libelle,
                    nb_offres=r.nb_offres,
                    derniere_offre=_texte(r.derniere_offre),
                    titres_recents=list(r.titres_recents or []),
                )
                for r in rows
            ],
        )
    except Exception as e:
        logger.error(f"❌ /beelix/comptes error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# Offres (dépliage d'un compte ou d'un secteur)
# ─────────────────────────────────────────
@router.get("/offres", response_model=OffresResponse)
def get_offres(
    secteur: Optional[str] = Query(None),
    entreprise: Optional[str] = Query(None, description="entreprise_normalise"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Offres détaillées, filtrées par secteur et/ou entreprise, les plus récentes d'abord."""
    secteurs = _secteurs(secteur, SECTEURS_CIBLES + [SECTEUR_CONCURRENCE])
    try:
        rows = _query(
            f"""
            SELECT
                id_unique, titre, entreprise_nom, secteur_libelle, localisation_libelle,
                type_contrat_libelle, url_offre,
                COALESCE(date_publication, DATE(date_collecte)) AS date_offre,
                COUNT(*) OVER () AS total
            FROM {T_OFFRES}
            WHERE secteur IN UNNEST(@secteurs)
              AND (@entreprise IS NULL OR entreprise_normalise = @entreprise)
            ORDER BY date_collecte DESC
            LIMIT @limit OFFSET @offset
            """,
            [
                bigquery.ArrayQueryParameter("secteurs", "STRING", secteurs),
                bigquery.ScalarQueryParameter("entreprise", "STRING", entreprise),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
                bigquery.ScalarQueryParameter("offset", "INT64", offset),
            ],
        )
        return OffresResponse(
            total=rows[0].total if rows else 0,
            items=[
                OffreItem(
                    id_unique=r.id_unique,
                    titre=r.titre,
                    entreprise_nom=r.entreprise_nom,
                    secteur_libelle=r.secteur_libelle,
                    localisation_libelle=r.localisation_libelle,
                    type_contrat_libelle=r.type_contrat_libelle,
                    date=_texte(r.date_offre),
                    url=r.url_offre,
                )
                for r in rows
            ],
        )
    except Exception as e:
        logger.error(f"❌ /beelix/offres error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# Concurrence
# ─────────────────────────────────────────
@router.get("/concurrence", response_model=ConcurrenceResponse)
def get_concurrence(limit: int = Query(20, ge=1, le=100)):
    """ESN et cabinets les plus actifs, part de voix ; Beelix toujours incluse avec son rang."""
    try:
        rows = _query(
            f"""
            WITH par_societe AS (
                SELECT
                    entreprise_normalise,
                    ANY_VALUE(entreprise_nom) AS entreprise_nom,
                    COUNT(*) AS nb_offres,
                    LOGICAL_OR(est_beelix) AS est_beelix
                FROM {T_OFFRES}
                WHERE secteur = @concurrence
                  AND COALESCE(entreprise_normalise, '') != ''
                GROUP BY entreprise_normalise
            ),
            classees AS (
                SELECT
                    *,
                    RANK() OVER (ORDER BY nb_offres DESC) AS rang,
                    SUM(nb_offres) OVER () AS total_offres,
                    COUNT(*) OVER () AS nb_concurrents
                FROM par_societe
            )
            SELECT *
            FROM classees
            WHERE rang <= @limit OR est_beelix
            ORDER BY rang, entreprise_nom
            """,
            [
                bigquery.ScalarQueryParameter("concurrence", "STRING", SECTEUR_CONCURRENCE),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
            ],
        )
        if not rows:
            return ConcurrenceResponse(total_offres=0, nb_concurrents=0, items=[])
        total = rows[0].total_offres
        rang_beelix = next((r.rang for r in rows if r.est_beelix), None)
        return ConcurrenceResponse(
            total_offres=total,
            nb_concurrents=rows[0].nb_concurrents,
            rang_beelix=rang_beelix,
            items=[
                ConcurrentItem(
                    rang=r.rang,
                    entreprise_nom=r.entreprise_nom or r.entreprise_normalise,
                    nb_offres=r.nb_offres,
                    part=round(100 * r.nb_offres / total, 1) if total else 0.0,
                    est_beelix=bool(r.est_beelix),
                )
                for r in rows
            ],
        )
    except Exception as e:
        logger.error(f"❌ /beelix/concurrence error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# Besoins (familles de profils)
# ─────────────────────────────────────────
@router.get("/besoins", response_model=BesoinsResponse)
def get_besoins(secteur: Optional[str] = Query(None, description="Secteur cible ou concurrence ; absent = les 6 secteurs Beelix")):
    """Répartition des offres par famille de profils, détectée dans les titres."""
    secteurs = _secteurs(secteur, SECTEURS_CIBLES + [SECTEUR_CONCURRENCE])
    try:
        rows = _query(
            f"""
            SELECT famille, COUNT(*) AS nb_offres
            FROM (
                SELECT {_famille_sql()} AS famille
                FROM {T_OFFRES}
                WHERE secteur IN UNNEST(@secteurs)
            )
            GROUP BY famille
            ORDER BY nb_offres DESC
            """,
            [bigquery.ArrayQueryParameter("secteurs", "STRING", secteurs)],
        )
        total = sum(r.nb_offres for r in rows)
        return BesoinsResponse(
            secteur=secteur,
            total=total,
            items=[
                BesoinItem(
                    famille=r.famille,
                    nb_offres=r.nb_offres,
                    part=round(100 * r.nb_offres / total, 1) if total else 0.0,
                )
                for r in rows
            ],
        )
    except Exception as e:
        logger.error(f"❌ /beelix/besoins error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# Tendance hebdomadaire
# ─────────────────────────────────────────
@router.get("/tendance", response_model=TendanceResponse)
def get_tendance():
    """Offres par semaine (lundi) : secteurs cibles contre concurrence."""
    try:
        rows = _query(
            f"""
            SELECT
                DATE_TRUNC(DATE(date_collecte), WEEK(MONDAY)) AS semaine,
                COUNTIF(secteur IN UNNEST(@cibles)) AS offres_cibles,
                COUNTIF(secteur = @concurrence) AS offres_concurrence
            FROM {T_OFFRES}
            GROUP BY semaine
            ORDER BY semaine
            """,
            [
                bigquery.ArrayQueryParameter("cibles", "STRING", SECTEURS_CIBLES),
                bigquery.ScalarQueryParameter("concurrence", "STRING", SECTEUR_CONCURRENCE),
            ],
        )
        return TendanceResponse(points=[
            TendancePoint(
                semaine=str(r.semaine),
                offres_cibles=r.offres_cibles,
                offres_concurrence=r.offres_concurrence,
            )
            for r in rows
        ])
    except Exception as e:
        logger.error(f"❌ /beelix/tendance error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# News (comme SQLI)
# ─────────────────────────────────────────
@router.get("/news", response_model=NewsResponse)
def get_news(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    """Actualités Beelix depuis BigQuery."""
    try:
        total_count = _query(
            f"""
            SELECT COUNT(*) AS total
            FROM {T_NEWS}
            WHERE COALESCE(JSON_VALUE(metadata, '$.chunk_index'), '0') = '0'
            """
        )[0].total
        rows = _query(
            f"""
            SELECT id, source, date, title, metadata
            FROM {T_NEWS}
            WHERE COALESCE(JSON_VALUE(metadata, '$.chunk_index'), '0') = '0'
            ORDER BY date DESC
            LIMIT @limit OFFSET @offset
            """,
            [
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
                bigquery.ScalarQueryParameter("offset", "INT64", offset),
            ],
        )
        items = []
        for row in rows:
            meta = row.metadata if isinstance(row.metadata, dict) else json.loads(row.metadata or "{}")
            items.append(NewsItem(
                id=row.id,
                title=row.title,
                date=_texte(row.date),
                source=row.source,
                url=meta.get("url"),
            ))
        return NewsResponse(total=total_count, items=items)
    except Exception as e:
        logger.error(f"❌ /beelix/news error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# RAG
# ─────────────────────────────────────────
@router.post("/rag", response_model=RagResponse)
async def rag(body: RagRequest):
    """RAG — ChromaDB beelix_veille (fiches d'offres + actualités) + LLM."""
    await wake("embedding-service")
    await heartbeat("embedding-service")
    try:
        result = await rag_service.rag_pipeline(
            question=body.question,
            n_results=body.n_results or 8,
        )
        return RagResponse(
            answer=result["answer"],
            sources=[RagSource(**s) for s in result["sources"]],
            model_used=result["model_used"],
            tokens_used=result["tokens_used"],
        )
    except Exception as e:
        logger.error(f"❌ /beelix/rag error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

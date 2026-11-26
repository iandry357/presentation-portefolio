"""
Routes FastAPI /wavestone/* — veille entreprise et signaux de recrutement (POC cooptation).
BigQuery wavestone_veille (articles_bruts, offres_wavestone) pour les vues, ChromaDB pour le RAG,
JSON embarqué pour le topic modeling.
"""
import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from google.cloud import bigquery
from google.oauth2 import service_account

from app.core.access_control import get_access_state, require_access
from app.core.config import settings
from routers.wavestone.schemas import (
    SectionCount, WavestoneStats,
    NewsItem, NewsResponse,
    RagRequest, RagResponse, RagSource,
    TopicModelingResponse, Topic, TopicDoc,
    CasClientsResponse,
    PosteItem, FamilleItem, RecrutementResponse,
)
from routers.wavestone import rag as rag_service

from app.services.orchestrator_client import wake, heartbeat

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/wavestone", tags=["Wavestone"])

BQ_PROJECT_ID = "gen-lang-client-0989575872"
BQ_DATASET    = "wavestone_veille"
T_NEWS        = f"`{BQ_PROJECT_ID}.{BQ_DATASET}.articles_bruts`"
T_OFFRES      = f"`{BQ_PROJECT_ID}.{BQ_DATASET}.offres_wavestone`"

DATA_DIR = Path(__file__).parent / "data"
TOPIC_MODELING_PATH = Path(os.getenv("WAVESTONE_TOPIC_MODELING_PATH", str(DATA_DIR / "topic_modeling.json")))
CAS_CLIENTS_PATH = DATA_DIR / "cas_clients.json"

SECTIONS = ["news", "insight", "clients_story", "presse"]   # presse = google_news (pas de section en métadonnée)
LANGUES = ["fr", "en"]
FILTRE_PREMIER_MORCEAU = "COALESCE(JSON_VALUE(metadata, '$.chunk_index'), '0') = '0'"
SECTION_SQL = "COALESCE(JSON_VALUE(metadata, '$.section'), 'presse')"

# Familles de postes détectées dans les titres (RE2, titre en minuscules) ; le premier motif l'emporte.
# Établies sur les intitulés Wavestone du mart Top Offres (exploration du 2026-11-20).
FAMILLES = [
    ("CTO / CIO Advisory", r"\bcto\b|\bcio\b"),
    ("Data Science", r"data scien"),
    ("Cybersécurité", r"cyber|secur|sécur"),
    ("Data & IA sectoriel", r"data.{0,4}(ia|ai|analytics)"),
    ("Stratégie IA", r"ai strategy|strat[ée]gie"),
    ("Agilité / Operating model", r"agilit|operating model"),
    ("UX / Design", r"\bux\b|\bui\b|design"),
]
FAMILLE_AUTRE = "Autre"


def _famille_sql() -> str:
    """Expression CASE qui range un titre dans une famille de postes."""
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


def _texte(valeur) -> Optional[str]:
    return str(valeur) if valeur is not None else None


def _verifier(valeur: Optional[str], autorises: list, nom: str) -> None:
    if valeur is not None and valeur not in autorises:
        raise HTTPException(status_code=400, detail=f"{nom} inconnu(e) : {valeur}")


# ─────────────────────────────────────────
# Stats
# ─────────────────────────────────────────
@router.get("/stats", response_model=WavestoneStats)
def get_stats():
    """Documents par section et langue, offres et période."""
    try:
        sections = _query(
            f"""
            SELECT
                {SECTION_SQL} AS section,
                JSON_VALUE(metadata, '$.langue') AS langue,
                COUNT(*) AS nb_documents,
                MAX(ingested_at) AS last_updated
            FROM {T_NEWS}
            WHERE {FILTRE_PREMIER_MORCEAU}
            GROUP BY section, langue
            ORDER BY section, langue
            """
        )
        offres = _query(
            f"""
            SELECT
                COUNT(*) AS total_offres,
                COUNT(DISTINCT COALESCE(titre_normalise, id_unique)) AS intitules_distincts,
                MIN(DATE(date_collecte)) AS periode_debut,
                MAX(DATE(date_collecte)) AS periode_fin,
                MAX(charge_le) AS charge_le
            FROM {T_OFFRES}
            """
        )[0]
        last_updated = max((r.last_updated for r in sections if r.last_updated), default=None)
        return WavestoneStats(
            total_documents=sum(r.nb_documents for r in sections),
            sections=[SectionCount(section=r.section, langue=r.langue, nb_documents=r.nb_documents) for r in sections],
            last_updated=_texte(last_updated),
            total_offres=offres.total_offres,
            intitules_distincts=offres.intitules_distincts,
            periode_debut=_texte(offres.periode_debut),
            periode_fin=_texte(offres.periode_fin),
            charge_le=_texte(offres.charge_le),
        )
    except Exception as e:
        logger.error(f"❌ /wavestone/stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# News (site + presse)
# ─────────────────────────────────────────
@router.get("/news", response_model=NewsResponse)
def get_news(
    langue: Optional[str] = Query(None, description="fr ou en ; absent = toutes"),
    section: Optional[str] = Query(None, description="news, insight, clients_story ou presse ; absent = toutes"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Publications, cas clients, communiqués et presse, les plus récents d'abord."""
    _verifier(langue, LANGUES, "Langue")
    _verifier(section, SECTIONS, "Section")
    try:
        rows = _query(
            f"""
            SELECT id, source, date, title, metadata, {SECTION_SQL} AS section,
                   COUNT(*) OVER () AS total
            FROM {T_NEWS}
            WHERE {FILTRE_PREMIER_MORCEAU}
              AND (@langue IS NULL OR JSON_VALUE(metadata, '$.langue') = @langue)
              AND (@section IS NULL OR {SECTION_SQL} = @section)
            ORDER BY date DESC
            LIMIT @limit OFFSET @offset
            """,
            [
                bigquery.ScalarQueryParameter("langue", "STRING", langue),
                bigquery.ScalarQueryParameter("section", "STRING", section),
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
                section=row.section,
                langue=meta.get("langue"),
                source_name=meta.get("source_name"),
                date_type=meta.get("date_type"),
            ))
        return NewsResponse(total=rows[0].total if rows else 0, items=items)
    except Exception as e:
        logger.error(f"❌ /wavestone/news error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# RAG
# ─────────────────────────────────────────
@router.post("/rag", response_model=RagResponse, dependencies=[Depends(require_access)])
async def rag(body: RagRequest):
    """RAG — ChromaDB wavestone_veille (site, presse, fiches d'offres) + LLM. Privé : code d'accès requis."""
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
        logger.error(f"❌ /wavestone/rag error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# ML — Topic Modeling
# ─────────────────────────────────────────
@router.get("/ml/topic-modeling", response_model=TopicModelingResponse)
async def get_topic_modeling():
    """Topic modeling LDA par langue — résultat calculé en local (JSON embarqué dans l'image)."""
    if not TOPIC_MODELING_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Topic modeling non encore calculé — lancez le script manuellement",
        )
    try:
        with open(TOPIC_MODELING_PATH, "r", encoding="utf-8") as f:
            result = json.load(f)
        return TopicModelingResponse(
            n_topics=result["n_topics"],
            total_docs=result["total_docs"],
            topics=[Topic(**t) for t in result["topics"]],
            docs=[TopicDoc(**d) for d in result["docs"]],
        )
    except Exception as e:
        logger.error(f"❌ /wavestone/ml/topic-modeling error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# Cas clients
# ─────────────────────────────────────────
@router.get("/cas-clients", response_model=CasClientsResponse)
async def get_cas_clients():
    """Cas clients par secteur et type de mission — catégories tirées des données par un LLM, calculées en local."""
    if not CAS_CLIENTS_PATH.exists():
        raise HTTPException(status_code=404, detail="Cas clients non encore classés — lancez ml/cas_clients.py")
    try:
        with open(CAS_CLIENTS_PATH, "r", encoding="utf-8") as f:
            return CasClientsResponse(**json.load(f))
    except Exception as e:
        logger.error(f"❌ /wavestone/cas-clients error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# Recrutement
# ─────────────────────────────────────────
@router.get("/recrutement", response_model=RecrutementResponse)
def get_recrutement(unlocked: bool = Depends(get_access_state)):
    """Postes Wavestone regroupés par intitulé (republications fusionnées) et familles.
    L'adéquation au profil (score, catégorie, métier cible) n'est renvoyée qu'avec l'accès privé ;
    sans accès, les postes sont triés par date pour que l'ordre ne trahisse pas le classement."""
    try:
        rows = _query(
            f"""
            WITH base AS (
                SELECT *, {_famille_sql()} AS famille
                FROM {T_OFFRES}
            )
            SELECT
                COALESCE(titre_normalise, id_unique) AS cle,
                ARRAY_AGG(STRUCT(titre, url_offre, localisation_libelle, type_contrat_libelle, source)
                          ORDER BY date_collecte DESC LIMIT 1)[OFFSET(0)] AS dernier,
                ANY_VALUE(famille) AS famille,
                COUNT(*) AS nb_publications,
                MIN(COALESCE(date_publication, DATE(date_collecte))) AS premiere_date,
                MAX(COALESCE(date_publication, DATE(date_collecte))) AS derniere_date,
                MAX(score) AS score_max,
                ARRAY_AGG(categorie IGNORE NULLS ORDER BY score DESC LIMIT 1)[SAFE_OFFSET(0)] AS categorie,
                ARRAY_AGG(cible_intitule IGNORE NULLS ORDER BY score DESC LIMIT 1)[SAFE_OFFSET(0)] AS cible_intitule,
                LOGICAL_OR(COALESCE(a_texte_complet, FALSE)) AS a_texte_complet,
                MIN(DATE(date_collecte)) AS collecte_min,
                MAX(DATE(date_collecte)) AS collecte_max
            FROM base
            GROUP BY cle
            ORDER BY score_max DESC, derniere_date DESC
            """
        )
        postes = [
            PosteItem(
                titre=r.dernier["titre"] or r.cle,
                famille=r.famille,
                nb_publications=r.nb_publications,
                premiere_date=_texte(r.premiere_date),
                derniere_date=_texte(r.derniere_date),
                lieu=r.dernier["localisation_libelle"],
                contrat=r.dernier["type_contrat_libelle"],
                source=r.dernier["source"],
                url=r.dernier["url_offre"],
                score_max=r.score_max if unlocked else None,
                categorie=r.categorie if unlocked else None,
                cible_intitule=r.cible_intitule if unlocked else None,
                a_texte_complet=bool(r.a_texte_complet),
            )
            for r in rows
        ]
        if not unlocked:
            postes.sort(key=lambda p: p.derniere_date or "", reverse=True)

        familles: dict = {}
        for p in postes:
            f = familles.setdefault(p.famille, {"nb_intitules": 0, "nb_publications": 0})
            f["nb_intitules"] += 1
            f["nb_publications"] += p.nb_publications

        return RecrutementResponse(
            total_offres=sum(p.nb_publications for p in postes),
            intitules_distincts=len(postes),
            periode_debut=_texte(min((r.collecte_min for r in rows), default=None)),
            periode_fin=_texte(max((r.collecte_max for r in rows), default=None)),
            familles=[
                FamilleItem(famille=nom, **v)
                for nom, v in sorted(familles.items(), key=lambda x: x[1]["nb_publications"], reverse=True)
            ],
            postes=postes,
        )
    except Exception as e:
        logger.error(f"❌ /wavestone/recrutement error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

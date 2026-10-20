"""
Lecture BigQuery du MVP Immobilier (dataset immobilier).
Credentials lus depuis GCP_SERVICE_ACCOUNT_JSON_IMMOBILIER (compte pipeline-immobilier).
Utilisé par le routeur backend/routers/immobilier.
Pages publiques : tables agrégées (agg_dpe_parc, agg_dvf_prix), mises en cache.
Liste des changements : dpe_logements (accès privé, sans cache).
"""

import json
import logging
import threading
import time
from datetime import date, datetime
from typing import Optional

from google.cloud import bigquery
from google.oauth2 import service_account

from app.core.config import settings

logger = logging.getLogger(__name__)

# Paramètres
CACHE_TTL_SECONDES = 0     # 0 désactive le cache
TABLE_AGG_DPE = "agg_dpe_parc"
TABLE_AGG_DVF = "agg_dvf_prix"
TABLE_DPE = "dpe_logements"

# Colonnes de dpe_logements renvoyées pour la liste des changements
COLONNES_CHANGEMENT = [
    "numero_dpe", "date_etablissement_dpe", "adresse_ban", "arrondissement", "etiquette_dpe",
    "type_energie_principale_chauffage", "flag_chauffage_electrique", "flag_post_reforme_2026",
]

_cache: dict[str, tuple[float, list[dict]]] = {}
_verrou = threading.Lock()


def _get_bq_client() -> bigquery.Client:
    """Construit le client BigQuery depuis les credentials JSON du compte Immobilier."""
    if not settings.GCP_SERVICE_ACCOUNT_JSON_IMMOBILIER:
        raise RuntimeError("GCP_SERVICE_ACCOUNT_JSON_IMMOBILIER non configuré")

    sa_info = json.loads(settings.GCP_SERVICE_ACCOUNT_JSON_IMMOBILIER)
    credentials = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/bigquery"],
    )
    return bigquery.Client(
        project=settings.BQ_PROJECT_ID,
        credentials=credentials,
    )


def _table(nom: str) -> str:
    return f"`{settings.BQ_PROJECT_ID}.{settings.BQ_DATASET_IMMOBILIER}.{nom}`"


def _serialiser(lignes) -> list[dict]:
    """Lignes BigQuery -> dicts ; dates et horodatages en chaînes ISO (sérialisation JSON)."""
    resultat = []
    for ligne in lignes:
        donnees = dict(ligne)
        for cle, valeur in list(donnees.items()):
            if isinstance(valeur, (date, datetime)):
                donnees[cle] = valeur.isoformat()
        resultat.append(donnees)
    return resultat


def _avec_cache(cle: str, charger) -> list[dict]:
    """Retourne la copie en mémoire si elle a moins de CACHE_TTL_SECONDES, sinon relit BigQuery."""
    if CACHE_TTL_SECONDES > 0:
        with _verrou:
            entree = _cache.get(cle)
            if entree and time.monotonic() - entree[0] < CACHE_TTL_SECONDES:
                return entree[1]
    donnees = charger()
    if CACHE_TTL_SECONDES > 0:
        with _verrou:
            _cache[cle] = (time.monotonic(), donnees)
    return donnees


def fetch_agg_dpe() -> list[dict]:
    """Table agg_dpe_parc entière (arrondissement x étiquette x chauffage électrique), en cache."""
    def charger():
        client = _get_bq_client()
        query = f"""
            SELECT arrondissement, etiquette_dpe, flag_chauffage_electrique,
                   nb_dpe, nb_remplacants, date_maj
            FROM {_table(TABLE_AGG_DPE)}
        """
        lignes = _serialiser(client.query(query).result())
        logger.info(f"[immobilier_bigquery] {len(lignes)} lignes {TABLE_AGG_DPE} lues")
        return lignes

    return _avec_cache(TABLE_AGG_DPE, charger)


def fetch_agg_dvf() -> list[dict]:
    """Table agg_dvf_prix entière (arrondissement x année x type de logement), en cache."""
    def charger():
        client = _get_bq_client()
        query = f"""
            SELECT arrondissement, annee, type_local, nb_ventes, prix_m2_median, date_maj
            FROM {_table(TABLE_AGG_DVF)}
        """
        lignes = _serialiser(client.query(query).result())
        logger.info(f"[immobilier_bigquery] {len(lignes)} lignes {TABLE_AGG_DVF} lues")
        return lignes

    return _avec_cache(TABLE_AGG_DVF, charger)


def fetch_changements(
    arrondissement: Optional[int],
    etiquette: Optional[str],
    chauffage: Optional[str],
    post_reforme: Optional[bool],
    date_min: Optional[date],
    date_max: Optional[date],
    page: int,
    taille: int,
) -> dict:
    """
    Une page des DPE refaits (numero_dpe_remplace renseigné), triés par date décroissante.
    Retourne {"total", "nb_recalcul_probable", "lignes"} ; total et nb_recalcul_probable portent
    sur l'ensemble filtré. Si la page demandée dépasse les résultats, lignes est vide (total = 0).
    """
    client = _get_bq_client()
    conditions = ["numero_dpe_remplace IS NOT NULL"]
    params = [
        bigquery.ScalarQueryParameter("limite", "INT64", taille),
        bigquery.ScalarQueryParameter("decalage", "INT64", (page - 1) * taille),
    ]

    if arrondissement is not None:
        conditions.append("arrondissement = @arrondissement")
        params.append(bigquery.ScalarQueryParameter("arrondissement", "INT64", arrondissement))
    if etiquette:
        conditions.append("etiquette_dpe = @etiquette")
        params.append(bigquery.ScalarQueryParameter("etiquette", "STRING", etiquette))
    if chauffage == "electrique":
        conditions.append("flag_chauffage_electrique")
    elif chauffage == "autre":
        conditions.append("NOT COALESCE(flag_chauffage_electrique, FALSE)")
    if post_reforme is not None:
        conditions.append("flag_post_reforme_2026 = @post_reforme")
        params.append(bigquery.ScalarQueryParameter("post_reforme", "BOOL", post_reforme))
    if date_min:
        conditions.append("date_etablissement_dpe >= @date_min")
        params.append(bigquery.ScalarQueryParameter("date_min", "DATE", date_min))
    if date_max:
        conditions.append("date_etablissement_dpe <= @date_max")
        params.append(bigquery.ScalarQueryParameter("date_max", "DATE", date_max))

    query = f"""
        SELECT {", ".join(COLONNES_CHANGEMENT)},
               COUNT(*) OVER() AS total,
               COUNTIF(flag_chauffage_electrique AND flag_post_reforme_2026) OVER() AS nb_recalcul_probable
        FROM {_table(TABLE_DPE)}
        WHERE {" AND ".join(conditions)}
        ORDER BY date_etablissement_dpe DESC, numero_dpe
        LIMIT @limite OFFSET @decalage
    """
    lignes = _serialiser(client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params)).result())

    total = lignes[0]["total"] if lignes else 0
    nb_recalcul = lignes[0]["nb_recalcul_probable"] if lignes else 0
    for ligne in lignes:
        ligne.pop("total")
        ligne.pop("nb_recalcul_probable")
    return {"total": total, "nb_recalcul_probable": nb_recalcul, "lignes": lignes}

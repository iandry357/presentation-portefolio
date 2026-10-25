"""Chargement du corpus : ChromaDB (OVH) puis table de traçabilité BigQuery. Lit chunks.json (après validation).

ChromaDB : les embeddings viennent de l'embedding-service partagé (réveillé via l'orchestrateur OVH). La collection est remplie
sous un nom de travail puis renommée, l'ancienne collection étant supprimée juste avant : en cas d'échec, elle reste intacte.
BigQuery : la table de traçabilité est remplacée en un seul job. Tout échec d'un lot arrête le chargement.
"""
import json
import logging
import time
from datetime import datetime, timezone

import chromadb
import requests
from chromadb.config import Settings
from google.cloud import bigquery

from pipeline.referentiel.config import (
    BQ_DATASET, CHROMA_HOST, CHROMA_PASSWORD, CHROMA_PORT, CHROMA_USER, COLLECTION_CHROMA, COLLECTION_CHROMA_TRAVAIL,
    DOSSIER_CORPUS, EMBEDDING_SERVICE_KEY, EMBEDDING_SERVICE_URL, FICHIER_CHUNKS, GCP_PROJECT_ID, GCP_SA_KEY_PATH,
    OVH_ORCHESTRATOR_URL, TABLE_CORPUS, TAILLE_LOT_EMBEDDING, WAKE_POLL_INTERVAL_SEC, WAKE_TIMEOUT_SEC,
)

logger = logging.getLogger(__name__)

SCHEMA_CORPUS = [
    bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("source", "STRING"), bigquery.SchemaField("type_texte", "STRING"),
    bigquery.SchemaField("reference", "STRING"), bigquery.SchemaField("theme", "STRING"),
    bigquery.SchemaField("statut", "STRING"), bigquery.SchemaField("date_version", "DATE"),
    bigquery.SchemaField("date_effet", "DATE"), bigquery.SchemaField("valable_jusqu_au", "DATE"),
    bigquery.SchemaField("url", "STRING"), bigquery.SchemaField("identifiant", "STRING"),
    bigquery.SchemaField("texte", "STRING"), bigquery.SchemaField("articles_cgi", "STRING"),
    bigquery.SchemaField("partie", "INT64"), bigquery.SchemaField("parties", "INT64"), bigquery.SchemaField("mots", "INT64"),
    bigquery.SchemaField("collecte_le", "DATE"), bigquery.SchemaField("document", "STRING"),
    bigquery.SchemaField("charge_le", "TIMESTAMP"),
]


def _verifier_configuration():
    variables = {
        "CHROMA_HOST": CHROMA_HOST, "CHROMA_USER": CHROMA_USER, "CHROMA_PASSWORD": CHROMA_PASSWORD,
        "OVH_ORCHESTRATOR_URL": OVH_ORCHESTRATOR_URL, "EMBEDDING_SERVICE_URL": EMBEDDING_SERVICE_URL,
    }
    manquantes = [nom for nom, valeur in variables.items() if not valeur]
    if manquantes:
        raise ValueError("Variables à définir dans pipeline/.env : " + ", ".join(manquantes))


def _reveiller_embedding():
    """Démarre l'embedding-service via l'orchestrateur OVH puis attend son /health."""
    try:
        requests.post(f"{OVH_ORCHESTRATOR_URL}/wake/{EMBEDDING_SERVICE_KEY}", timeout=10)
    except requests.exceptions.RequestException as e:
        logger.warning("Réveil de %s non confirmé : %s", EMBEDDING_SERVICE_KEY, e)
    attente = 0
    while attente < WAKE_TIMEOUT_SEC:
        try:
            if requests.get(f"{EMBEDDING_SERVICE_URL}/health", timeout=5).status_code == 200:
                logger.info("%s prêt", EMBEDDING_SERVICE_KEY)
                return
        except requests.exceptions.RequestException:
            pass
        time.sleep(WAKE_POLL_INTERVAL_SEC)
        attente += WAKE_POLL_INTERVAL_SEC
    raise TimeoutError(f"{EMBEDDING_SERVICE_KEY} indisponible après {WAKE_TIMEOUT_SEC} s")


def _embeddings(textes):
    r = requests.post(f"{EMBEDDING_SERVICE_URL}/embed", json={"texts": textes}, timeout=120)
    r.raise_for_status()
    resultat = r.json()["embeddings"]
    if len(resultat) != len(textes):
        raise ValueError(f"{len(resultat)} embeddings reçus pour {len(textes)} textes")
    return resultat


def _client_chroma():
    return chromadb.HttpClient(
        host=CHROMA_HOST, port=CHROMA_PORT,
        settings=Settings(
            chroma_client_auth_provider="chromadb.auth.basic_authn.BasicAuthClientProvider",
            chroma_client_auth_credentials=f"{CHROMA_USER}:{CHROMA_PASSWORD}",
            anonymized_telemetry=False,
        ),
    )


def _supprimer_collection(client, nom):
    try:
        client.delete_collection(nom)
    except Exception as e:  # collection absente (premier chargement) : pas une erreur
        logger.debug("Suppression de %s ignorée : %s", nom, e)


def charger_chroma(chunks):
    """Remplace la collection referentiel_immobilier par les chunks ; renvoie le nombre de chunks chargés."""
    _reveiller_embedding()
    client = _client_chroma()
    _supprimer_collection(client, COLLECTION_CHROMA_TRAVAIL)
    travail = client.create_collection(name=COLLECTION_CHROMA_TRAVAIL, metadata={"hnsw:space": "cosine"})
    for i in range(0, len(chunks), TAILLE_LOT_EMBEDDING):
        lot = chunks[i:i + TAILLE_LOT_EMBEDDING]
        textes = [c["document"] for c in lot]
        travail.add(ids=[c["id"] for c in lot], embeddings=_embeddings(textes), documents=textes, metadatas=[c["metadata"] for c in lot])
        logger.info("ChromaDB : lot %d, %d/%d chunks", i // TAILLE_LOT_EMBEDDING + 1, i + len(lot), len(chunks))
    if travail.count() != len(chunks):
        raise ValueError(f"{COLLECTION_CHROMA_TRAVAIL} : {travail.count()} chunks au lieu de {len(chunks)}")
    _supprimer_collection(client, COLLECTION_CHROMA)
    travail.modify(name=COLLECTION_CHROMA)
    logger.info("Collection %s : %d chunks", COLLECTION_CHROMA, travail.count())
    return len(chunks)


def charger_bigquery(chunks):
    """Remplace la table de traçabilité en un seul job ; renvoie le nombre de lignes chargées."""
    charge_le = datetime.now(timezone.utc).isoformat()
    lignes = []
    for c in chunks:
        m = c["metadata"]
        lignes.append({
            "id": c["id"], "source": m["source"], "type_texte": m["type_texte"], "reference": m["reference"], "theme": m["theme"],
            "statut": m["statut"], "date_version": m["date_version"] or None, "date_effet": m["date_effet"] or None,
            "valable_jusqu_au": m["valable_jusqu_au"] or None, "url": m["url"], "identifiant": m["identifiant"], "texte": m["texte"],
            "articles_cgi": m["articles_cgi"], "partie": m["partie"], "parties": m["parties"], "mots": m["mots"],
            "collecte_le": m["collecte_le"] or None, "document": c["document"], "charge_le": charge_le,
        })
    client = bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)
    config = bigquery.LoadJobConfig(schema=SCHEMA_CORPUS, write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
    job = client.load_table_from_json(lignes, f"{GCP_PROJECT_ID}.{BQ_DATASET}.{TABLE_CORPUS}", job_config=config)
    job.result()
    if job.output_rows != len(chunks):
        raise ValueError(f"{TABLE_CORPUS} : {job.output_rows} lignes chargées pour {len(chunks)} attendues")
    logger.info("Table %s : %d lignes", TABLE_CORPUS, job.output_rows)
    return job.output_rows


def charger(chemin=None, etape="tout"):
    """Charge chunks.json dans ChromaDB et/ou BigQuery (etape : chroma, bigquery ou tout)."""
    chemin = chemin or DOSSIER_CORPUS / FICHIER_CHUNKS
    chunks = json.loads(chemin.read_text(encoding="utf-8"))["chunks"]
    resultat = {}
    if etape in ("chroma", "tout"):
        _verifier_configuration()
        resultat["chroma"] = charger_chroma(chunks)
    if etape in ("bigquery", "tout"):
        resultat["bigquery"] = charger_bigquery(chunks)
    return resultat

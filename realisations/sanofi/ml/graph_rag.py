"""
graph_rag.py
------------
Graph RAG — requêtes Cypher sur Neo4j + construction contexte structuré.
LLM non branché — retourne le contexte brut jusqu'à disponibilité du GGUF Mistral 7B.

Routes exposées dans main.py :
    POST /ml/graph-rag
        body : { cluster_id: int, question: str }
        retour : { cluster_label, targets_count, context, answer }
"""

import os
import time

import httpx
from neo4j import GraphDatabase
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# PARAMÈTRES CONFIGURABLES
# ---------------------------------------------------------------------------
load_dotenv()

NEO4J_URI      = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER     = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

ORCHESTRATOR_URL     = os.getenv("OVH_ORCHESTRATOR_URL", "http://localhost:8080")
# NEO4J_HEALTH_URL     = "http://localhost:7474"
NEO4J_HEALTH_URL     = os.getenv("NEO4J_HEALTH_URL", "http://neo4j:7474")
NEO4J_WAKE_TIMEOUT   = 60    # secondes max pour attendre Neo4j up
NEO4J_POLL_INTERVAL  = 2     # secondes entre chaque poll

LLM_AVAILABLE = False        # Passer à True quand GGUF Mistral branché

# ---------------------------------------------------------------------------
# WAKE NEO4J
# ---------------------------------------------------------------------------

def _wake_neo4j() -> bool:
    """
    Réveille Neo4j via l'orchestrateur puis poll /health jusqu'à 200 OK.
    Retourne True si Neo4j est prêt, False si timeout.
    """
    # 1 — Signal wake à l'orchestrateur
    try:
        httpx.post(f"{ORCHESTRATOR_URL}/wake/neo4j", timeout=10)
    except Exception as e:
        print(f"[GRAPH RAG] Wake orchestrateur échoué : {e}")

    # 2 — Poll Neo4j HTTP jusqu'à disponibilité
    deadline = time.time() + NEO4J_WAKE_TIMEOUT
    while time.time() < deadline:
        try:
            resp = httpx.get(NEO4J_HEALTH_URL, timeout=5)
            if resp.status_code == 200:
                print("[GRAPH RAG] Neo4j ready.")
                return True
        except Exception:
            pass
        time.sleep(NEO4J_POLL_INTERVAL)

    print("[GRAPH RAG] Neo4j wake timeout.")
    return False


# ---------------------------------------------------------------------------
# DRIVER NEO4J
# ---------------------------------------------------------------------------

def _get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# ---------------------------------------------------------------------------
# REQUÊTES CYPHER
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# STRATÉGIE DE SÉLECTION DU CONTEXTE
# ---------------------------------------------------------------------------
# Pour éviter de saturer le LLM avec des milliers de targets par cluster,
# on sélectionne intelligemment selon 3 signaux complémentaires :
#
#   Signal 1 — top 5 par score OpenTargets
#       → cibles les mieux documentées scientifiquement
#
#   Signal 2 — top 5 par fréquence transversale
#       → cibles présentes dans plusieurs diseases du cluster
#       → signal de centralité biologique
#
#   Signal 3 — top 5 has_approved_drug
#       → cibles avec médicament approuvé sur le marché
#       → validation commerciale réelle
#
# Les 3 ensembles sont dédupliqués → max ~10-12 targets uniques.
# Suffisant pour un prompt LLM de ~300-500 tokens.
# ---------------------------------------------------------------------------

CYPHER_TOP_BY_SCORE = """
MATCH (c:Cluster {cluster_id: $cluster_id})-[:CLUSTER_HAS_TARGET]->(t:Target)
OPTIONAL MATCH (t)<-[:DRUG_TARGETS]-(dr:Drug)
OPTIONAL MATCH (t)-[:TARGET_IN_PATHWAY]->(p:Pathway)
OPTIONAL MATCH (t)-[:TARGET_TREATS]->(d:Disease)
WITH c, t,
     collect(DISTINCT dr.name) AS drugs,
     collect(DISTINCT p.name)  AS pathways,
     collect(DISTINCT d.name)  AS diseases
ORDER BY t.score DESC
LIMIT 5
RETURN
    c.label AS cluster_label, c.profile AS profile,
    c.bio_score_avg AS bio_score_avg, c.approved_drug_rate AS approved_drug_rate,
    c.count AS trial_count,
    t.symbol AS target_symbol, t.approved_name AS target_name,
    t.score AS target_score, t.frequency AS target_frequency,
    t.has_approved_drug AS has_approved_drug,
    t.max_clinical_stage AS max_clinical_stage,
    t.target_class AS target_class, t.tractability AS tractability,
    drugs, pathways, diseases
"""

CYPHER_TOP_BY_FREQUENCY = """
MATCH (c:Cluster {cluster_id: $cluster_id})-[:CLUSTER_HAS_TARGET]->(t:Target)
OPTIONAL MATCH (t)<-[:DRUG_TARGETS]-(dr:Drug)
OPTIONAL MATCH (t)-[:TARGET_IN_PATHWAY]->(p:Pathway)
OPTIONAL MATCH (t)-[:TARGET_TREATS]->(d:Disease)
WITH c, t,
     collect(DISTINCT dr.name) AS drugs,
     collect(DISTINCT p.name)  AS pathways,
     collect(DISTINCT d.name)  AS diseases
ORDER BY t.frequency DESC
LIMIT 5
RETURN
    c.label AS cluster_label, c.profile AS profile,
    c.bio_score_avg AS bio_score_avg, c.approved_drug_rate AS approved_drug_rate,
    c.count AS trial_count,
    t.symbol AS target_symbol, t.approved_name AS target_name,
    t.score AS target_score, t.frequency AS target_frequency,
    t.has_approved_drug AS has_approved_drug,
    t.max_clinical_stage AS max_clinical_stage,
    t.target_class AS target_class, t.tractability AS tractability,
    drugs, pathways, diseases
"""

CYPHER_TOP_APPROVED = """
MATCH (c:Cluster {cluster_id: $cluster_id})-[:CLUSTER_HAS_TARGET]->(t:Target)
WHERE t.has_approved_drug = true
OPTIONAL MATCH (t)<-[:DRUG_TARGETS]-(dr:Drug)
OPTIONAL MATCH (t)-[:TARGET_IN_PATHWAY]->(p:Pathway)
OPTIONAL MATCH (t)-[:TARGET_TREATS]->(d:Disease)
WITH c, t,
     collect(DISTINCT dr.name) AS drugs,
     collect(DISTINCT p.name)  AS pathways,
     collect(DISTINCT d.name)  AS diseases
ORDER BY t.score DESC
LIMIT 5
RETURN
    c.label AS cluster_label, c.profile AS profile,
    c.bio_score_avg AS bio_score_avg, c.approved_drug_rate AS approved_drug_rate,
    c.count AS trial_count,
    t.symbol AS target_symbol, t.approved_name AS target_name,
    t.score AS target_score, t.frequency AS target_frequency,
    t.has_approved_drug AS has_approved_drug,
    t.max_clinical_stage AS max_clinical_stage,
    t.target_class AS target_class, t.tractability AS tractability,
    drugs, pathways, diseases
"""


def _parse_rows(result) -> tuple[dict, list]:
    """Parse les rows Neo4j en meta + liste targets."""
    cluster_meta = {}
    rows = []
    for record in result:
        if not cluster_meta:
            cluster_meta = {
                "label":              record["cluster_label"],
                "profile":            record["profile"],
                "bio_score_avg":      record["bio_score_avg"],
                "approved_drug_rate": record["approved_drug_rate"],
                "trial_count":        record["trial_count"],
            }
        if record["target_symbol"]:
            rows.append({
                "symbol":             record["target_symbol"],
                "approved_name":      record["target_name"],
                "score":              record["target_score"],
                "frequency":          record["target_frequency"],
                "has_approved_drug":  record["has_approved_drug"],
                "max_clinical_stage": record["max_clinical_stage"],
                "target_class":       record["target_class"] or [],
                "tractability":       record["tractability"] or [],
                "drugs":              [d for d in record["drugs"] if d],
                "pathways":           [p for p in record["pathways"] if p],
                "diseases":           [d for d in record["diseases"] if d],
            })
    return cluster_meta, rows


def _fetch_cluster_context(cluster_id: int) -> dict:
    """
    3 requêtes Cypher ciblées — top 5 score + top 5 fréquence + top 5 approuvés.
    Déduplique par symbol → max ~10-12 targets uniques.
    """
    driver = _get_driver()
    cluster_meta = {}
    seen_symbols = set()
    targets = []

    with driver.session() as session:
        for cypher in [CYPHER_TOP_BY_SCORE, CYPHER_TOP_BY_FREQUENCY, CYPHER_TOP_APPROVED]:
            result = session.run(cypher, cluster_id=cluster_id)
            meta, rows = _parse_rows(result)
            if meta and not cluster_meta:
                cluster_meta = meta
            for row in rows:
                if row["symbol"] not in seen_symbols:
                    seen_symbols.add(row["symbol"])
                    targets.append(row)

    driver.close()
    return {"meta": cluster_meta, "targets": targets}


# ---------------------------------------------------------------------------
# CONSTRUCTION DU CONTEXTE TEXTE
# ---------------------------------------------------------------------------

def _build_context(cluster_data: dict) -> str:
    """
    Transforme les données Neo4j en contexte texte structuré
    prêt à être injecté dans le prompt LLM.
    """
    meta    = cluster_data.get("meta", {})
    targets = cluster_data.get("targets", [])

    lines = []

    # En-tête cluster
    lines.append(f"CLUSTER : {meta.get('label', 'N/A')}")
    lines.append(f"Profil  : {meta.get('profile', 'N/A')}")
    lines.append(f"Bio score moyen       : {meta.get('bio_score_avg', 0):.3f}")
    lines.append(f"Taux médicaments approuvés : {meta.get('approved_drug_rate', 0):.3f}")
    lines.append(f"Nombre d'essais cliniques  : {meta.get('trial_count', 0)}")
    lines.append("")

    # # Targets — top 20 par score pour ne pas saturer le contexte
    # lines.append(f"CIBLES BIOLOGIQUES ({len(targets)} total — top 20 affichées) :")

    # Targets — sélection intelligente : top 5 score + top 5 fréquence + top 5 approuvés
    lines.append(f"CIBLES BIOLOGIQUES SÉLECTIONNÉES ({len(targets)} — score · fréquence · approuvées) :")
    for t in targets:
        lines.append(f"\n  [{t['symbol']}] {t['approved_name']}")
        lines.append(f"    Score OpenTargets : {t['score']:.4f} | Fréquence transversale : {t['frequency']}")
        lines.append(f"    Stade clinique max : {t['max_clinical_stage']} | Médicament approuvé : {t['has_approved_drug']}")

        if t["target_class"]:
            lines.append(f"    Classe protéique : {', '.join(t['target_class'][:3])}")

        if t["drugs"]:
            lines.append(f"    Médicaments : {', '.join(t['drugs'][:5])}")

        if t["pathways"]:
            lines.append(f"    Voies biologiques : {', '.join(t['pathways'][:3])}")

        if t["diseases"]:
            lines.append(f"    Maladies associées : {', '.join(t['diseases'][:3])}")

        if t["tractability"]:
            lines.append(f"    Druggabilité : {', '.join(t['tractability'][:2])}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ENTRYPOINT PRINCIPAL
# ---------------------------------------------------------------------------

def query_graph_rag(cluster_id: int, question: str) -> dict:
    """
    Point d'entrée appelé depuis main.py.
    Réveille Neo4j, requête Cypher, construit le contexte.
    LLM non branché — retourne contexte brut.
    """
    # Wake Neo4j
    neo4j_ready = _wake_neo4j()
    if not neo4j_ready:
        return {
            "cluster_label":  None,
            "targets_count":  0,
            "context":        "",
            "answer":         "Neo4j unavailable — please retry in a few seconds.",
            "llm_available":  False,
        }

    # Fetch contexte depuis Neo4j
    cluster_data = _fetch_cluster_context(cluster_id)
    meta    = cluster_data.get("meta", {})
    targets = cluster_data.get("targets", [])

    if not meta:
        return {
            "cluster_label": None,
            "targets_count": 0,
            "context":       "",
            "answer":        f"Cluster {cluster_id} not found in graph.",
            "llm_available": False,
        }

    # Construction contexte texte
    context = _build_context(cluster_data)

    # LLM — non branché
    answer = "LLM not available yet — context retrieved successfully."

    return {
        "cluster_label": meta.get("label"),
        "targets_count": len(targets),
        "context":       context,
        "answer":        answer,
        "llm_available": LLM_AVAILABLE,
    }
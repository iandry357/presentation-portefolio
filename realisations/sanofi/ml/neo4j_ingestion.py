"""
neo4j_ingestion.py
------------------
Charge therapeutic_insight.json dans Neo4j.
- Repart d'un graphe vide à chaque run (DETACH DELETE total)
- Crée les noeuds : Cluster, Target, Disease, Drug, Pathway
- Crée les relations : CLUSTER_HAS_TARGET, TARGET_TREATS, TARGET_IN_PATHWAY, DRUG_TARGETS
- Lit les credentials depuis les variables d'environnement

Usage :
    python neo4j_ingestion.py
"""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

# ---------------------------------------------------------------------------
# PARAMÈTRES CONFIGURABLES
# ---------------------------------------------------------------------------
RESULTS_DIR = Path(__file__).parent / "results"
INPUT_FILE = RESULTS_DIR / "therapeutic_insight.json"

load_dotenv()
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# ---------------------------------------------------------------------------
# CONNEXION
# ---------------------------------------------------------------------------

def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# ---------------------------------------------------------------------------
# NETTOYAGE
# ---------------------------------------------------------------------------

def clear_graph(session):
    session.run("MATCH (n) DETACH DELETE n")
    print("[CLEAR] Graphe vidé.")


# ---------------------------------------------------------------------------
# CRÉATION DES NOEUDS
# ---------------------------------------------------------------------------

def create_cluster(session, cluster: dict):
    session.run(
        """
        CREATE (c:Cluster {
            cluster_id:      $cluster_id,
            label:           $label,
            count:           $count,
            bio_score_avg:   $bio_score_avg,
            approved_drug_rate: $approved_drug_rate,
            profile:         $profile
        })
        """,
        cluster_id=cluster["cluster_id"],
        label=cluster.get("label", ""),
        count=cluster.get("count", 0),
        bio_score_avg=cluster.get("bio_score_avg", 0.0),
        approved_drug_rate=cluster.get("approved_drug_rate", 0.0),
        profile=cluster.get("profile", ""),
    )


def create_target(session, target: dict):
    session.run(
        """
        MERGE (t:Target {ensembl_id: $ensembl_id})
        SET t.symbol        = $symbol,
            t.approved_name = $approved_name,
            t.target_class  = $target_class,
            t.score         = $score,
            t.frequency     = $frequency,
            t.has_approved_drug  = $has_approved_drug,
            t.max_clinical_stage = $max_clinical_stage,
            t.tractability  = $tractability
        """,
        ensembl_id=target["ensembl_id"],
        symbol=target.get("symbol", ""),
        approved_name=target.get("approved_name", ""),
        target_class=target.get("target_class", []),
        score=target.get("score", 0.0),
        frequency=target.get("frequency", 0),
        has_approved_drug=target.get("has_approved_drug", False),
        max_clinical_stage=target.get("max_clinical_stage", ""),
        tractability=target.get("tractability", []),
    )


def create_disease(session, disease_name: str):
    session.run(
        "MERGE (d:Disease {name: $name})",
        name=disease_name,
    )


def create_drug(session, drug_name: str):
    session.run(
        "MERGE (dr:Drug {name: $name})",
        name=drug_name,
    )


def create_pathway(session, pathway: dict):
    session.run(
        "MERGE (p:Pathway {id: $id}) SET p.name = $name",
        id=pathway["id"],
        name=pathway.get("name", ""),
    )


# ---------------------------------------------------------------------------
# CRÉATION DES RELATIONS
# ---------------------------------------------------------------------------

def link_cluster_target(session, cluster_id: int, ensembl_id: str):
    session.run(
        """
        MATCH (c:Cluster {cluster_id: $cluster_id})
        MATCH (t:Target  {ensembl_id: $ensembl_id})
        MERGE (c)-[:CLUSTER_HAS_TARGET]->(t)
        """,
        cluster_id=cluster_id,
        ensembl_id=ensembl_id,
    )


def link_target_disease(session, ensembl_id: str, disease_name: str):
    session.run(
        """
        MATCH (t:Target  {ensembl_id: $ensembl_id})
        MATCH (d:Disease {name: $disease_name})
        MERGE (t)-[:TARGET_TREATS]->(d)
        """,
        ensembl_id=ensembl_id,
        disease_name=disease_name,
    )


def link_target_pathway(session, ensembl_id: str, pathway_id: str):
    session.run(
        """
        MATCH (t:Target  {ensembl_id: $ensembl_id})
        MATCH (p:Pathway {id: $pathway_id})
        MERGE (t)-[:TARGET_IN_PATHWAY]->(p)
        """,
        ensembl_id=ensembl_id,
        pathway_id=pathway_id,
    )


def link_drug_target(session, drug_name: str, ensembl_id: str):
    session.run(
        """
        MATCH (dr:Drug  {name: $drug_name})
        MATCH (t:Target {ensembl_id: $ensembl_id})
        MERGE (dr)-[:DRUG_TARGETS]->(t)
        """,
        drug_name=drug_name,
        ensembl_id=ensembl_id,
    )


# ---------------------------------------------------------------------------
# INGESTION PRINCIPALE
# ---------------------------------------------------------------------------

def ingest(data: dict, session):
    clusters = data.get("clusters", [])

    counters = {
        "clusters": 0,
        "targets": 0,
        "diseases": 0,
        "drugs": 0,
        "pathways": 0,
        "rel_cluster_target": 0,
        "rel_target_disease": 0,
        "rel_target_pathway": 0,
        "rel_drug_target": 0,
    }

    # for cluster in clusters:
    #     create_cluster(session, cluster)
    #     counters["clusters"] += 1
    total_clusters = len(clusters)
    for cluster in clusters:
        print(f"[INGEST] Cluster {cluster['cluster_id']+1}/{total_clusters} — {cluster.get('label','?')} ({len(cluster.get('targets',[]))} targets)", flush=True)
        create_cluster(session, cluster)
        counters["clusters"] += 1

        for target in cluster.get("targets", []):
            create_target(session, target)
            counters["targets"] += 1

            link_cluster_target(session, cluster["cluster_id"], target["ensembl_id"])
            counters["rel_cluster_target"] += 1

            # Diseases depuis source_diseases de la target (lien précis)
            for disease_name in target.get("source_diseases", []):
                create_disease(session, disease_name)
                counters["diseases"] += 1
                link_target_disease(session, target["ensembl_id"], disease_name)
                counters["rel_target_disease"] += 1

            # Pathways
            for pathway in target.get("pathways", [])[:10]:
                create_pathway(session, pathway)
                counters["pathways"] += 1
                link_target_pathway(session, target["ensembl_id"], pathway["id"])
                counters["rel_target_pathway"] += 1

            # Drugs
            for drug_name in target.get("drugs", []):
                create_drug(session, drug_name)
                counters["drugs"] += 1
                link_drug_target(session, drug_name, target["ensembl_id"])
                counters["rel_drug_target"] += 1

    return counters


# ---------------------------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------------------------

def main():
    print(f"[START] Lecture de {INPUT_FILE}")
    start = time.time()

    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Fichier introuvable : {INPUT_FILE}")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"[INFO] {data.get('n_clusters', '?')} clusters — généré le {data.get('generated_at', '?')}")

    driver = get_driver()
    with driver.session() as session:
        clear_graph(session)
        counters = ingest(data, session)

    driver.close()

    elapsed = time.time() - start
    print("\n[RÉSUMÉ]")
    print(f"  Clusters   : {counters['clusters']}")
    print(f"  Targets    : {counters['targets']}")
    print(f"  Diseases   : {counters['diseases']}")
    print(f"  Drugs      : {counters['drugs']}")
    print(f"  Pathways   : {counters['pathways']}")
    print(f"  REL cluster→target   : {counters['rel_cluster_target']}")
    print(f"  REL target→disease   : {counters['rel_target_disease']}")
    print(f"  REL target→pathway   : {counters['rel_target_pathway']}")
    print(f"  REL drug→target      : {counters['rel_drug_target']}")
    print(f"\n[DONE] Durée totale : {elapsed:.1f}s")


if __name__ == "__main__":
    main()
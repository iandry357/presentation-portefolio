"""
therapeutic_insight.py
Release 2 Sanofi — Therapeutic Insight

Script one-shot pré-calculé.
Lit clustering.json → interroge OpenTargets GraphQL → génère therapeutic_insight.json

Exécution :
    python therapeutic_insight.py

Paramètres configurables en tête de script.
"""

import json
import os
import time
import requests
from collections import defaultdict
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Paramètres configurables
# ---------------------------------------------------------------------------

DISEASES_PER_CONDITION = 5        # Nb de diseases OpenTargets retournées par condition
SCORE_THRESHOLD_DISEASE = 0       # Seuil score disease search (0 = tout garder)
TARGETS_PER_DISEASE = 25          # Nb de cibles biologiques par disease
REQUEST_DELAY_SEC = 0.05           # Délai entre chaque batch de requêtes (secondes)

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------

CLUSTERING_PATH = os.path.join(os.path.dirname(__file__), "results", "clustering.json")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results", "therapeutic_insight.json")
OT_GRAPHQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"

# ---------------------------------------------------------------------------
# Requêtes GraphQL
# ---------------------------------------------------------------------------

QUERY_SEARCH_DISEASE = """
query SearchDisease($queryString: String!) {
  search(queryString: $queryString, entityNames: ["disease"], page: {index: 0, size: %(size)s}) {
    hits {
      id
      name
      score
    }
  }
}
""" % {"size": DISEASES_PER_CONDITION}

QUERY_DISEASE_TARGETS = """
query DiseaseTargets($efoId: String!) {
  disease(efoId: $efoId) {
    id
    name
    associatedTargets(page: {index: 0, size: %(size)s}) {
      rows {
        target {
          id
          approvedSymbol
          approvedName
          targetClass { label }
          pathways { pathway pathwayId }
          interactions(page: {index: 0, size: 5}) {
            rows {
              targetB { approvedSymbol }
              score
            }
          }
          tractability { label modality value }
        }
        score
      }
    }
  }
}

""" % {"size": TARGETS_PER_DISEASE}

QUERY_TARGET_KNOWN_DRUGS = """
query TargetKnownDrugs($ensemblId: String!) {
  target(ensemblId: $ensemblId) {
    id
    approvedSymbol
    drugAndClinicalCandidates {
      rows {
        id
        maxClinicalStage
        drug {
          id
          name
        }
        diseases {
          disease {
            id
            name
          }
        }
      }
    }
  }
}
"""

# ---------------------------------------------------------------------------
# Client OpenTargets
# ---------------------------------------------------------------------------

def _ot_post(query: str, variables: dict) -> dict:
    """Appel POST vers OpenTargets GraphQL avec gestion basique d'erreur."""
    try:
        resp = requests.post(
            OT_GRAPHQL_URL,
            json={"query": query, "variables": variables},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            print(f"  [OT GraphQL error] {data['errors']}")
            return {}
        return data.get("data", {})
    except requests.RequestException as e:
        print(f"  [OT request failed] {e}")
        return {}


# ---------------------------------------------------------------------------
# Normalisation des conditions
# ---------------------------------------------------------------------------

def _normalize_condition(condition: str) -> list[str]:
    """
    Retourne une ou deux variantes d'une condition médicale.
    Si la condition contient une virgule : retourne les 2 formes.
      "Colitis, Ulcerative" → ["Colitis, Ulcerative", "Ulcerative Colitis"]
    Sinon : retourne la condition telle quelle.
    """
    condition = condition.strip()
    if "," in condition:
        parts = [p.strip() for p in condition.split(",", 1)]
        inverted = f"{parts[1]} {parts[0]}"
        return [condition, inverted]
    return [condition]


# ---------------------------------------------------------------------------
# Étape 1 — Extraction des conditions par cluster
# ---------------------------------------------------------------------------

def _extract_conditions_by_cluster(clustering: dict) -> dict[int, dict[str, int]]:
    """
    Pour chaque cluster_id, retourne un dict {condition: fréquence}.
    Toutes les conditions sont conservées (pas de limite).
    """
    conditions_by_cluster: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for trial in clustering.get("trials", []):
        cluster_id = trial.get("cluster_id")
        conditions = trial.get("conditions", [])
        if cluster_id is None:
            continue
        for cond in conditions:
            if cond and cond.strip():
                conditions_by_cluster[cluster_id][cond.strip()] += 1

    # Trier par fréquence décroissante
    result = {}
    for cid, cond_freq in conditions_by_cluster.items():
        result[cid] = dict(
            sorted(cond_freq.items(), key=lambda x: x[1], reverse=True)
        )

    return result


# ---------------------------------------------------------------------------
# Étape 2 — Search diseases OpenTargets pour une condition
# ---------------------------------------------------------------------------

def _search_diseases_for_condition(condition: str) -> list[dict]:
    """
    Lance 1 ou 2 requêtes selon présence de virgule.
    Retourne une liste dédupliquée de {id, name, score} avec score max.
    """
    variants = _normalize_condition(condition)
    disease_map: dict[str, dict] = {}

    for variant in variants:
        time.sleep(REQUEST_DELAY_SEC)
        data = _ot_post(QUERY_SEARCH_DISEASE, {"queryString": variant})
        hits = data.get("search", {}).get("hits", [])

        for hit in hits:
            if hit["score"] < SCORE_THRESHOLD_DISEASE:
                continue
            disease_id = hit["id"]
            if disease_id not in disease_map or hit["score"] > disease_map[disease_id]["score"]:
                disease_map[disease_id] = {
                    "id": disease_id,
                    "name": hit["name"],
                    "score": hit["score"],
                }

    return list(disease_map.values())


# ---------------------------------------------------------------------------
# Étape 3 — Fetch cibles biologiques pour une disease
# ---------------------------------------------------------------------------

def _fetch_targets_for_disease(disease_id: str) -> list[dict]:
    """
    Retourne les cibles biologiques associées à une disease.
    Format : {ensembl_id, symbol, score}
    """
    time.sleep(REQUEST_DELAY_SEC)
    data = _ot_post(QUERY_DISEASE_TARGETS, {"efoId": disease_id})
    disease_data = data.get("disease", {})
    if not disease_data:
        return []

    rows = disease_data.get("associatedTargets", {}).get("rows", [])
    targets = []
    for row in rows:
        target = row.get("target", {})
        if not target.get("id"):
            continue

        # Pathways
        pathways = [
            {"id": p["pathwayId"], "name": p["pathway"]}
            for p in target.get("pathways", [])
            if p.get("pathwayId") and p.get("pathway")
        ]

        # Interactions — partenaires protéiques score > 0.5
        interactions = [
            r["targetB"]["approvedSymbol"]
            for r in target.get("interactions", {}).get("rows", [])
            if r.get("targetB") and r.get("score", 0) > 0.5
        ]

        # Tractability — garder uniquement les true
        tractability = [
            f"{t['label']} ({t['modality']})"
            for t in target.get("tractability", [])
            if t.get("value") is True
        ]

        # Target class
        target_class = [
            tc["label"]
            for tc in target.get("targetClass", [])
            if tc.get("label")
        ]

        targets.append({
            "ensembl_id": target["id"],
            "symbol": target.get("approvedSymbol", ""),
            "approved_name": target.get("approvedName", ""),
            "target_class": target_class,
            "score": row.get("score", 0.0),
            "pathways": pathways,
            "interactions": interactions,
            "tractability": tractability,
        })
    return targets


# ---------------------------------------------------------------------------
# Étape 4 — Fetch knownDrugs pour une cible
# ---------------------------------------------------------------------------

# Mapping phase clinique → valeur ordinale pour trouver le max
PHASE_RANK = {
    "PHASE1": 1,
    "PHASE2": 2,
    "PHASE3": 3,
    "PHASE4": 4,
    "APPROVAL": 5,
    "APPROVED": 5,
}

def _fetch_known_drugs_for_target(ensembl_id: str) -> dict:
    """
    Retourne {has_approved_drug: bool, max_clinical_stage: str} pour une cible.
    """
    time.sleep(REQUEST_DELAY_SEC)
    data = _ot_post(QUERY_TARGET_KNOWN_DRUGS, {"ensemblId": ensembl_id})
    target_data = data.get("target", {})
    if not target_data:
        return {"has_approved_drug": False, "max_clinical_stage": None}

    rows = target_data.get("drugAndClinicalCandidates", {}).get("rows", [])
    has_approved = False
    max_rank = 0
    max_stage = None

    for row in rows:
        stage = (row.get("maxClinicalStage") or "").upper()

        if stage == "APPROVAL":
            has_approved = True

        rank = PHASE_RANK.get(stage, 0)
        if rank > max_rank:
            max_rank = rank
            max_stage = stage

    if has_approved:
        max_stage = "APPROVAL"

    drug_names = list({
        row["drug"]["name"]
        for row in rows
        if row.get("drug") and row["drug"].get("name")
    })

    return {
        "has_approved_drug": has_approved,
        "max_clinical_stage": max_stage,
        "drugs": drug_names,
    }


# ---------------------------------------------------------------------------
# Étape 5 — Agrégation des cibles par cluster
# ---------------------------------------------------------------------------

def _aggregate_targets_for_cluster(
    cluster_id: int,
    conditions_freq: dict[str, int],
) -> list[dict]:
    """
    Pour un cluster donné :
    - Parcourt toutes ses conditions
    - Search diseases pour chaque condition
    - Fetch cibles pour chaque disease unique
    - Agrège score (max) et frequency (transversale) par cible
    - Fetch knownDrugs pour chaque cible unique
    Retourne la liste des cibles enrichies.
    """
    print(f"\n  Cluster {cluster_id} — {len(conditions_freq)} conditions uniques")

    # Collecte de toutes les diseases pour ce cluster (déduplication par ID)
    all_diseases: dict[str, dict] = {}
    for condition in conditions_freq.keys():
        diseases = _search_diseases_for_condition(condition)
        for d in diseases:
            did = d["id"]
            if did not in all_diseases or d["score"] > all_diseases[did]["score"]:
                all_diseases[did] = d

    print(f"    → {len(all_diseases)} diseases uniques trouvées")

    # Collecte des cibles biologiques (agrégation score max + fréquence)
    target_map: dict[str, dict] = {}
    for disease_id in all_diseases:
        targets = _fetch_targets_for_disease(disease_id)
        for t in targets:
            tid = t["ensembl_id"]
            if tid not in target_map:
                target_map[tid] = {
                    "ensembl_id": tid,
                    "symbol": t["symbol"],
                    "approved_name": t.get("approved_name", ""),
                    "target_class": t.get("target_class", []),
                    "score": t["score"],
                    "frequency": 1,
                    "pathways": t.get("pathways", []),
                    "interactions": t.get("interactions", []),
                    "tractability": t.get("tractability", []),
                }
            else:
                target_map[tid]["frequency"] += 1
                if t["score"] > target_map[tid]["score"]:
                    target_map[tid]["score"] = t["score"]
                # Enrichir pathways/interactions/tractability si plus complets
                if not target_map[tid]["approved_name"] and t.get("approved_name"):
                    target_map[tid]["approved_name"] = t["approved_name"]
                if not target_map[tid]["target_class"] and t.get("target_class"):
                    target_map[tid]["target_class"] = t["target_class"]
                if not target_map[tid]["pathways"] and t.get("pathways"):
                    target_map[tid]["pathways"] = t["pathways"]
                if not target_map[tid]["interactions"] and t.get("interactions"):
                    target_map[tid]["interactions"] = t["interactions"]
                if not target_map[tid]["tractability"] and t.get("tractability"):
                    target_map[tid]["tractability"] = t["tractability"]

    print(f"    → {len(target_map)} cibles biologiques uniques")

    # Fetch knownDrugs pour chaque cible unique
    targets_out = []
    for tid, target in target_map.items():
        drug_info = _fetch_known_drugs_for_target(tid)
        targets_out.append({
            "ensembl_id": target["ensembl_id"],
            "symbol": target["symbol"],
            "approved_name": target.get("approved_name", ""),
            "target_class": target.get("target_class", []),
            "score": round(target["score"], 4),
            "frequency": target["frequency"],
            "has_approved_drug": drug_info["has_approved_drug"],
            "max_clinical_stage": drug_info["max_clinical_stage"],
            "drugs": drug_info.get("drugs", []),
            "pathways": target.get("pathways", []),
            "interactions": target.get("interactions", []),
            "tractability": target.get("tractability", []),
        })

    # Tri : signaux forts d'abord (score desc), signaux faibles repérables par frequency
    targets_out.sort(key=lambda x: x["score"], reverse=True)
    return targets_out


# ---------------------------------------------------------------------------
# Étape 6 — Calcul des profils cluster
# ---------------------------------------------------------------------------

def _compute_cluster_profiles(clusters_enriched: list[dict]) -> list[dict]:
    """
    Calcule bio_score_avg et approved_drug_rate par cluster.
    Assigne un profil (Mature / Émergent / Actif / Exploratoire)
    basé sur la médiane des 11 clusters — pas de seuils hardcodés.
    """
    for cluster in clusters_enriched:
        targets = cluster["targets"]
        if not targets:
            cluster["bio_score_avg"] = 0.0
            cluster["approved_drug_rate"] = 0.0
            continue

        scores = [t["score"] for t in targets]
        approved = [1 for t in targets if t["has_approved_drug"]]

        cluster["bio_score_avg"] = round(sum(scores) / len(scores), 4)
        cluster["approved_drug_rate"] = round(len(approved) / len(targets), 4)

    # Médiane dynamique sur les 11 clusters
    bio_scores = [c["bio_score_avg"] for c in clusters_enriched]
    drug_rates = [c["approved_drug_rate"] for c in clusters_enriched]

    bio_scores_sorted = sorted(bio_scores)
    drug_rates_sorted = sorted(drug_rates)
    n = len(clusters_enriched)
    median_bio = bio_scores_sorted[n // 2]
    median_drug = drug_rates_sorted[n // 2]

    print(f"\n  Médiane bio_score_avg   : {median_bio}")
    print(f"  Médiane approved_drug_rate : {median_drug}")

    for cluster in clusters_enriched:
        high_bio = cluster["bio_score_avg"] >= median_bio
        high_drug = cluster["approved_drug_rate"] >= median_drug

        if high_bio and high_drug:
            cluster["profile"] = "Mature"
        elif high_bio and not high_drug:
            cluster["profile"] = "Émergent"
        elif not high_bio and high_drug:
            cluster["profile"] = "Actif"
        else:
            cluster["profile"] = "Exploratoire"

    return clusters_enriched


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def run() -> dict:
    print("=== Therapeutic Insight — Release 2 Sanofi ===\n")

    # Chargement clustering.json
    if not os.path.exists(CLUSTERING_PATH):
        raise FileNotFoundError(f"clustering.json introuvable : {CLUSTERING_PATH}")

    with open(CLUSTERING_PATH, "r") as f:
        clustering = json.load(f)

    clusters_meta = {c["cluster_id"]: c for c in clustering.get("clusters", [])}
    print(f"Clusters chargés : {len(clusters_meta)}")
    print(f"Trials chargés   : {len(clustering.get('trials', []))}")

    # Extraction conditions par cluster
    conditions_by_cluster = _extract_conditions_by_cluster(clustering)

    # Traitement cluster par cluster
    clusters_enriched = []
    for cluster_id in sorted(conditions_by_cluster.keys()):
        meta = clusters_meta.get(cluster_id, {})
        conditions_freq = conditions_by_cluster[cluster_id]

        print(f"\n{'='*60}")
        print(f"Cluster {cluster_id} — {meta.get('label', 'N/A')} ({meta.get('count', 0)} trials)")

        targets = _aggregate_targets_for_cluster(cluster_id, conditions_freq)

        # Récupération des diseases_searched pour traçabilité
        diseases_searched = list(conditions_freq.keys())

        clusters_enriched.append({
            "cluster_id": cluster_id,
            "label": meta.get("label", ""),
            "count": meta.get("count", 0),
            "diseases_searched": diseases_searched,
            "bio_score_avg": 0.0,       # calculé à l'étape suivante
            "approved_drug_rate": 0.0,  # calculé à l'étape suivante
            "profile": "",              # calculé à l'étape suivante
            "targets": targets,
        })

    # Calcul des profils
    clusters_enriched = _compute_cluster_profiles(clusters_enriched)

    # Construction du résultat final
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_clusters": len(clusters_enriched),
        "parameters": {
            "diseases_per_condition": DISEASES_PER_CONDITION,
            "score_threshold_disease": SCORE_THRESHOLD_DISEASE,
            "targets_per_disease": TARGETS_PER_DISEASE,
            "request_delay_sec": REQUEST_DELAY_SEC,
        },
        "clusters": clusters_enriched,
    }

    # Écriture JSON
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"✓ therapeutic_insight.json généré")
    print(f"  Clusters traités : {len(clusters_enriched)}")
    for c in clusters_enriched:
        print(
            f"  Cluster {c['cluster_id']} — {c['label']} "
            f"| {len(c['targets'])} cibles "
            f"| profil : {c['profile']} "
            f"| bio_score : {c['bio_score_avg']} "
            f"| drug_rate : {c['approved_drug_rate']}"
        )

    return result


if __name__ == "__main__":
    run()
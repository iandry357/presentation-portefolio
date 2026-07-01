"""
prepare_dataset.py
------------------
Prépare le dataset de fine-tuning pour Mistral 7B drug discovery.

Étapes :
    1. Télécharge PubMedQA (PQA-L + PQA-A) depuis HuggingFace
    2. Génère des paires QA synthétiques depuis therapeutic_insight.json
       via Gemma 3 12B Ollama local
    3. Normalise au format Mistral Instruct
    4. Split 80/20 → dataset_train.jsonl + dataset_eval.jsonl

Usage :
    python prepare_dataset.py
    python prepare_dataset.py --skip-pubmedqa      # synthétique uniquement
    python prepare_dataset.py --skip-synthetic     # PubMedQA uniquement

Prérequis :
    - Ollama local avec gemma3:12b pullé
    - data/therapeutic_insight.json rapatrié via scp depuis OVH
"""

import argparse
import json
import random
import time
from pathlib import Path

import httpx
from datasets import load_dataset

# ---------------------------------------------------------------------------
# PARAMÈTRES CONFIGURABLES
# ---------------------------------------------------------------------------

DATA_DIR               = Path(__file__).parent / "data"
THERAPEUTIC_JSON       = DATA_DIR / "therapeutic_insight.json"
CLUSTERING_JSON        = DATA_DIR / "clustering.json"

# Chemin source — ml/results/ (relatif à training/)
ML_RESULTS_DIR = Path(__file__).parent.parent / "ml" / "results"

TRAIN_OUTPUT           = DATA_DIR / "dataset_train.jsonl"
EVAL_OUTPUT            = DATA_DIR / "dataset_eval.jsonl"

OLLAMA_URL             = "http://localhost:11434/api/generate"
OLLAMA_MODEL           = "gemma3:12b"
OLLAMA_TIMEOUT         = 120        # secondes par appel

PUBMEDQA_PQA_L_SIZE    = 1000       # toutes les PQA-L expert-annotated
PUBMEDQA_PQA_A_SIZE    = 2000       # sous-ensemble PQA-A artificiel

# Génération synthétique
N_PAIRS_PER_CLUSTER    = 4          # paires Type 1 — cluster
N_PAIRS_PER_TARGET     = 2          # paires Type 2 — target (top 20 par cluster)
N_PAIRS_COMPARATIVE    = 2          # paires Type 3 — comparatif par paire adjacente

TRAIN_RATIO            = 0.80
RANDOM_SEED            = 42

OVH_USER       = "ubuntu"
OVH_HOST       = "51.68.130.23"
OVH_RESULTS_DIR = "/home/ubuntu/ml-project/realisations/sanofi/ml/results"

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _log(msg: str):
    print(f"[PREPARE] {msg}", flush=True)


def _save_jsonl(records: list[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    _log(f"Saved {len(records)} records → {path}")


def _to_mistral_format(instruction: str, context: str, response: str) -> dict:
    """
    Formate une paire QA au format Mistral Instruct.
    """
    if context.strip():
        prompt = f"[INST] {instruction}\n\nContext:\n{context} [/INST]"
    else:
        prompt = f"[INST] {instruction} [/INST]"
    return {
        "text": f"{prompt} {response}",
        "instruction": instruction,
        "context": context,
        "response": response,
    }

def _build_domain_keywords(clustering_path: Path) -> list[str]:
    """
    Extrait les mots-clés de filtrage depuis clustering.json.
    Utilise les labels des clusters + leurs keywords.
    """
    if not clustering_path.exists():
        raise FileNotFoundError(
            f"clustering.json introuvable : {clustering_path}\n"
            "Rapatrier via : scp ubuntu@51.68.130.23:/home/ubuntu/ml-project/"
            "realisations/sanofi/ml/results/clustering.json "
            "realisations/sanofi/training/data/"
        )
    with open(clustering_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    keywords = set()
    for cluster in data.get("clusters", []):
        # Label du cluster — chaque mot significatif
        for word in cluster.get("label", "").lower().split():
            if len(word) > 3:
                keywords.add(word)
        # Keywords du cluster
        for kw in cluster.get("keywords", []):
            keywords.add(kw.lower())

    _log(f"Keywords extraits depuis clustering.json : {len(keywords)} termes")
    return list(keywords)

def _ensure_data_files(source: str = "ovh"):
    """
    Rapatrie les JSON nécessaires vers training/data/.
    source='ovh'   → scp depuis OVH (source de vérité — prod)
    source='local' → copie depuis ml/results/ (dev local)
    """
    import shutil
    import subprocess
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for filename in ["therapeutic_insight.json", "clustering.json"]:
        dest = DATA_DIR / filename

        if source == "local":
            src = ML_RESULTS_DIR / filename
            if not src.exists():
                raise FileNotFoundError(
                    f"{filename} introuvable dans ml/results/\n"
                    f"Vérifier que le pipeline a bien tourné en local."
                )
            shutil.copy2(str(src), str(dest))
            _log(f"{filename} copié depuis local ml/results/ → {dest}")

        else:  # ovh
            src = f"{OVH_USER}@{OVH_HOST}:{OVH_RESULTS_DIR}/{filename}"
            _log(f"scp {filename} depuis OVH...")
            result = subprocess.run(
                ["scp", src, str(dest)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"scp échoué pour {filename} :\n{result.stderr}\n"
                    f"Vérifier la connexion SSH vers {OVH_HOST}"
                )
            _log(f"{filename} rapatrié depuis OVH → {dest}")
        
# ---------------------------------------------------------------------------
# ÉTAPE 1 — PubMedQA
# ---------------------------------------------------------------------------

def _is_relevant(question: str, context: str, domain_keywords: list[str]) -> bool:
    text = (question + " " + context).lower()
    return any(kw in text for kw in domain_keywords)


def load_pubmedqa(domain_keywords: list[str]) -> list[dict]:
    """
    Charge PubMedQA PQA-L (expert) + sous-ensemble PQA-A (artificiel).
    Filtre par domaines pertinents pour les 11 clusters Sanofi.
    Normalise au format Mistral Instruct.
    """
    _log("Chargement PubMedQA (filtré par domaine)...")
    records = []

    # PQA-L — 1000 expert-annotated — on garde tous les pertinents
    try:
        ds_l = load_dataset("qiaojin/PubMedQA", "pqa_labeled", split="train")
        count = 0
        skipped = 0
        for item in ds_l:
            context  = " ".join(item.get("context", {}).get("contexts", []))
            question = item.get("question", "")
            answer   = item.get("long_answer", "")
            if not question or not answer:
                continue
            if not _is_relevant(question, context, domain_keywords):
                skipped += 1
                continue
            records.append(_to_mistral_format(
                instruction=question,
                context=context[:1000],
                response=answer,
            ))
            count += 1
            if count >= PUBMEDQA_PQA_L_SIZE:
                break
        _log(f"PQA-L : {count} exemples retenus / {skipped} filtrés")
    except Exception as e:
        _log(f"PQA-L erreur : {e}")

    # PQA-A — on parcourt aléatoirement et on garde les pertinents jusqu'à PUBMEDQA_PQA_A_SIZE
    try:
        ds_a    = load_dataset("qiaojin/PubMedQA", "pqa_artificial", split="train")
        indices = random.sample(range(len(ds_a)), min(PUBMEDQA_PQA_A_SIZE * 5, len(ds_a)))
        count   = 0
        skipped = 0
        for i in indices:
            if count >= PUBMEDQA_PQA_A_SIZE:
                break
            item     = ds_a[i]
            context  = " ".join(item.get("context", {}).get("contexts", []))
            question = item.get("question", "")
            answer   = item.get("long_answer", "")
            if not question or not answer:
                continue
            if not _is_relevant(question, context, domain_keywords):
                skipped += 1
                continue
            records.append(_to_mistral_format(
                instruction=question,
                context=context[:1000],
                response=answer,
            ))
            count += 1
        _log(f"PQA-A : {count} exemples retenus / {skipped} filtrés")
    except Exception as e:
        _log(f"PQA-A erreur : {e}")

    _log(f"PubMedQA total après filtrage : {len(records)} exemples")
    return records


# ---------------------------------------------------------------------------
# ÉTAPE 2 — Génération synthétique via Gemma 3 12B Ollama
# ---------------------------------------------------------------------------

def _ollama_generate(prompt: str) -> str:
    """
    Appel Ollama — retourne la réponse générée ou chaîne vide si échec.
    """
    try:
        resp = httpx.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 300,
                },
            },
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        _log(f"Ollama erreur : {e}")
        return ""


def _parse_qa(raw: str) -> tuple[str, str] | None:
    """
    Parse la réponse Ollama — extrait Q: et A:.
    Retourne (question, answer) ou None si parsing échoue.
    """
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    question, answer = "", []
    in_answer = False

    for line in lines:
        if line.startswith("Q:") or line.startswith("Question:"):
            question = line.split(":", 1)[1].strip()
        elif line.startswith("A:") or line.startswith("Answer:"):
            in_answer = True
            answer.append(line.split(":", 1)[1].strip())
        elif in_answer:
            answer.append(line)

    if question and answer:
        return question, " ".join(answer)
    return None


def _generate_cluster_pairs(cluster: dict) -> list[dict]:
    """
    Type 1 — Questions sur le profil d'un cluster.
    """
    top_targets = sorted(cluster["targets"], key=lambda t: t["score"], reverse=True)[:5]
    target_summary = ", ".join([f"{t['symbol']} (score={t['score']:.3f})" for t in top_targets])

    prompt = f"""You are a drug discovery expert. Generate {N_PAIRS_PER_CLUSTER} question-answer pairs about the following therapeutic cluster.

Cluster: {cluster['label']}
Profile: {cluster['profile']}
Bio score average: {cluster['bio_score_avg']:.3f}
Approved drug rate: {cluster['approved_drug_rate']:.3f}
Trial count: {cluster['count']}
Top biological targets: {target_summary}

Rules:
- Questions must be relevant to drug discovery and R&D strategy
- Answers must be grounded in the provided data
- Format each pair exactly as:
  Q: <question>
  A: <answer>

Generate {N_PAIRS_PER_CLUSTER} pairs:"""

    raw = _ollama_generate(prompt)
    pairs = []

    # Parse multiple QA pairs
    blocks = raw.split("\nQ:")
    for block in blocks:
        if not block.strip():
            continue
        if not block.startswith("Q:"):
            block = "Q:" + block
        parsed = _parse_qa(block)
        if parsed:
            q, a = parsed
            context = (
                f"Cluster: {cluster['label']} | Profile: {cluster['profile']} | "
                f"Bio score: {cluster['bio_score_avg']:.3f} | "
                f"Drug rate: {cluster['approved_drug_rate']:.3f} | "
                f"Top targets: {target_summary}"
            )
            pairs.append(_to_mistral_format(q, context, a))

    return pairs


def _generate_target_pairs(target: dict, cluster_label: str) -> list[dict]:
    """
    Type 2 — Questions sur une target spécifique.
    """
    drugs = ", ".join(target.get("drugs", [])[:5]) or "none"
    pathways = ", ".join([p["name"] for p in target.get("pathways", [])[:3]]) or "unknown"
    diseases = ", ".join(target.get("source_diseases", [])[:3]) or "unknown"
    tractability = ", ".join(target.get("tractability", [])[:2]) or "unknown"

    prompt = f"""You are a drug discovery expert. Generate {N_PAIRS_PER_TARGET} question-answer pairs about the following biological target.

Target: {target['symbol']} ({target.get('approved_name', '')})
Cluster context: {cluster_label}
OpenTargets score: {target['score']:.4f}
Cross-cluster frequency: {target['frequency']}
Has approved drug: {target['has_approved_drug']}
Max clinical stage: {target.get('max_clinical_stage', 'unknown')}
Associated drugs: {drugs}
Key pathways: {pathways}
Source diseases: {diseases}
Druggability: {tractability}

Rules:
- Questions must be relevant to drug discovery
- Answers must be grounded in the provided data
- Format each pair exactly as:
  Q: <question>
  A: <answer>

Generate {N_PAIRS_PER_TARGET} pairs:"""

    raw = _ollama_generate(prompt)
    pairs = []

    blocks = raw.split("\nQ:")
    for block in blocks:
        if not block.strip():
            continue
        if not block.startswith("Q:"):
            block = "Q:" + block
        parsed = _parse_qa(block)
        if parsed:
            q, a = parsed
            context = (
                f"Target: {target['symbol']} | Score: {target['score']:.4f} | "
                f"Frequency: {target['frequency']} | Drugs: {drugs} | "
                f"Pathways: {pathways} | Diseases: {diseases}"
            )
            pairs.append(_to_mistral_format(q, context, a))

    return pairs


def _generate_comparative_pairs(cluster_a: dict, cluster_b: dict) -> list[dict]:
    """
    Type 3 — Questions comparatives entre deux clusters.
    """
    prompt = f"""You are a drug discovery expert. Generate {N_PAIRS_COMPARATIVE} question-answer pairs comparing these two therapeutic clusters.

Cluster A: {cluster_a['label']}
  Profile: {cluster_a['profile']} | Bio score: {cluster_a['bio_score_avg']:.3f} | Drug rate: {cluster_a['approved_drug_rate']:.3f}

Cluster B: {cluster_b['label']}
  Profile: {cluster_b['profile']} | Bio score: {cluster_b['bio_score_avg']:.3f} | Drug rate: {cluster_b['approved_drug_rate']:.3f}

Rules:
- Questions must compare R&D maturity, opportunities, or strategy
- Answers must reference both clusters with specific data points
- Format each pair exactly as:
  Q: <question>
  A: <answer>

Generate {N_PAIRS_COMPARATIVE} pairs:"""

    raw = _ollama_generate(prompt)
    pairs = []

    blocks = raw.split("\nQ:")
    for block in blocks:
        if not block.strip():
            continue
        if not block.startswith("Q:"):
            block = "Q:" + block
        parsed = _parse_qa(block)
        if parsed:
            q, a = parsed
            context = (
                f"Cluster A: {cluster_a['label']} ({cluster_a['profile']}, "
                f"bio={cluster_a['bio_score_avg']:.3f}, drug={cluster_a['approved_drug_rate']:.3f}) | "
                f"Cluster B: {cluster_b['label']} ({cluster_b['profile']}, "
                f"bio={cluster_b['bio_score_avg']:.3f}, drug={cluster_b['approved_drug_rate']:.3f})"
            )
            pairs.append(_to_mistral_format(q, context, a))

    return pairs


def generate_synthetic(data: dict) -> list[dict]:
    """
    Génère toutes les paires synthétiques depuis therapeutic_insight.json.
    """
    clusters = data["clusters"]
    all_pairs = []
    total_calls = 0

    # Type 1 — clusters
    _log(f"Génération Type 1 — {len(clusters)} clusters × {N_PAIRS_PER_CLUSTER} paires...")
    for cluster in clusters:
        pairs = _generate_cluster_pairs(cluster)
        all_pairs.extend(pairs)
        total_calls += 1
        _log(f"  Cluster {cluster['cluster_id']} — {len(pairs)} paires générées")

    # Type 2 — targets (top 20 par cluster)
    _log(f"Génération Type 2 — targets (top 20 par cluster)...")
    for cluster in clusters:
        top_targets = sorted(cluster["targets"], key=lambda t: t["score"], reverse=True)[:20]
        for target in top_targets:
            pairs = _generate_target_pairs(target, cluster["label"])
            all_pairs.extend(pairs)
            total_calls += 1
        _log(f"  Cluster {cluster['cluster_id']} — {len(top_targets)} targets traitées")

    # Type 3 — comparatifs (clusters adjacents dans le scatter)
    _log(f"Génération Type 3 — comparatifs...")
    sorted_clusters = sorted(clusters, key=lambda c: c["bio_score_avg"])
    for i in range(len(sorted_clusters) - 1):
        pairs = _generate_comparative_pairs(sorted_clusters[i], sorted_clusters[i + 1])
        all_pairs.extend(pairs)
        total_calls += 1

    _log(f"Synthétique total : {len(all_pairs)} paires ({total_calls} appels Ollama)")
    return all_pairs


# ---------------------------------------------------------------------------
# ÉTAPE 3 — Split et sauvegarde
# ---------------------------------------------------------------------------

def split_and_save(records: list[dict]):
    """
    Mélange et split 80/20 → train + eval.
    """
    random.seed(RANDOM_SEED)
    random.shuffle(records)

    split_idx = int(len(records) * TRAIN_RATIO)
    train = records[:split_idx]
    eval_ = records[split_idx:]

    _save_jsonl(train, TRAIN_OUTPUT)
    _save_jsonl(eval_, EVAL_OUTPUT)

    _log(f"Split : {len(train)} train / {len(eval_)} eval")


# ---------------------------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Prepare fine-tuning dataset — Sanofi drug discovery")
    parser.add_argument("--skip-pubmedqa", action="store_true", help="Sauter PubMedQA")
    parser.add_argument("--skip-synthetic", action="store_true", help="Sauter la génération synthétique")
    parser.add_argument(
        "--source",
        choices=["ovh", "local"],
        default="ovh",
        help="Source des fichiers JSON — ovh (prod) ou local (dev)",
    )
    args = parser.parse_args()

    _log("=== Préparation dataset fine-tuning Mistral 7B ===")
    start = time.time()
    _ensure_data_files(source=args.source)
    all_records = []

    # PubMedQA
    if not args.skip_pubmedqa:
        domain_keywords = _build_domain_keywords(CLUSTERING_JSON)
        pubmed_records  = load_pubmedqa(domain_keywords)
        all_records.extend(pubmed_records)
    else:
        _log("--skip-pubmedqa activé")

    # Synthétique
    if not args.skip_synthetic:
        if not THERAPEUTIC_JSON.exists():
            raise FileNotFoundError(
                f"therapeutic_insight.json introuvable : {THERAPEUTIC_JSON}\n"
                "Rapatrier via : scp ubuntu@51.68.130.23:/home/ubuntu/ml-project/"
                "realisations/sanofi/ml/results/therapeutic_insight.json "
                "realisations/sanofi/training/data/"
            )
        with open(THERAPEUTIC_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        _log(f"therapeutic_insight.json chargé — {data['n_clusters']} clusters")
        synthetic_records = generate_synthetic(data)
        all_records.extend(synthetic_records)
    else:
        _log("--skip-synthetic activé")

    if not all_records:
        _log("Aucun enregistrement — arrêt.")
        return

    # Split + sauvegarde
    split_and_save(all_records)

    elapsed = time.time() - start
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    _log(f"=== Dataset prêt en {minutes}m {seconds}s — {len(all_records)} exemples total ===")


if __name__ == "__main__":
    main()
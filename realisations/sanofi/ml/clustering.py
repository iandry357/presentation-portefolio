import json
import os
import numpy as np
import sklearn.feature_extraction.text
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize
from bq_client import get_clinical_trials
from chroma_client import get_embeddings_clinical_trials
import litellm

N_CLUSTERS = 11
TFIDF_WEIGHT = 0.4
EMBED_WEIGHT = 0.6
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results", "clustering.json")

MEDICAL_STOP_WORDS = [
    "study", "patients", "placebo", "treatment", "safety",
    "clinical", "trial", "subjects", "dose", "week", "mg",
    "phase", "open", "label", "randomized", "controlled",
    "double", "blind", "efficacy", "versus", "compared",
    "period", "daily", "drug", "acid", "single",
    "healthy", "tolerability", "titre", "disease", "administration",
]


def _build_text(trial: dict) -> str:
    conditions = trial.get("metadata", {}).get("conditions", [])
    conditions_str = " ".join(conditions) if conditions else ""
    title = trial.get("title") or ""
    content = trial.get("content") or ""
    return f"{title} {conditions_str} {content}".strip()


def _top_keywords(tfidf_matrix, feature_names: list, cluster_id: int, labels, n=10) -> list:
    indices = [i for i, l in enumerate(labels) if l == cluster_id]
    if not indices:
        return []
    cluster_matrix = tfidf_matrix[indices]
    scores = cluster_matrix.mean(axis=0).A1
    top_indices = scores.argsort()[::-1][:n]
    return [feature_names[i] for i in top_indices]

def _generate_label(keywords: list) -> str:
    prompt = (
        f"You are analyzing Sanofi clinical trials clusters. "
        f"Given these top keywords from a cluster: {', '.join(keywords[:10])}. "
        f"Generate a short domain label (3-4 words max) in English that best describes "
        f"the therapeutic area or research domain. Reply with only the label, nothing else."
    )
    response = litellm.completion(
        model="mistral/mistral-small-latest",
        messages=[{"role": "user", "content": prompt}],
        api_key=MISTRAL_API_KEY,
        max_tokens=20,
    )
    return response.choices[0].message.content.strip()


def run() -> dict:
    trials = get_clinical_trials()
    embeddings_map = get_embeddings_clinical_trials()

    # Filtrer les trials qui ont un embedding
    matched = []
    skipped = []
    for t in trials:
        if t["id"] in embeddings_map:
            matched.append(t)
        else:
            skipped.append(t["id"])

    if skipped:
        print(f"Warning — {len(skipped)} trials sans embedding ignorés : {skipped}")

    print(f"Trials matchés BQ + ChromaDB : {len(matched)}")

    # TF-IDF
    texts = [_build_text(t) for t in matched]
    vectorizer = TfidfVectorizer(
        max_features=500,
        stop_words=list(sklearn.feature_extraction.text.ENGLISH_STOP_WORDS) + MEDICAL_STOP_WORDS,
        ngram_range=(1, 2),
        min_df=2,
    )
    tfidf_matrix = vectorizer.fit_transform(texts)
    feature_names = vectorizer.get_feature_names_out().tolist()
    tfidf_normalized = normalize(tfidf_matrix.toarray())

    # Embeddings
    embed_matrix = np.array([embeddings_map[t["id"]] for t in matched])
    embed_normalized = normalize(embed_matrix)

    # Combinaison pondérée
    combined = np.hstack([
        tfidf_normalized * TFIDF_WEIGHT,
        embed_normalized * EMBED_WEIGHT,
    ])

    # KMeans
    kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
    labels = kmeans.fit_predict(combined)

    # Résultats trials
    trials_out = []
    for i, trial in enumerate(matched):
        meta = trial.get("metadata", {})
        trials_out.append({
            "id": trial.get("id"),
            "title": trial.get("title"),
            "cluster_id": int(labels[i]),
            "phase": meta.get("phase"),
            "status": meta.get("status"),
            "conditions": meta.get("conditions", []),
        })

    # Résumé clusters
    tfidf_sparse = vectorizer.transform(texts)
    clusters_out = []
    for cid in range(N_CLUSTERS):
        keywords = _top_keywords(tfidf_sparse, feature_names, cid, labels)
        count = int((labels == cid).sum())
        # clusters_out.append({
        #     "cluster_id": cid,
        #     "count": count,
        #     "keywords": keywords,
        # })
        label = _generate_label(keywords)
        clusters_out.append({
            "cluster_id": cid,
            "count": count,
            "keywords": keywords,
            "label": label,
        })

    result = {
        "n_clusters": N_CLUSTERS,
        "total_trials": len(matched),
        "skipped": skipped,
        "tfidf_weight": TFIDF_WEIGHT,
        "embed_weight": EMBED_WEIGHT,
        "clusters": clusters_out,
        "trials": trials_out,
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"Clustering done — {len(matched)} trials → {N_CLUSTERS} clusters")
    for c in clusters_out:
        # print(f"  Cluster {c['cluster_id']} ({c['count']} trials): {', '.join(c['keywords'][:5])}")
        print(f"  Cluster {c['cluster_id']} — {c['label']} ({c['count']} trials): {', '.join(c['keywords'][:5])}")
    return result


if __name__ == "__main__":
    run()
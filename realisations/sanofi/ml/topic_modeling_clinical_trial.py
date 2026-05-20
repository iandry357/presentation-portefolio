import json
import os
import numpy as np
import sklearn.feature_extraction.text
import litellm
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from bq_client import get_clinical_trials

N_TOPICS = 5
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results", "topic_modeling.json")

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")

MEDICAL_STOP_WORDS = [
    "study", "patients", "placebo", "treatment", "safety",
    "clinical", "trial", "subjects", "dose", "week", "mg",
    "phase", "open", "label", "randomized", "controlled",
    "double", "blind", "efficacy", "versus", "compared",
    "period", "daily", "drug", "acid", "single",
    "healthy", "tolerability", "titre", "disease", "administration",
    "patient", "primary", "secondary", "endpoint", "group",
    "receive", "received", "including", "based", "used",
]


def _build_text(trial: dict) -> str:
    title = trial.get("title") or ""
    content = trial.get("content") or ""
    conditions = trial.get("metadata", {}).get("conditions", [])
    conditions_str = " ".join(conditions) if conditions else ""
    return f"{title} {conditions_str} {content}".strip()


def _top_keywords(lda_model, feature_names: list, topic_id: int, n=10) -> list:
    topic = lda_model.components_[topic_id]
    top_indices = topic.argsort()[::-1][:n]
    return [feature_names[i] for i in top_indices]


def _generate_label(keywords: list) -> str:
    prompt = (
        f"You are analyzing Sanofi clinical trials topics. "
        f"Given these top keywords from a topic: {', '.join(keywords[:10])}. "
        f"Generate a short narrative theme label (3-4 words max) in English that best describes "
        f"the research theme. Reply with only the label, nothing else."
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

    texts = [_build_text(t) for t in trials]

    vectorizer = CountVectorizer(
        max_features=500,
        stop_words=list(sklearn.feature_extraction.text.ENGLISH_STOP_WORDS) + MEDICAL_STOP_WORDS,
        ngram_range=(1, 2),
        min_df=2,
    )
    doc_term_matrix = vectorizer.fit_transform(texts)
    feature_names = vectorizer.get_feature_names_out().tolist()

    lda = LatentDirichletAllocation(
        n_components=N_TOPICS,
        random_state=42,
        max_iter=20,
        learning_method="batch",
    )
    doc_topic_matrix = lda.fit_transform(doc_term_matrix)

    # Topics
    topics_out = []
    for tid in range(N_TOPICS):
        keywords = _top_keywords(lda, feature_names, tid)
        label = _generate_label(keywords)
        topics_out.append({
            "topic_id": tid,
            "label": label,
            "keywords": keywords,
        })

    # Essais avec topic dominant
    trials_out = []
    for i, trial in enumerate(trials):
        topic_scores = doc_topic_matrix[i].tolist()
        dominant_topic = int(np.argmax(topic_scores))
        confidence = round(float(np.max(topic_scores)), 3)
        meta = trial.get("metadata", {})
        trials_out.append({
            "id": trial.get("id"),
            "title": trial.get("title"),
            "dominant_topic": dominant_topic,
            "dominant_label": topics_out[dominant_topic]["label"],
            "confidence": confidence,
            "phase": meta.get("phase"),
            "conditions": meta.get("conditions", []),
        })

    result = {
        "n_topics": N_TOPICS,
        "total_trials": len(trials),
        "topics": topics_out,
        "trials": trials_out,
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"Topic modeling done — {len(trials)} trials → {N_TOPICS} topics")
    for t in topics_out:
        print(f"  Topic {t['topic_id']} — {t['label']}: {', '.join(t['keywords'][:5])}")

    return result


if __name__ == "__main__":
    run()
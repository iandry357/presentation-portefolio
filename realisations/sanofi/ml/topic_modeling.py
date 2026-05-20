import json
import os
import numpy as np
import sklearn.feature_extraction.text
import litellm
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from bq_client import get_news, get_press_releases

N_TOPICS = 5
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results", "topic_modeling.json")

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")

# NEWS_STOP_WORDS = [
#     "sanofi", "company", "said", "year", "new", "also", "says",
#     "according", "would", "could", "one", "two", "three", "million",
#     "billion", "percent", "including", "based", "used", "using",
#     "depuis", "titre", "source", "résumé", "font", "color", "href",
# ]

NEWS_STOP_WORDS = [
    "sanofi", "company", "said", "year", "new", "also", "says",
    "according", "would", "could", "one", "two", "three", "million",
    "billion", "percent", "including", "based", "used", "using",
    "depuis", "titre", "source", "résumé", "font", "color", "href",
    # Stopwords français
    "le", "la", "les", "de", "du", "des", "en", "et", "un", "une",
    "il", "elle", "ils", "elles", "ce", "se", "sa", "son", "ses",
    "que", "qui", "au", "aux", "par", "sur", "pour", "dans", "est",
    "avec", "tout", "tous", "plus", "pas", "mais", "ou", "donc",
    "bfm", "rmc", "tv", "fr",
]


def _build_text(doc: dict) -> str:
    title = doc.get("title") or ""
    content = doc.get("content") or ""
    return f"{title} {content}".strip()


def _is_html(text: str) -> bool:
    """Détecte si le contenu est du HTML brut RSS inutilisable."""
    return "<a href=" in text or "<font" in text


def _top_keywords(lda_model, feature_names: list, topic_id: int, n=10) -> list:
    topic = lda_model.components_[topic_id]
    top_indices = topic.argsort()[::-1][:n]
    return [feature_names[i] for i in top_indices]


def _generate_label(keywords: list, source_hint: str) -> str:
    prompt = (
        f"You are analyzing Sanofi {source_hint} topics. "
        f"Given these top keywords from a topic: {', '.join(keywords[:10])}. "
        f"Generate a short narrative theme label (3-4 words max) in English that best describes "
        f"the communication theme. Reply with only the label, nothing else."
    )
    response = litellm.completion(
        model="mistral/mistral-small-latest",
        messages=[{"role": "user", "content": prompt}],
        api_key=MISTRAL_API_KEY,
        max_tokens=20,
    )
    return response.choices[0].message.content.strip()


def run() -> dict:
    # Charge press releases + google news
    press_releases = get_press_releases()
    news = get_news()

    # Filtre les docs avec contenu HTML brut inutilisable
    all_docs = []
    skipped = 0
    for doc in press_releases + news:
        text = _build_text(doc)
        if not text or _is_html(text) or len(text) < 100:
            skipped += 1
            continue
        all_docs.append(doc)

    print(f"Topic modeling — {len(all_docs)} docs exploitables ({skipped} skipped HTML/vide)")
    print(f"  Press Releases : {sum(1 for d in all_docs if d.get('source') == 'press_releases')}")
    print(f"  Google News    : {sum(1 for d in all_docs if d.get('source') == 'google_news')}")

    if len(all_docs) < N_TOPICS:
        print(f"⚠️  Pas assez de documents ({len(all_docs)}) pour {N_TOPICS} topics — réduction")
        n_topics = max(2, len(all_docs) // 2)
    else:
        n_topics = N_TOPICS

    texts = [_build_text(d) for d in all_docs]

    vectorizer = CountVectorizer(
        max_features=300,
        stop_words=list(sklearn.feature_extraction.text.ENGLISH_STOP_WORDS) + NEWS_STOP_WORDS,
        ngram_range=(1, 2),
        min_df=1,
    )
    doc_term_matrix = vectorizer.fit_transform(texts)
    feature_names = vectorizer.get_feature_names_out().tolist()

    lda = LatentDirichletAllocation(
        n_components=n_topics,
        random_state=42,
        max_iter=20,
        learning_method="batch",
    )
    doc_topic_matrix = lda.fit_transform(doc_term_matrix)

    # Topics
    topics_out = []
    for tid in range(n_topics):
        keywords = _top_keywords(lda, feature_names, tid)
        label = _generate_label(keywords, "press releases and news")
        topics_out.append({
            "topic_id": tid,
            "label": label,
            "keywords": keywords,
        })

    # Docs avec topic dominant
    docs_out = []
    for i, doc in enumerate(all_docs):
        topic_scores = doc_topic_matrix[i].tolist()
        dominant_topic = int(np.argmax(topic_scores))
        confidence = round(float(np.max(topic_scores)), 3)
        docs_out.append({
            "id": doc.get("id"),
            "source": doc.get("source"),
            "title": doc.get("title"),
            "date": doc.get("date"),
            "dominant_topic": dominant_topic,
            "dominant_label": topics_out[dominant_topic]["label"],
            "confidence": confidence,
        })

    result = {
        "n_topics": n_topics,
        "total_docs": len(all_docs),
        "sources": {
            "press_releases": sum(1 for d in all_docs if d.get("source") == "press_releases"),
            "google_news": sum(1 for d in all_docs if d.get("source") == "google_news"),
        },
        "topics": topics_out,
        "docs": docs_out,
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"✅ Topic modeling done — {len(all_docs)} docs → {n_topics} topics")
    for t in topics_out:
        print(f"  Topic {t['topic_id']} — {t['label']}: {', '.join(t['keywords'][:5])}")

    return result


if __name__ == "__main__":
    run()
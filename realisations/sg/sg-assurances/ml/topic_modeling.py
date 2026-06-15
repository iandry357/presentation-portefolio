"""
Topic Modeling — SG Assurances
LDA sur articles de veille BigQuery + labeling LiteLLM (Mistral/Gemini fallback)
"""

import json
import logging
import os

import numpy as np
import sklearn.feature_extraction.text
import litellm
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation

from bq_client import get_news

logger = logging.getLogger(__name__)

N_TOPICS     = 5
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results", "topic_modeling.json")

# ─────────────────────────────────────────
# Stopwords — finance / assurance / bruit RSS
# ─────────────────────────────────────────
NEWS_STOP_WORDS = [
    # Entités SG
    "société", "générale", "assurances", "sg", "assurance",
    # Bruit générique
    "company", "said", "year", "new", "also", "says", "according",
    "would", "could", "one", "two", "three", "million", "billion",
    "percent", "including", "based", "used", "using",
    # Bruit RSS
    "depuis", "titre", "source", "résumé", "font", "color", "href",
    "lire", "suite", "voir", "plus", "aujourd", "hui",
    "texte", "intégral", "article", "complet",
    # Stopwords français
    "le", "la", "les", "de", "du", "des", "en", "et", "un", "une",
    "il", "elle", "ils", "elles", "ce", "se", "sa", "son", "ses",
    "que", "qui", "au", "aux", "par", "sur", "pour", "dans", "est",
    "avec", "tout", "tous", "plus", "pas", "mais", "ou", "donc",
    "ne", "qu", "ni", "je", "tu", "nous", "on", "y", "été",
    "faire", "leur", "leurs", "sont", "cette", "cet", "ces",
    "après", "avant", "être", "très", "aussi", "même", "comme",
    "quand", "alors", "ainsi", "entre", "sous", "vers", "sans",
    "selon", "face", "dont", "car", "dès", "lors", "vos", "votre",
    "nos", "vous", "notre",
    # Bruit finance/juridique générique
    "banque", "groupe", "résultats", "trimestre", "rapport",
    "bourse", "euros", "marché", "cours", "action", "actions",
    "conseil", "stratégie", "information", "investissement",
    "finance", "financier", "financière",
    # Bruit médias
    "bfm", "rmc", "tv", "fr", "reuters", "bloomberg",
    # Bruit dates
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    "2023", "2024", "2025", "2026",
    # Bruit anglais
    "the", "and", "for", "with", "this", "that", "are", "has",
    "have", "its", "from", "will", "been", "were",
]


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────
def _build_text(doc: dict) -> str:
    title   = doc.get("title") or ""
    content = doc.get("content") or ""
    return f"{title} {content}".strip()


def _is_html(text: str) -> bool:
    return "<a href=" in text or "<font" in text


def _top_keywords(lda_model, feature_names: list, topic_id: int, n: int = 10) -> list:
    topic       = lda_model.components_[topic_id]
    top_indices = topic.argsort()[::-1][:n]
    return [feature_names[i] for i in top_indices]


def _generate_label(keywords: list) -> str:
    prompt = (
        f"Tu analyses des sujets liés au secteur bancaire, financier et à l'assurance, "
        f"en lien avec la Société Générale. "
        f"Voici les mots-clés dominants d'un topic : {', '.join(keywords[:10])}. "
        f"Génère un label thématique court (3-4 mots max) en français qui décrit au mieux "
        f"le thème. Réponds uniquement avec le label, rien d'autre."
    )
    for model, key_env in [
        ("mistral/mistral-small-latest", "MISTRAL_API_KEY"),
        ("gemini/gemini-1.5-flash",      "GEMINI_API_KEY"),
    ]:
        api_key = os.getenv(key_env, "")
        if not api_key:
            continue
        try:
            response = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                api_key=api_key,
                max_tokens=20,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"[topic] {model} failed : {e} — trying next")
    return "Unknown Topic"


# ─────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────
def run() -> dict:
    news = get_news()

    all_docs = []
    skipped  = 0
    for doc in news:
        text = _build_text(doc)
        if not text or _is_html(text) or len(text) < 100:
            skipped += 1
            continue
        all_docs.append(doc)

    print(f"[topic] {len(all_docs)} docs exploitables ({skipped} skipped)")

    if len(all_docs) < N_TOPICS:
        n_topics = max(2, len(all_docs) // 2)
        print(f"[topic] Réduction topics → {n_topics}")
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
    feature_names   = vectorizer.get_feature_names_out().tolist()

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
        label    = _generate_label(keywords)
        topics_out.append({
            "topic_id": tid,
            "label":    label,
            "keywords": keywords,
        })

    # Docs avec topic dominant
    docs_out = []
    for i, doc in enumerate(all_docs):
        topic_scores    = doc_topic_matrix[i].tolist()
        dominant_topic  = int(np.argmax(topic_scores))
        confidence      = round(float(np.max(topic_scores)), 3)
        docs_out.append({
            "id":             doc.get("id"),
            "source":         doc.get("source"),
            "title":          doc.get("title"),
            "date":           doc.get("date"),
            "url":            doc.get("metadata", {}).get("url", ""),
            "dominant_topic": dominant_topic,
            "dominant_label": topics_out[dominant_topic]["label"],
            "confidence":     confidence,
        })

    result = {
        "n_topics":   n_topics,
        "total_docs": len(all_docs),
        "topics":     topics_out,
        "docs":       docs_out,
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"[topic] Done — {len(all_docs)} docs → {n_topics} topics")
    for t in topics_out:
        print(f"  Topic {t['topic_id']} — {t['label']} : {', '.join(t['keywords'][:5])}")

    return result


if __name__ == "__main__":
    run()
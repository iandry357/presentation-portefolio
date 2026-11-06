"""
Topic Modeling — SQLI
LDA sur articles de veille BigQuery + labeling LiteLLM (Mistral/Gemini fallback)
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta

import numpy as np
import sklearn.feature_extraction.text
import litellm
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation

from bq_client import get_news

logger = logging.getLogger(__name__)

N_TOPICS_BY_LANG = {"fr": 4, "en": 3}   # un LDA par langue : évite les topics mixtes
MAX_AGE_DAYS = None  # fenêtre de récence en jours ; None pour tout garder
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results", "topic_modeling.json")

# ─────────────────────────────────────────
# Stopwords — entités SQLI / bruit RSS
# ─────────────────────────────────────────
NEWS_STOP_WORDS = [
    # Entités SQLI
    "sqli", "group", "groupe", "digital", "digitale", "agence",
    # Bruit RSS observé
    "suitedetails", "recrute", "euronext", "2027",
    "publié", "nov", "philippe", "05", "11", "10", "12",
    "transformation", "numériques", "services", "france", "paris", "marché",
    "tendances", "partenaires", "affaires", "ans", "chiffre", "faut", "nouvelles",
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


EN_HINTS = {"the", "and", "of", "to", "in", "for", "with", "is", "are", "that", "this", "on", "by", "as", "at"}
FR_HINTS = {"le", "la", "les", "de", "des", "du", "et", "un", "une", "pour", "dans", "que", "qui", "est", "sur", "au", "aux", "avec"}


def _detect_lang(text: str) -> str:
    words = re.findall(r"[a-zàâçéèêëîïôûùüÿœ']+", text.lower())[:300]
    en = sum(w in EN_HINTS for w in words)
    fr = sum(w in FR_HINTS for w in words)
    return "en" if en > fr else "fr"


def _top_keywords(lda_model, feature_names: list, topic_id: int, n: int = 10) -> list:
    topic       = lda_model.components_[topic_id]
    top_indices = topic.argsort()[::-1][:n]
    return [feature_names[i] for i in top_indices]


def _ask_llm(prompt: str, max_tokens: int):
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
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip().strip('"')
        except Exception as e:
            logger.warning(f"[topic] {model} failed : {e} — trying next")
    return None


def _generate_label(keywords: list, titles: list, used_labels: list) -> str:
    prompt = (
        f"Tu nommes un topic extrait d'articles de presse et de pages web sur la société SQLI. "
        f"Mots-clés dominants : {', '.join(keywords[:10])}.\n"
        f"Titres d'articles représentatifs :\n"
        + "\n".join(f"- {t}" for t in titles)
        + "\n\n"
        f"Génère un label précis de 3 à 5 mots, en français, qui décrit le sujet concret "
        f"traité par ces articles (par exemple une activité, un pays, un client, un événement). "
        f"Mots interdits : transformation, digital, digitale, numérique, services, SQLI. "
    )
    if used_labels:
        prompt += (
            f"Labels déjà utilisés pour d'autres topics, à ne pas répéter ni paraphraser : "
            f"{', '.join(used_labels)}. "
        )
    prompt += "Réponds uniquement avec le label, rien d'autre."
    return _ask_llm(prompt, max_tokens=30) or "Unknown Topic"


def _generate_summary(label: str, titles: list) -> str:
    prompt = (
        f"Voici des titres d'articles et de pages web sur la société SQLI, regroupés sous le thème « {label} » :\n"
        + "\n".join(f"- {t}" for t in titles)
        + "\n\n"
        f"Rédige en français un résumé de 2 phrases (50 mots maximum) qui explique ce que couvre ce groupe : "
        f"les faits concrets, les lieux, les clients ou les événements qui reviennent. "
        f"Appuie-toi uniquement sur ces titres, sans rien inventer. "
        f"Réponds uniquement avec le résumé."
    )
    return _ask_llm(prompt, max_tokens=150) or ""


# ─────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────
def run() -> dict:
    news = get_news()

    cutoff = (datetime.utcnow() - timedelta(days=MAX_AGE_DAYS)).date() if MAX_AGE_DAYS else None

    all_docs = []
    skipped  = 0
    for doc in news:
        text = _build_text(doc)
        if not text or _is_html(text) or len(text) < 100:
            skipped += 1
            continue
        if cutoff and doc.get("date") and doc["date"] < cutoff:
            skipped += 1
            continue
        if doc.get("metadata", {}).get("chunk_index", 0) != 0:
            skipped += 1
            continue
        all_docs.append(doc)

    print(f"[topic] {len(all_docs)} docs exploitables ({skipped} skipped)")

    # Un LDA par langue : les mots anglais et français ne cooccurrent jamais,
    # un modèle unique produirait des topics mixtes
    docs_by_lang = {}
    for d in all_docs:
        docs_by_lang.setdefault(_detect_lang(_build_text(d)), []).append(d)
    print("[topic] " + ", ".join(f"{lang}: {len(ds)}" for lang, ds in docs_by_lang.items()))

    stop_words = list(sklearn.feature_extraction.text.ENGLISH_STOP_WORDS) + NEWS_STOP_WORDS

    topics_out  = []
    docs_out    = []
    used_labels = []
    for lang, lang_docs in docs_by_lang.items():
        n_topics = min(N_TOPICS_BY_LANG.get(lang, 3), len(lang_docs) // 3)
        if n_topics < 2:
            print(f"[topic] {lang}: {len(lang_docs)} docs, trop peu pour un topic modeling — ignoré")
            continue

        texts = [_build_text(d) for d in lang_docs]

        vectorizer = CountVectorizer(
            max_features=300,
            stop_words=stop_words,
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

        # Topics (identifiants continus d'une langue à l'autre)
        offset = len(topics_out)
        for tid in range(n_topics):
            keywords = _top_keywords(lda, feature_names, tid)
            top_idx  = doc_topic_matrix[:, tid].argsort()[::-1][:5]
            titles   = [lang_docs[i].get("title", "") for i in top_idx]
            label    = _generate_label(keywords, titles, used_labels)
            used_labels.append(label)
            summary_idx = doc_topic_matrix[:, tid].argsort()[::-1][:10]
            summary     = _generate_summary(label, [lang_docs[i].get("title", "") for i in summary_idx])
            topics_out.append({
                "topic_id": offset + tid,
                "label":    label,
                "keywords": keywords,
                "lang":     lang,
                "summary":  summary,
            })

        # Docs avec topic dominant
        for i, doc in enumerate(lang_docs):
            topic_scores   = doc_topic_matrix[i].tolist()
            dominant_topic = offset + int(np.argmax(topic_scores))
            confidence     = round(float(np.max(topic_scores)), 3)
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
        "n_topics":   len(topics_out),
        "total_docs": len(docs_out),
        "topics":     topics_out,
        "docs":       docs_out,
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"[topic] Done — {len(docs_out)} docs → {len(topics_out)} topics")
    for t in topics_out:
        print(f"  Topic {t['topic_id']} — {t['label']} : {', '.join(t['keywords'][:5])}")

    return result


if __name__ == "__main__":
    run()

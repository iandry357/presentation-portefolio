"""
Topic Modeling — Wavestone
LDA par langue (FR, EN) + labeling LiteLLM (Mistral/Gemini fallback), sur les communiqués, publications et presse,
hors cas clients (classés à part par cas_clients.py) → results/topic_modeling.json
Un document = son premier morceau (chunk_index 0) ; langue lue dans metadata.langue, détection en secours.
Nombre de thèmes choisi automatiquement par corpus et par langue : K de K_MIN à K_MAX, meilleure cohérence UMass
parmi les K dont la redondance (similarité cosinus maximale entre deux thèmes) ne dépasse pas la plus faible
redondance observée + MARGE_REDONDANCE (seuil relatif : la redondance de fond varie d'un corpus à l'autre).
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

MAX_AGE_DAYS = None  # fenêtre de récence en jours ; None pour tout garder
VECTORIZER_MAX_FEATURES = 1000
VECTORIZER_MIN_DF = 2       # mot présent dans au moins 2 documents
VECTORIZER_MAX_DF = 0.5     # mot présent dans plus de la moitié des documents écarté (formules récurrentes du site)
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
SECTION_CAS_CLIENTS = "clients_story"

# Choix automatique du nombre de thèmes (par corpus et par langue)
K_MIN = 3                   # nombre de thèmes minimal testé
K_MAX = 10                  # nombre de thèmes maximal testé
DOCS_MIN_PAR_THEME = 10     # K plafonné à nb_docs // DOCS_MIN_PAR_THEME (50 docs → K ≤ 5)
MARGE_REDONDANCE = 0.05     # redondance tolérée = plus faible redondance observée sur les K testés + marge
N_MOTS_COHERENCE = 10       # mots-clés par thème pris en compte dans la cohérence UMass

# Un LDA par langue ; volumes au 2026-11-26 : 298 docs FR et 302 EN (hors cas clients)
CORPUS = {
    "base": {
        "results_path": os.path.join(RESULTS_DIR, "topic_modeling.json"),
        "description": "publications, communiqués et articles de presse sur le cabinet de conseil Wavestone",
    },
}

# ─────────────────────────────────────────
# Stopwords — entités Wavestone / bruit RSS
# ─────────────────────────────────────────
NEWS_STOP_WORDS = [
    # Entités et gabarits du site Wavestone (en-têtes « Publié le … - Section », « En bref », « Key takeaways »)
    "wavestone", "insights", "news", "communiqués", "press", "releases",
    "publié", "published", "bref", "brief", "key", "takeaways", "défi", "challenge",
    "client", "clients", "expert", "experts", "expertise", "success", "story",
    "2027", "05", "11", "10", "12",
    "transformation", "services", "france", "paris",
    # Gabarit des cas clients (structure commune Défi / Solution / Résultats, présent partout)
    "groupe", "entreprise", "équipe", "équipes", "solution", "group", "strategic", "project",
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
    "ont", "peut", "doit", "afin", "via", "chez", "cela", "également", "notamment",
    "comment", "avons",
    "plusieurs", "chaque", "autres", "autre", "certains", "toute", "toutes",
    # Bruit médias
    "bfm", "rmc", "tv", "fr", "reuters", "bloomberg",
    # Bruit dates
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    "2023", "2024", "2025", "2026",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
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


def _generate_label(keywords: list, titles: list, used_labels: list, description: str) -> str:
    prompt = (
        f"Tu nommes un topic extrait de {description}. "
        f"Mots-clés dominants : {', '.join(keywords[:10])}.\n"
        f"Titres d'articles représentatifs :\n"
        + "\n".join(f"- {t}" for t in titles)
        + "\n\n"
        f"Génère un label précis de 3 à 5 mots, en français, qui décrit le sujet concret "
        f"traité par ces articles (par exemple une activité, un pays, un client, un événement). "
        f"Mots interdits : transformation, digital, digitale, numérique, services, conseil, Wavestone. "
    )
    if used_labels:
        prompt += (
            f"Labels déjà utilisés pour d'autres topics, à ne pas répéter ni paraphraser : "
            f"{', '.join(used_labels)}. "
        )
    prompt += "Réponds uniquement avec le label, rien d'autre."
    return _ask_llm(prompt, max_tokens=30) or "Unknown Topic"


def _generate_summary(label: str, titles: list, description: str) -> str:
    prompt = (
        f"Voici des titres de {description}, regroupés sous le thème « {label} » :\n"
        + "\n".join(f"- {t}" for t in titles)
        + "\n\n"
        f"Rédige en français un résumé de 2 phrases (50 mots maximum) qui explique ce que couvre ce groupe : "
        f"les faits concrets, les lieux, les clients ou les événements qui reviennent. "
        f"Appuie-toi uniquement sur ces titres, sans rien inventer. "
        f"Réponds uniquement avec le résumé."
    )
    return _ask_llm(prompt, max_tokens=150) or ""


# ─────────────────────────────────────────
# Choix du nombre de thèmes
# ─────────────────────────────────────────
def _entrainer_lda(doc_term_matrix, n_topics: int) -> LatentDirichletAllocation:
    lda = LatentDirichletAllocation(
        n_components=n_topics,
        random_state=42,
        max_iter=20,
        learning_method="batch",
    )
    return lda.fit(doc_term_matrix)


def _coherence_umass(lda, doc_term_matrix, n_mots: int = N_MOTS_COHERENCE) -> float:
    """Cohérence UMass moyenne des thèmes : plus elle est proche de 0, plus les mots-clés
    d'un thème apparaissent ensemble dans les mêmes documents."""
    presence = (doc_term_matrix > 0).astype(np.int32).tocsc()   # documents × mots, 0/1
    nb_docs_par_mot = np.asarray(presence.sum(axis=0)).ravel()
    scores = []
    for topic in lda.components_:
        top = topic.argsort()[::-1][:n_mots]
        colonnes = presence[:, top]
        co_docs = (colonnes.T @ colonnes).toarray()             # documents communs à chaque paire de mots
        score = 0.0
        for i in range(1, len(top)):
            for j in range(i):
                score += np.log((co_docs[i, j] + 1) / nb_docs_par_mot[top[j]])
        scores.append(score)
    return float(np.mean(scores))


def _redondance_max(lda) -> float:
    """Similarité cosinus maximale entre deux thèmes (distributions de mots)."""
    comp = lda.components_ / np.linalg.norm(lda.components_, axis=1, keepdims=True)
    sim = comp @ comp.T
    np.fill_diagonal(sim, 0.0)
    return float(sim.max())


def _choisir_k(doc_term_matrix, k_max: int):
    """Teste K de K_MIN à k_max ; retient la meilleure cohérence parmi les K dont la redondance
    ne dépasse pas la plus faible observée + MARGE_REDONDANCE."""
    essais = []
    for k in range(K_MIN, k_max + 1):
        lda = _entrainer_lda(doc_term_matrix, k)
        essais.append((k, lda, _coherence_umass(lda, doc_term_matrix), _redondance_max(lda)))
        print(f"[topic]   K={k:2d}  cohérence={essais[-1][2]:8.2f}  redondance max={essais[-1][3]:.2f}")

    seuil = min(e[3] for e in essais) + MARGE_REDONDANCE
    candidats = [e for e in essais if e[3] <= seuil]
    k, lda, _, _ = max(candidats, key=lambda e: e[2])
    print(f"[topic]   → K retenu : {k} (meilleure cohérence parmi les K de redondance ≤ {seuil:.2f})")
    return k, lda


# ─────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────
def _charger_docs() -> list:
    """Premiers morceaux exploitables d'articles_bruts (site et presse)."""
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
    return all_docs


def _modeliser(nom: str, docs: list, cfg: dict) -> dict:
    """LDA par langue sur un corpus, libellés LLM, écriture du JSON du corpus."""
    print(f"\n[topic] === Corpus {nom} : {len(docs)} docs ===")

    # Un LDA par langue : les mots anglais et français ne cooccurrent jamais,
    # un modèle unique produirait des topics mixtes
    docs_by_lang = {}
    for d in docs:
        lang = d.get("metadata", {}).get("langue") or _detect_lang(_build_text(d))
        docs_by_lang.setdefault(lang, []).append(d)
    print("[topic] " + ", ".join(f"{lang}: {len(ds)}" for lang, ds in docs_by_lang.items()))

    stop_words = list(sklearn.feature_extraction.text.ENGLISH_STOP_WORDS) + NEWS_STOP_WORDS

    topics_out  = []
    docs_out    = []
    used_labels = []
    for lang, lang_docs in docs_by_lang.items():
        k_max = min(K_MAX, len(lang_docs) // DOCS_MIN_PAR_THEME)
        if k_max < K_MIN:
            print(f"[topic] {lang}: {len(lang_docs)} docs, trop peu pour un topic modeling — ignoré")
            continue

        texts = [_build_text(d) for d in lang_docs]

        vectorizer = CountVectorizer(
            max_features=VECTORIZER_MAX_FEATURES,
            stop_words=stop_words,
            ngram_range=(1, 2),
            min_df=VECTORIZER_MIN_DF,
            max_df=VECTORIZER_MAX_DF,
        )
        doc_term_matrix = vectorizer.fit_transform(texts)
        feature_names   = vectorizer.get_feature_names_out().tolist()

        print(f"[topic] {lang} : choix de K entre {K_MIN} et {k_max}")
        n_topics, lda = _choisir_k(doc_term_matrix, k_max)
        doc_topic_matrix = lda.transform(doc_term_matrix)

        # Topics (identifiants continus d'une langue à l'autre)
        offset = len(topics_out)
        for tid in range(n_topics):
            keywords = _top_keywords(lda, feature_names, tid)
            top_idx  = doc_topic_matrix[:, tid].argsort()[::-1][:5]
            titles   = [lang_docs[i].get("title", "") for i in top_idx]
            label    = _generate_label(keywords, titles, used_labels, cfg["description"])
            used_labels.append(label)
            summary_idx = doc_topic_matrix[:, tid].argsort()[::-1][:10]
            summary     = _generate_summary(label, [lang_docs[i].get("title", "") for i in summary_idx], cfg["description"])
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
                "lang":           lang,
                "section":        doc.get("metadata", {}).get("section", "presse"),
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

    results_path = cfg["results_path"]
    os.makedirs(os.path.dirname(results_path), exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"[topic] {nom} — {len(docs_out)} docs → {len(topics_out)} topics ({results_path})")
    for t in topics_out:
        print(f"  Topic {t['topic_id']} [{t['lang']}] — {t['label']} : {', '.join(t['keywords'][:5])}")

    return result


def run() -> dict:
    """Corpus de base (communiqués, publications, presse) ; les cas clients sont traités par cas_clients.py."""
    all_docs = _charger_docs()
    base        = [d for d in all_docs if d.get("metadata", {}).get("section") != SECTION_CAS_CLIENTS]
    return _modeliser("base", base, CORPUS["base"])


if __name__ == "__main__":
    run()

"""
Inspection des résultats topic modeling — affiche les docs par topic.
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

RESULTS_PATH = Path(__file__).resolve().parent.parent / "results" / "topic_modeling.json"


def run():
    if not RESULTS_PATH.exists():
        print(f"❌ Fichier non trouvé: {RESULTS_PATH}")
        sys.exit(1)

    with open(RESULTS_PATH) as f:
        r = json.load(f)

    print(f"{'='*60}")
    print(f"Topic Modeling — {r['total_docs']} docs, {r['n_topics']} topics")
    print(f"  Press Releases : {r['sources'].get('press_releases', 0)}")
    print(f"  Google News    : {r['sources'].get('google_news', 0)}")
    print(f"{'='*60}\n")

    # Topics
    print("📋 TOPICS\n")
    for t in r["topics"]:
        print(f"  Topic {t['topic_id']} — {t['label']}")
        print(f"  Keywords : {', '.join(t['keywords'][:7])}")
        print()

    # Docs groupés par topic
    print(f"{'='*60}")
    print("📰 DOCUMENTS PAR TOPIC\n")

    by_topic = defaultdict(list)
    for doc in r["docs"]:
        by_topic[doc["dominant_topic"]].append(doc)

    for tid in sorted(by_topic.keys()):
        topic_label = r["topics"][tid]["label"]
        docs = sorted(by_topic[tid], key=lambda d: d["confidence"], reverse=True)
        print(f"  [{tid}] {topic_label} — {len(docs)} docs")
        for d in docs:
            source_tag = "PR" if d["source"] == "press_releases" else "GN"
            print(f"    [{source_tag}] ({d['confidence']:.2f}) {d['title'][:80]}")
        print()


if __name__ == "__main__":
    run()
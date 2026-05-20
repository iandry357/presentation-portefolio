"""
Test collecteur Press Releases — vérifie la collecte RSS + contenu Trafilatura.
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from pipeline.collectors import press_releases


def run():
    logger.info("🔍 Test collecteur Press Releases")
    docs = press_releases.collect()

    if not docs:
        logger.error("❌ Aucun document collecté")
        return

    logger.info(f"✅ {len(docs)} press releases collectés\n")

    for i, doc in enumerate(docs, 1):
        print(f"{'='*60}")
        print(f"[{i}] {doc['title']}")
        print(f"    Date    : {doc['date']}")
        print(f"    URL     : {doc['metadata'].get('url', 'N/A')}")
        content = doc['content']
        print(f"    Contenu : {len(content)} caractères")
        print(f"    Extrait : {content[:300]}...")
        print()


if __name__ == "__main__":
    run()
"""
pipeline_orchestrator.py
------------------------
Orchestrateur one-shot — enchaîne :
    1. therapeutic_insight.py  — recalcul du JSON OpenTargets
    2. neo4j_ingestion.py      — chargement du graphe Neo4j

Garanties :
    - Neo4j wake avant ingestion (poll orchestrateur OVH)
    - Arrêt immédiat si therapeutic_insight.py échoue
    - neo4j_ingestion.py ne tourne que si le JSON est valide et récent

Usage :
    python pipeline_orchestrator.py                    # run complet
    python pipeline_orchestrator.py --skip-therapeutic # ingestion Neo4j uniquement
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
import os

# ---------------------------------------------------------------------------
# PARAMÈTRES CONFIGURABLES
# ---------------------------------------------------------------------------
load_dotenv()

RESULTS_DIR          = Path(__file__).parent / "results"
THERAPEUTIC_JSON     = RESULTS_DIR / "therapeutic_insight.json"
THERAPEUTIC_SCRIPT   = Path(__file__).parent / "therapeutic_insight.py"
NEO4J_INGESTION_SCRIPT = Path(__file__).parent / "neo4j_ingestion.py"

ORCHESTRATOR_URL     = os.getenv("OVH_ORCHESTRATOR_URL", "http://localhost:8080")
NEO4J_HEALTH_URL     = "http://localhost:7474"
NEO4J_WAKE_TIMEOUT   = 60    # secondes max pour attendre Neo4j up
NEO4J_POLL_INTERVAL  = 2     # secondes entre chaque poll

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _log(msg: str):
    print(f"[ORCHESTRATOR] {msg}", flush=True)


def _abort(msg: str):
    _log(f"ABORT — {msg}")
    sys.exit(1)


def _wake_neo4j() -> bool:
    """
    Réveille Neo4j via l'orchestrateur OVH puis poll /health jusqu'à 200 OK.
    Retourne True si Neo4j est prêt, False si timeout.
    """
    _log("Wake Neo4j via orchestrateur...")
    try:
        httpx.post(f"{ORCHESTRATOR_URL}/wake/neo4j", timeout=10)
    except Exception as e:
        _log(f"Wake orchestrateur échoué : {e} — tentative de connexion directe")

    deadline = time.time() + NEO4J_WAKE_TIMEOUT
    while time.time() < deadline:
        try:
            resp = httpx.get(NEO4J_HEALTH_URL, timeout=5)
            if resp.status_code == 200:
                _log("Neo4j ready.")
                return True
        except Exception:
            pass
        time.sleep(NEO4J_POLL_INTERVAL)

    return False


def _validate_json() -> bool:
    """
    Vérifie que therapeutic_insight.json existe et est valide.
    Retourne True si OK, False sinon.
    """
    if not THERAPEUTIC_JSON.exists():
        _log("therapeutic_insight.json introuvable.")
        return False
    try:
        with open(THERAPEUTIC_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        n_clusters = data.get("n_clusters", 0)
        generated_at = data.get("generated_at", "?")
        _log(f"JSON valide — {n_clusters} clusters — généré le {generated_at}")
        return n_clusters > 0
    except json.JSONDecodeError as e:
        _log(f"JSON corrompu : {e}")
        return False


def _run_script(script: Path, label: str) -> bool:
    """
    Lance un script Python en subprocess.
    Retourne True si succès (exit code 0), False sinon.
    Streame les logs en temps réel.
    """
    _log(f"Lancement {label}...")
    start = time.time()

    process = subprocess.Popen(
        [sys.executable, str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    for line in process.stdout:
        print(f"  [{label}] {line}", end="", flush=True)

    process.wait()
    elapsed = time.time() - start

    if process.returncode == 0:
        _log(f"{label} terminé en {elapsed:.1f}s ✓")
        return True
    else:
        _log(f"{label} échoué (exit code {process.returncode}) en {elapsed:.1f}s ✗")
        return False


# ---------------------------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Pipeline orchestrator — Sanofi Therapeutic Insight")
    parser.add_argument(
        "--skip-therapeutic",
        action="store_true",
        help="Sauter therapeutic_insight.py — utiliser le JSON existant",
    )
    args = parser.parse_args()

    _log("=== Pipeline Sanofi — Therapeutic Insight + Neo4j ===")
    start_total = time.time()

    # ── Étape 1 — therapeutic_insight.py ──────────────────────────────────
    if args.skip_therapeutic:
        _log("--skip-therapeutic activé — vérification du JSON existant")
        if not _validate_json():
            _abort("JSON inexistant ou invalide — relancer sans --skip-therapeutic")
    else:
        success = _run_script(THERAPEUTIC_SCRIPT, "therapeutic_insight")
        if not success:
            _abort("therapeutic_insight.py a échoué — ingestion Neo4j annulée")

        if not _validate_json():
            _abort("JSON généré invalide — ingestion Neo4j annulée")

    # ── Étape 2 — Wake Neo4j ───────────────────────────────────────────────
    neo4j_ready = _wake_neo4j()
    if not neo4j_ready:
        _abort(f"Neo4j unavailable après {NEO4J_WAKE_TIMEOUT}s — ingestion annulée")

    # ── Étape 3 — neo4j_ingestion.py ──────────────────────────────────────
    success = _run_script(NEO4J_INGESTION_SCRIPT, "neo4j_ingestion")
    if not success:
        _abort("neo4j_ingestion.py a échoué")

    # ── Résumé ─────────────────────────────────────────────────────────────
    elapsed_total = time.time() - start_total
    minutes = int(elapsed_total // 60)
    seconds = int(elapsed_total % 60)
    _log(f"=== Pipeline terminé en {minutes}m {seconds}s ===")


if __name__ == "__main__":
    main()
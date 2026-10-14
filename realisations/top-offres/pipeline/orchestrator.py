"""
Orchestrateur du worker top-offres.
Modes (argparse) : cibles-proposer, cibles-valider.
Les modes run et marts sont ajoutés à l'étape E9.
"""
import argparse
import json
import logging
import sys
from pathlib import Path

from agents import cibles_agent
from pipeline import config
from pipeline.collectors import profil_collector
from pipeline.loaders import bigquery_loader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _ecrire_export(version: dict) -> Path:
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    chemin = config.RESULTS_DIR / f"cibles_{version['version_cibles']}.json"
    export = {**version, "statut": "proposee"}
    chemin.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
    return chemin


def cibles_proposer() -> None:
    logger.info("ÉTAPE 1 — Lecture du profil (PostgreSQL, lecture seule)")
    experiences = profil_collector.collecter_experiences()
    if not experiences:
        logger.error("Aucune expérience en base — arrêt")
        sys.exit(1)
    texte_profil = profil_collector.construire_texte_profil(experiences)

    logger.info("ÉTAPE 2 — Dérivation des cibles (%s)", config.MODELE_CIBLES)
    cibles = cibles_agent.deriver_cibles(texte_profil)
    version = cibles_agent.construire_version(cibles)

    logger.info("ÉTAPE 3 — Écriture BigQuery (statut proposee)")
    nb = bigquery_loader.ecrire_cibles_proposees(version)
    logger.info("%d cibles écrites, version %s", nb, version["version_cibles"])

    logger.info("ÉTAPE 4 — Export pour relecture")
    chemin = _ecrire_export(version)
    logger.info("Export : %s", chemin)


def cibles_valider(fichier: str) -> None:
    logger.info("ÉTAPE 1 — Lecture et contrôle du fichier %s", fichier)
    try:
        export = json.loads(Path(fichier).read_text(encoding="utf-8"))
        version_cibles = export["version_cibles"]
        cibles_agent.valider_cibles(export["cibles"])
        identifiants = [c["cible_id"] for c in export["cibles"]]
        if not all(identifiants) or len(set(identifiants)) != len(identifiants):
            raise ValueError("cible_id manquant ou en double")
    except (OSError, KeyError, ValueError) as e:
        logger.error("Fichier invalide : %s", e)
        sys.exit(1)

    logger.info("ÉTAPE 2 — Contrôle du statut en base (version %s)", version_cibles)
    statut = bigquery_loader.statut_version(version_cibles)
    if statut not in ("proposee", "validee"):
        logger.error("Version %s introuvable ou archivée (statut : %s) — arrêt", version_cibles, statut)
        sys.exit(1)

    logger.info("ÉTAPE 3 — Validation")
    if statut == "proposee":
        bigquery_loader.supprimer_lignes_proposees(version_cibles)
        bigquery_loader.charger_cibles_validees(export)
    else:
        logger.info("Version déjà validée : seul l'archivage des autres versions est refait")
    bigquery_loader.archiver_autres_versions(version_cibles)
    logger.info("Version %s validée", version_cibles)


def main() -> None:
    parser = argparse.ArgumentParser(description="Orchestrateur top-offres")
    modes = parser.add_subparsers(dest="mode", required=True)
    modes.add_parser(
        "cibles-proposer",
        help="Dérive des cibles depuis le profil (statut proposee) et exporte un fichier",
    )
    valider = modes.add_parser("cibles-valider", help="Passe une version relue au statut validee")
    valider.add_argument("--fichier", required=True, help="Export relu, par ex. results/cibles_<version>.json")
    args = parser.parse_args()

    if args.mode == "cibles-proposer":
        cibles_proposer()
    elif args.mode == "cibles-valider":
        cibles_valider(args.fichier)


if __name__ == "__main__":
    main()

"""
Orchestrateur du worker top-offres.
Modes (argparse) : cibles-proposer, cibles-valider, run, marts.
"""
import argparse
import json
import logging
import sys
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agents import cibles_agent, scoring_agent
from pipeline import config
from pipeline.collectors import offres_collector, profil_collector
from pipeline.loaders import bigquery_loader
from pipeline.transformation import entreprises as entreprises_transformation
from pipeline.transformation import dbt_runner
from pipeline.transformation import similarite

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logging.getLogger("primp").setLevel(logging.WARNING)  # moteur de recherche web : une ligne INFO par requête
logger = logging.getLogger(__name__)


def _generer_run_id() -> str:
    return f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"


def etape_scoring(run_id: str, limite: int | None = None) -> dict:
    """Étape 3 du run : entreprises, embeddings, scoring LLM, écriture du staging.
    `limite` sert aux essais : le staging ne correspond alors plus à int_offres_a_scorer."""
    if not config.MODELE_SCORING:
        logger.error("MODELE_SCORING non défini (variable d'environnement) — arrêt")
        sys.exit(1)

    logger.info("ÉTAPE 3.1 — Cibles validées et profil")
    cibles = bigquery_loader.lire_cibles_validees()
    if not cibles:
        logger.error("Aucune version de cibles validée — arrêt")
        sys.exit(1)
    version_cibles = cibles[0]["version_cibles"]
    version_scoring = scoring_agent.calculer_version_scoring(version_cibles)
    resume_profil = profil_collector.construire_resume_profil(profil_collector.collecter_experiences())

    logger.info("ÉTAPE 3.2 — Offres à scorer")
    offres = offres_collector.lire_offres_a_scorer()
    if limite:
        offres = offres[:limite]
    if not offres:
        logger.warning("Aucune offre à scorer")
        bigquery_loader.remplacer_staging([])
        return {"offres": 0}

    logger.info("ÉTAPE 3.3 — Entreprises")
    entreprises_transformation.enrichir_entreprises(offres_collector.regrouper_entreprises(offres))
    cles = list({o["entreprise_normalise"] for o in offres if o["entreprise_normalise"]})
    refs = bigquery_loader.lire_entreprises_ref(cles)

    logger.info("ÉTAPE 3.4 — Embeddings (titres ↔ cibles)")
    similarite.reveiller_service()
    vecteurs_cibles = similarite.embedder([c["description"] for c in cibles])
    vecteurs_titres = similarite.embedder([o["titre"] for o in offres])
    indices, similarites = similarite.meilleure_cible(vecteurs_titres, vecteurs_cibles)
    for offre, indice, similarite_max in zip(offres, indices, similarites):
        ref = refs.get(offre["entreprise_normalise"], {})
        offre.update(
            type_annonceur=ref.get("type_annonceur"),
            naf_libelle=ref.get("naf_libelle"),
            cible_proche=cibles[indice]["cible_id"],
            cible_proche_intitule=cibles[indice]["intitule"],
            similarite=float(similarite_max),
        )

    logger.info("ÉTAPE 3.5 — Scoring LLM (%s)", config.MODELE_SCORING)
    resultats = scoring_agent.scorer_offres(offres, {"resume_profil": resume_profil, "cibles": cibles})

    logger.info("ÉTAPE 3.6 — Écriture du staging")
    score_le = datetime.now(timezone.utc).isoformat()
    lignes = [
        {
            **r,
            "run_id": run_id,
            "modele": config.MODELE_SCORING,
            "version_prompt": scoring_agent.FICHIER_PROMPT,
            "version_cibles": version_cibles,
            "version_scoring": version_scoring,
            "score_le": score_le,
        }
        for r in resultats
    ]
    bigquery_loader.remplacer_staging(lignes)
    bilan = {"run_id": run_id, "offres": len(lignes), **Counter(r["statut_llm"] for r in resultats)}
    logger.info("Scoring terminé : %s", bilan)
    return bilan


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


FORMAT_FENETRE = "%Y-%m-%d %H:%M:%S"  # fenêtre UTC transmise à dbt


def _formater_fenetre(date: datetime) -> str:
    return date.astimezone(timezone.utc).strftime(FORMAT_FENETRE)


def _parser_date(texte: str) -> datetime:
    """Date ou date-heure ISO ; UTC si le fuseau n'est pas précisé."""
    date = datetime.fromisoformat(texte)
    return date if date.tzinfo else date.replace(tzinfo=timezone.utc)


def _resoudre_fenetre(args: argparse.Namespace, maintenant: datetime) -> tuple[datetime, datetime]:
    """Fenêtre [début, fin[ sur date_collecte : --entre, --depuis, --derniers-jours, sinon --auto (défaut)."""
    if args.entre:
        return _parser_date(args.entre[0]), _parser_date(args.entre[1])
    if args.depuis:
        return _parser_date(args.depuis), maintenant
    if args.derniers_jours is not None:
        return maintenant - timedelta(days=args.derniers_jours), maintenant
    dernier = bigquery_loader.lire_dernier_run_succes()
    if dernier:
        return dernier["fenetre_fin"], maintenant
    return maintenant - timedelta(days=config.DERNIERS_JOURS_DEFAUT), maintenant


def _calculer_versions() -> tuple[str, str]:
    """(version_cibles, version_scoring) ; arrêt si MODELE_SCORING ou les cibles validées manquent."""
    if not config.MODELE_SCORING:
        logger.error("MODELE_SCORING non défini (variable d'environnement) — arrêt")
        sys.exit(1)
    cibles = bigquery_loader.lire_cibles_validees()
    if not cibles:
        logger.error("Aucune version de cibles validée — arrêt")
        sys.exit(1)
    version_cibles = cibles[0]["version_cibles"]
    return version_cibles, scoring_agent.calculer_version_scoring(version_cibles)


def _fin_etape(numero: int, debut: datetime) -> datetime:
    """Journalise la durée de l'étape et retourne l'instant de départ de la suivante."""
    maintenant = datetime.now(timezone.utc)
    logger.info("ÉTAPE %d terminée en %.0f s", numero, (maintenant - debut).total_seconds())
    return maintenant


def lancer_run(args: argparse.Namespace) -> None:
    run_id = _generer_run_id()
    debut = datetime.now(timezone.utc)
    fenetre_debut, fenetre_fin = _resoudre_fenetre(args, debut)
    if fenetre_debut >= fenetre_fin:
        logger.error("Fenêtre invalide : %s >= %s — arrêt", fenetre_debut, fenetre_fin)
        sys.exit(1)
    version_cibles, version_scoring = _calculer_versions()
    variables = dbt_runner.variables_dbt(
        _formater_fenetre(fenetre_debut), _formater_fenetre(fenetre_fin), run_id, version_scoring, args.forcer
    )
    logger.info(
        "Run %s — fenêtre [%s, %s[ — version_scoring %s%s",
        run_id, variables["fenetre_debut"], variables["fenetre_fin"], version_scoring,
        " — forcer" if args.forcer else "",
    )

    ligne = {
        "run_id": run_id,
        "mode": "run",
        "fenetre_debut": fenetre_debut.isoformat(),
        "fenetre_fin": fenetre_fin.isoformat(),
        "forcer": args.forcer,
        "appliquer_exclusions": config.APPLIQUER_EXCLUSIONS,
        "modele_scoring": config.MODELE_SCORING,
        "version_prompt": scoring_agent.FICHIER_PROMPT,
        "version_cibles": version_cibles,
        "version_scoring": version_scoring,
        "verdict": "erreur",
        "message": None,
        "debut": debut.isoformat(),
    }
    top = datetime.now(timezone.utc)
    try:
        logger.info("ÉTAPE 1 — Entreprises exclues")
        logger.info("%d entreprises exclues synchronisées", entreprises_transformation.synchroniser_exclues())
        top = _fin_etape(1, top)

        logger.info("ÉTAPE 2 — dbt amont")
        if not dbt_runner.preparer_amont(variables):
            raise RuntimeError("dbt amont en échec")
        ligne.update(bigquery_loader.lire_comptes_fenetre())
        top = _fin_etape(2, top)

        logger.info("ÉTAPE 3 — Scoring")
        bilan = etape_scoring(run_id)
        ligne["nb_scorees_ok"] = bilan.get("ok", 0)
        ligne["nb_erreurs"] = bilan.get("json_invalide", 0) + bilan.get("erreur", 0)
        top = _fin_etape(3, top)

        logger.info("ÉTAPE 4 — Porte de contrôle")
        porte_ok = dbt_runner.verifier_porte(variables)
        top = _fin_etape(4, top)
        if not porte_ok:
            ligne.update(verdict="echec_tests", message="Porte de contrôle en échec : aucune fusion")
        else:
            logger.info("ÉTAPE 5 — Fusion et marts")
            if not dbt_runner.construire_marts(variables):
                raise RuntimeError("dbt marts en échec")
            _fin_etape(5, top)
            ligne["verdict"] = "succes"
    except Exception as e:
        logger.exception("Run en erreur")
        ligne.update(verdict="erreur", message=str(e)[:500])
    finally:
        fin = datetime.now(timezone.utc)
        ligne.update(fin=fin.isoformat(), duree_s=round((fin - debut).total_seconds(), 1))
        logger.info("ÉTAPE 6 — Journal : verdict %s en %.0f s", ligne["verdict"], ligne["duree_s"])
        bigquery_loader.ecrire_run(ligne)
    if ligne["verdict"] != "succes":
        sys.exit(1)


def reconstruire_marts() -> None:
    """Relance fusion et marts avec les variables du dernier run en succès (après un changement de seuils)."""
    dernier = bigquery_loader.lire_dernier_run_succes()
    if not dernier:
        logger.error("Aucun run en succès : lancer d'abord le mode run — arrêt")
        sys.exit(1)
    variables = dbt_runner.variables_dbt(
        _formater_fenetre(dernier["fenetre_debut"]),
        _formater_fenetre(dernier["fenetre_fin"]),
        dernier["run_id"],
        dernier["version_scoring"],
        False,
    )
    logger.info("Marts — variables du run %s", dernier["run_id"])
    if not dbt_runner.construire_marts(variables):
        logger.error("dbt marts en échec")
        sys.exit(1)
    logger.info("Marts reconstruits")


def main() -> None:
    parser = argparse.ArgumentParser(description="Orchestrateur top-offres")
    modes = parser.add_subparsers(dest="mode", required=True)
    modes.add_parser(
        "cibles-proposer",
        help="Dérive des cibles depuis le profil (statut proposee) et exporte un fichier",
    )
    valider = modes.add_parser("cibles-valider", help="Passe une version relue au statut validee")
    valider.add_argument("--fichier", required=True, help="Export relu, par ex. results/cibles_<version>.json")
    run = modes.add_parser("run", help="Pipeline complet : exclues, dbt, scoring, porte de contrôle, marts, journal")
    fenetre = run.add_mutually_exclusive_group()
    fenetre.add_argument("--auto", action="store_true", help="Depuis la fin du dernier run en succès (défaut)")
    fenetre.add_argument("--depuis", metavar="DATE", help="De DATE (UTC) à maintenant")
    fenetre.add_argument("--entre", nargs=2, metavar=("DEBUT", "FIN"), help="Entre deux dates (UTC)")
    fenetre.add_argument("--derniers-jours", type=int, metavar="N", help="Les N derniers jours")
    run.add_argument("--forcer", action="store_true", help="Re-score les offres déjà scorées avec la version courante")
    modes.add_parser("marts", help="Relance fusion et marts avec les variables du dernier run en succès")
    args = parser.parse_args()

    if args.mode == "cibles-proposer":
        cibles_proposer()
    elif args.mode == "cibles-valider":
        cibles_valider(args.fichier)
    elif args.mode == "run":
        lancer_run(args)
    elif args.mode == "marts":
        reconstruire_marts()


if __name__ == "__main__":
    main()

import json
import logging
import subprocess

from pipeline import config

logger = logging.getLogger(__name__)

MODELE_AMONT = "int_offres_a_scorer"
MODELES_MARTS = ["offres_scores", "mart_top_du_jour", "mart_stats"]
TESTS_PORTE = [
    "source:top_offres",
    "porte_alertes_valides",
    "porte_score_valide",
    "porte_nb_lignes_staging",
    "porte_taux_erreur_llm",
    "porte_version_et_run",
]


def variables_dbt(fenetre_debut: str, fenetre_fin: str, run_id: str, version_scoring: str, forcer: bool) -> dict:
    """Variables passées à dbt (fenêtres en UTC, « AAAA-MM-JJ hh:mm:ss »)."""
    return {
        "fenetre_debut": fenetre_debut,
        "fenetre_fin": fenetre_fin,
        "run_id": run_id,
        "version_scoring": version_scoring,
        "forcer": forcer,
        "seuil_haut": config.SEUIL_HAUT,
        "seuil_bas": config.SEUIL_BAS,
        "appliquer_exclusions": config.APPLIQUER_EXCLUSIONS,
        "taux_erreur_llm_max": config.TAUX_ERREUR_LLM_MAX,
    }


def executer(commande: str, variables: dict, selection: list[str] | None = None, options: list[str] | None = None) -> int:
    """Lance `dbt <commande>` dans le projet dbt/ ; journalise la sortie ; retourne le code de retour (0 = succès)."""
    args = ["dbt", commande, "--project-dir", str(config.DBT_DIR), "--profiles-dir", str(config.DBT_DIR)]
    if selection:
        args += ["--select", *selection]
    args += options or []
    args += ["--vars", json.dumps(variables)]
    logger.info("dbt %s %s", commande, " ".join(selection or []))
    processus = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    for ligne in processus.stdout:
        logger.info("dbt | %s", ligne.rstrip())
    code = processus.wait()
    if code != 0:
        logger.error("dbt %s : code de retour %d", commande, code)
    return code


def preparer_amont(variables: dict) -> bool:
    """Seeds puis build de int_offres_a_scorer (modèle et ses propres tests : « cautious » exclut les tests de la
    porte, qui lisent aussi le staging)."""
    return (
        executer("seed", variables) == 0
        and executer("build", variables, [MODELE_AMONT], ["--indirect-selection", "cautious"]) == 0
    )


def verifier_porte(variables: dict) -> bool:
    """Porte de contrôle sur le staging : vrai si tous les tests passent."""
    return executer("test", variables, TESTS_PORTE) == 0


def construire_marts(variables: dict) -> bool:
    """Fusion dans offres_scores et marts, puis tests des marts."""
    return executer("run", variables, MODELES_MARTS) == 0 and executer("test", variables, MODELES_MARTS) == 0

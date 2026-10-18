"""
Test de rappel (cahier 8.4) : les offres postulées ou enregistrées (job_offers) passent dans la même chaîne que
le run (entreprises, embeddings, scoring LLM), sans écriture dans le staging ni dans offres_scores.
Usage : docker-compose run --rm pipeline scripts/test_rappel.py [--modele NOM]
Sorties : results/test_rappel_<modele>_<horodatage>.json et une ligne dans runs (mode test-rappel).
"""
import argparse
import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone

from agents import scoring_agent
from pipeline import config, orchestrator
from pipeline.collectors import historique_collector, profil_collector
from pipeline.loaders import bigquery_loader

PAS_SEUIL = 5  # pas de la courbe rappel = f(seuil)
RAPPEL_CIBLE = 0.90  # cible indicative (D6) : sert à proposer un seuil
NOTES = [
    "Les positifs sont des offres déjà retenues par l'utilisateur : le rappel mesure la capacité à les retrouver, "
    "pas la précision.",
    "Les filtres durs (stage, alternance, hors Île-de-France) ne sont pas appliqués dans ce test.",
    "Seules les offres au statut_llm ok comptent dans les rappels.",
]

logger = logging.getLogger(__name__)


def _part(scores: list[int], seuil: int) -> float | None:
    """Part des scores supérieurs ou égaux au seuil ; None si la liste est vide."""
    return round(sum(s >= seuil for s in scores) / len(scores), 3) if scores else None


def _pct(valeur: float | None) -> str:
    return "n/a" if valeur is None else f"{valeur:.1%}"


def evaluer_rappel(positifs: list[dict], resultats: list[dict]) -> dict:
    """Rappel des positifs aux seuils courants et par seuil. `resultats` suit l'ordre de `positifs`
    (sortie de scorer_offres). Seules les offres au statut_llm ok comptent ; les autres sont dénombrées à part."""
    lignes = [{**p, **r} for p, r in zip(positifs, resultats)]
    notees = [ligne for ligne in lignes if ligne["statut_llm"] == "ok"]
    seuils = list(range(0, 101, PAS_SEUIL))

    groupes = {"tous": notees}
    for statut in historique_collector.STATUTS_POSITIFS:
        groupes[statut] = [ligne for ligne in notees if ligne["statut"] == statut]
    rappels = {}
    for nom, groupe in groupes.items():
        scores = [ligne["score"] for ligne in groupe]
        rappels[nom] = {
            "nb": len(scores),
            "a_lire": _part(scores, config.SEUIL_HAUT),
            "a_lire_ou_zone_grise": _part(scores, config.SEUIL_BAS),
            "par_seuil": {str(s): _part(scores, s) for s in seuils},
        }

    seuil_cible = next(
        (s for s in reversed(seuils) if (rappels["tous"]["par_seuil"][str(s)] or 0) >= RAPPEL_CIBLE), None
    )
    par_source = {}
    for source in sorted({ligne["source"] for ligne in notees}):
        scores = [ligne["score"] for ligne in notees if ligne["source"] == source]
        par_source[source] = {"nb": len(scores), "a_lire_ou_zone_grise": _part(scores, config.SEUIL_BAS)}

    champs = ("id_unique", "statut", "source", "titre", "entreprise_nom", "score", "categorie", "raison",
              "cible_proche", "similarite")
    rates = [
        {champ: ligne[champ] for champ in champs}
        for ligne in sorted(notees, key=lambda ligne: ligne["score"])
        if ligne["score"] < config.SEUIL_BAS
    ]
    return {
        "seuils": {"haut": config.SEUIL_HAUT, "bas": config.SEUIL_BAS},
        "statuts_llm": dict(Counter(ligne["statut_llm"] for ligne in lignes)),
        "rappels": rappels,
        "seuil_pour_rappel_cible": {"rappel_cible": RAPPEL_CIBLE, "seuil": seuil_cible},
        "par_source": par_source,
        "rates": rates,
    }


def _message(rapport: dict) -> str:
    r = rapport["rappels"]
    return (
        f"Rappel a_lire+zone_grise {_pct(r['tous']['a_lire_ou_zone_grise'])} "
        f"(postule {_pct(r['postule']['a_lire_ou_zone_grise'])}, enregistre {_pct(r['enregistre']['a_lire_ou_zone_grise'])}) ; "
        f"seuil pour {RAPPEL_CIBLE:.0%} : {rapport['seuil_pour_rappel_cible']['seuil']}"
    )


def _ecrire_rapport(rapport: dict, horodatage: datetime) -> str:
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    modele = config.MODELE_SCORING.replace(":", "-").replace("/", "-")
    chemin = config.RESULTS_DIR / f"test_rappel_{modele}_{horodatage:%Y%m%d-%H%M%S}.json"
    chemin.write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(chemin)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test de rappel sur les offres postulées / enregistrées")
    parser.add_argument("--modele", help="Modèle de scoring (défaut : variable MODELE_SCORING)")
    args = parser.parse_args()
    if args.modele:
        config.MODELE_SCORING = args.modele
    if not config.MODELE_SCORING:
        logger.error("Aucun modèle : définir MODELE_SCORING ou passer --modele — arrêt")
        sys.exit(1)

    cibles = bigquery_loader.lire_cibles_validees()
    if not cibles:
        logger.error("Aucune version de cibles validée — arrêt")
        sys.exit(1)
    version_cibles = cibles[0]["version_cibles"]
    version_scoring = scoring_agent.calculer_version_scoring(version_cibles)

    debut = datetime.now(timezone.utc)
    run_id = f"rappel-{debut:%Y%m%d-%H%M%S}"
    ligne = {
        "run_id": run_id,
        "mode": "test-rappel",
        "forcer": False,
        "appliquer_exclusions": config.APPLIQUER_EXCLUSIONS,
        "modele_scoring": config.MODELE_SCORING,
        "version_prompt": scoring_agent.FICHIER_PROMPT,
        "version_cibles": version_cibles,
        "version_scoring": version_scoring,
        "verdict": "erreur",
        "message": None,
        "debut": debut.isoformat(),
    }
    try:
        logger.info("Test de rappel %s — modèle %s", run_id, config.MODELE_SCORING)
        resume_profil = profil_collector.construire_resume_profil(profil_collector.collecter_experiences())
        positifs = historique_collector.lire_positifs()
        resultats = orchestrator.enrichir_et_scorer(positifs, cibles, resume_profil)

        rapport = evaluer_rappel(positifs, resultats)
        nb_ok = rapport["statuts_llm"].get("ok", 0)
        ligne.update(nb_lues=len(positifs), nb_scorees_ok=nb_ok, nb_erreurs=len(positifs) - nb_ok)
        ligne.update(verdict="succes", message=_message(rapport))
        chemin = _ecrire_rapport(
            {
                "run_id": run_id,
                "date": debut.isoformat(),
                "modele": config.MODELE_SCORING,
                "version_prompt": scoring_agent.FICHIER_PROMPT,
                "version_cibles": version_cibles,
                "notes": NOTES,
                **rapport,
            },
            debut,
        )
        logger.info("%s", ligne["message"])
        logger.info("%d positifs sous le seuil bas — rapport : %s", len(rapport["rates"]), chemin)
    except Exception as e:
        logger.exception("Test de rappel en erreur")
        ligne.update(verdict="erreur", message=str(e)[:500])
    finally:
        fin = datetime.now(timezone.utc)
        ligne.update(fin=fin.isoformat(), duree_s=round((fin - debut).total_seconds(), 1))
        logger.info("Durée totale : %.0f s (%.1f min)", ligne["duree_s"], ligne["duree_s"] / 60)        
        bigquery_loader.ecrire_run(ligne)
    if ligne["verdict"] != "succes":
        sys.exit(1)


if __name__ == "__main__":
    main()

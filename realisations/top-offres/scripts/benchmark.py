"""
Benchmark des modèles de scoring (cahier 8.4) : même jeu d'offres pour chaque modèle.
Jeu : positifs (job_offers) + échantillon d'offres récentes (int_offres_a_scorer) + copies exactes d'offres de
l'échantillon (stabilité). Rien n'est écrit dans runs, offres_scores ni le staging (seul le cache entreprises_ref).
Usage : docker-compose run --rm pipeline scripts/benchmark.py [--modeles M1 M2 ...] [--taille-lot N]
        [--echantillon N] [--derniers-jours N] [--sans-amont] [--graine N]
Sorties : results/benchmark_<horodatage>.json (réécrit après chaque modèle) et un tableau comparatif dans les logs.
"""
import argparse
import json
import logging
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from agents import llm_client, scoring_agent
from pipeline import config, orchestrator
from pipeline.collectors import historique_collector, offres_collector, profil_collector
from pipeline.loaders import bigquery_loader
from pipeline.transformation import dbt_runner
from scripts.test_rappel import evaluer_rappel

MODELES = ["qwen3.5:4b", "gemma4:e4b", "phi4-mini", "mistral:latest", "mistral-nemo:latest"]
TAILLE_ECHANTILLON = 200
GRAINE = 42
DERNIERS_JOURS = 30
NB_TITRES_STABILITE = 10  # offres de l'échantillon copiées pour mesurer la stabilité
NB_COPIES_STABILITE = 5  # copies exactes de chacune
NOTES = [
    "Même jeu, même ordre et mêmes entrées enrichies pour tous les modèles ; le tirage dépend de la graine.",
    "Le rappel se mesure sur des offres déjà retenues par l'utilisateur ; la charge de lecture (part de "
    "l'échantillon en a_lire ou zone_grise) évite de préférer un modèle qui note tout haut.",
    "Stabilité : copies exactes d'une même offre réparties dans des lots différents ; un écart de score entre copies "
    "est du bruit du modèle.",
    "Les filtres durs ne sont pas appliqués aux positifs.",
]

logger = logging.getLogger(__name__)


def _part(scores: list[int], seuil: int) -> float | None:
    return round(sum(s >= seuil for s in scores) / len(scores), 3) if scores else None


def _pct(valeur: float | None) -> str:
    return "n/a" if valeur is None else f"{valeur:.1%}"


def construire_jeu(positifs: list[dict], echantillon: list[dict], graine: int) -> list[dict]:
    """Positifs + échantillon mélangés, plus NB_COPIES_STABILITE copies exactes de NB_TITRES_STABILITE offres de
    l'échantillon. La c-ième copie d'une offre est placée dans la c-ième tranche du jeu : les copies tombent dans
    des lots différents. L'ordre est reproductible (graine) et identique pour tous les modèles."""
    rng = random.Random(graine)
    sources = rng.sample(echantillon, min(NB_TITRES_STABILITE, len(echantillon)))
    base = [{**p, "origine": "positif"} for p in positifs] + [{**o, "origine": "echantillon"} for o in echantillon]
    rng.shuffle(base)
    placees = [(j / len(base), offre) for j, offre in enumerate(base)]
    for c in range(NB_COPIES_STABILITE):
        for i, source in enumerate(sources):
            copie = {**source, "id_unique": f"stab-{i}-{c}", "origine": "stabilite", "groupe_stabilite": i}
            placees.append(((c + rng.random()) / NB_COPIES_STABILITE, copie))
    return [offre for _, offre in sorted(placees, key=lambda element: element[0])]


def mesurer_stabilite(lignes: list[dict]) -> dict:
    """Écarts de score entre les copies exactes d'une même offre."""
    groupes = defaultdict(list)
    for ligne in lignes:
        if ligne["origine"] == "stabilite" and ligne["statut_llm"] == "ok":
            groupes[ligne["groupe_stabilite"]].append(ligne)
    ecarts, details, bascules, categories = [], [], 0, 0
    for groupe in groupes.values():
        scores = [ligne["score"] for ligne in groupe]
        if len(scores) < 2:
            continue
        ecarts.append(max(scores) - min(scores))
        if min(scores) < config.SEUIL_BAS <= max(scores):
            bascules += 1  # copies de part et d'autre du seuil bas : la décision changerait
        if len({ligne["categorie"] for ligne in groupe}) > 1:
            categories += 1
        details.append({"titre": groupe[0]["titre"], "scores": sorted(scores)})
    return {
        "nb_groupes": len(ecarts),
        "ecart_moyen": round(statistics.mean(ecarts), 1) if ecarts else None,
        "ecart_max": max(ecarts) if ecarts else None,
        "groupes_bascule_seuil_bas": bascules,
        "groupes_categories_differentes": categories,
        "details": details,
    }


def evaluer_modele(modele: str, jeu: list[dict], contexte: dict) -> dict:
    config.MODELE_SCORING = modele
    logger.info("=== Modèle %s (lots de %d) ===", modele, config.TAILLE_LOT_LLM)
    try:
        scoring_agent.scorer_offres(jeu[:1], contexte)  # chargement du modèle dans Ollama, hors mesure
        nb_lots = -(-len(jeu) // config.TAILLE_LOT_LLM)
        debut = time.monotonic()
        resultats = scoring_agent.scorer_offres(jeu, contexte)
        duree = time.monotonic() - debut
    except Exception as e:
        logger.exception("Modèle %s en erreur", modele)
        return {"modele": modele, "erreur": str(e)[:300]}

    lignes = [{**offre, **resultat} for offre, resultat in zip(jeu, resultats)]
    positifs = [(o, r) for o, r in zip(jeu, resultats) if o["origine"] == "positif"]
    rapport = evaluer_rappel([o for o, _ in positifs], [r for _, r in positifs])
    echantillon = [l["score"] for l in lignes if l["origine"] == "echantillon" and l["statut_llm"] == "ok"]
    statuts = Counter(ligne["statut_llm"] for ligne in lignes)
    return {
        "modele": modele,
        "taille_lot": config.TAILLE_LOT_LLM,
        "duree_s": round(duree, 1),
        "temps_moyen_lot_s": round(duree / nb_lots, 1),
        "statuts_llm": dict(statuts),
        "part_json_invalide": round(statuts.get("json_invalide", 0) / len(lignes), 3),
        "part_erreur": round(statuts.get("erreur", 0) / len(lignes), 3),
        "rappel": {
            nom: {
                "nb": r["nb"],
                "a_lire": r["a_lire"],
                "a_lire_ou_zone_grise": r["a_lire_ou_zone_grise"],
                "par_seuil": r["par_seuil"],
            }
            for nom, r in rapport["rappels"].items()
        },
        "seuil_pour_rappel_cible": rapport["seuil_pour_rappel_cible"],
        "charge_lecture": {
            "nb": len(echantillon),
            "a_lire": _part(echantillon, config.SEUIL_HAUT),
            "a_lire_ou_zone_grise": _part(echantillon, config.SEUIL_BAS),
            "par_seuil": {seuil: _part(echantillon, int(seuil)) for seuil in rapport["rappels"]["tous"]["par_seuil"]},
        },
        "stabilite": mesurer_stabilite(lignes),
    }


def _afficher_tableau(modeles: list[dict]) -> None:
    logger.info(
        "%-24s %8s %8s %8s %8s %8s %6s %6s %6s %5s %5s",
        "modèle", "rappel", "postule", "enreg.", "charge", "json_inv", "erreur", "s/lot", "écart", "bascu", "cat≠",
    )
    for m in modeles:
        if "erreur" in m:
            logger.info("%-24s en erreur : %s", m["modele"], m["erreur"])
            continue
        r, s = m["rappel"], m["stabilite"]
        logger.info(
            "%-24s %8s %8s %8s %8s %8s %6s %6.1f %6s %5d %5d",
            m["modele"],
            _pct(r["tous"]["a_lire_ou_zone_grise"]),
            _pct(r["postule"]["a_lire_ou_zone_grise"]),
            _pct(r["enregistre"]["a_lire_ou_zone_grise"]),
            _pct(m["charge_lecture"]["a_lire_ou_zone_grise"]),
            _pct(m["part_json_invalide"]),
            _pct(m["part_erreur"]),
            m["temps_moyen_lot_s"],
            s["ecart_moyen"],
            s["groupes_bascule_seuil_bas"],
            s["groupes_categories_differentes"],
        )


def _ecrire_rapport(rapport: dict, chemin) -> None:
    chemin.write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark des modèles de scoring")
    parser.add_argument("--modeles", nargs="+", default=MODELES, help="Modèles Ollama à comparer")
    parser.add_argument("--taille-lot", type=int, help="Offres par appel LLM (défaut : TAILLE_LOT_LLM)")
    parser.add_argument("--echantillon", type=int, default=TAILLE_ECHANTILLON, help="Taille de l'échantillon récent")
    parser.add_argument("--derniers-jours", type=int, default=DERNIERS_JOURS, help="Fenêtre de l'échantillon")
    parser.add_argument("--sans-amont", action="store_true", help="Ne pas reconstruire int_offres_a_scorer")
    parser.add_argument("--graine", type=int, default=GRAINE, help="Graine du tirage et du mélange")
    args = parser.parse_args()
    debut_total = time.monotonic()    
    if args.taille_lot:
        config.TAILLE_LOT_LLM = args.taille_lot

    installes = llm_client.lister_modeles()
    modeles = []
    for modele in args.modeles:
        if modele in installes or f"{modele}:latest" in installes:
            modeles.append(modele)
        else:
            logger.warning("Modèle %s absent d'Ollama — ignoré", modele)
    if not modeles:
        logger.error("Aucun modèle disponible — arrêt")
        sys.exit(1)

    cibles = bigquery_loader.lire_cibles_validees()
    if not cibles:
        logger.error("Aucune version de cibles validée — arrêt")
        sys.exit(1)
    version_cibles = cibles[0]["version_cibles"]
    resume_profil = profil_collector.construire_resume_profil(profil_collector.collecter_experiences())

    if not args.sans_amont:
        fin = datetime.now(timezone.utc)
        debut = fin - timedelta(days=args.derniers_jours)
        logger.warning("Reconstruction de int_offres_a_scorer sur %d jours (table écrasée)", args.derniers_jours)
        variables = dbt_runner.variables_dbt(
            debut.strftime(orchestrator.FORMAT_FENETRE), fin.strftime(orchestrator.FORMAT_FENETRE),
            "benchmark", "benchmark", False,
        )
        if not dbt_runner.preparer_amont(variables):
            logger.error("dbt amont en échec — arrêt")
            sys.exit(1)

    echantillon = offres_collector.lire_echantillon(args.echantillon, args.graine)
    if not echantillon:
        logger.error("Échantillon vide : int_offres_a_scorer ne contient aucune offre éligible — arrêt")
        sys.exit(1)
    positifs = historique_collector.lire_positifs()
    jeu = construire_jeu(positifs, echantillon, args.graine)
    logger.info("Jeu : %d offres (%d positifs, %d échantillon)", len(jeu), len(positifs), len(echantillon))
    orchestrator.enrichir_offres(jeu, cibles)

    horodatage = datetime.now(timezone.utc)
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    chemin = config.RESULTS_DIR / f"benchmark_{horodatage:%Y%m%d-%H%M%S}.json"
    rapport = {
        "date": horodatage.isoformat(),
        "graine": args.graine,
        "derniers_jours": None if args.sans_amont else args.derniers_jours,
        "taille_lot": config.TAILLE_LOT_LLM,
        "version_prompt": scoring_agent.FICHIER_PROMPT,
        "version_cibles": version_cibles,
        "nb_positifs": len(positifs),
        "nb_echantillon": len(echantillon),
        "nb_stabilite": sum(1 for o in jeu if o["origine"] == "stabilite"),
        "notes": NOTES,
        "modeles": [],
    }
    contexte = {"resume_profil": resume_profil, "cibles": cibles}
    for modele in modeles:
        rapport["modeles"].append(evaluer_modele(modele, jeu, contexte))
        _ecrire_rapport(rapport, chemin)

    _afficher_tableau(rapport["modeles"])
    duree_total = time.monotonic() - debut_total
    logger.info("Durée totale : %.0f s (%.1f min)", duree_total, duree_total / 60)
    logger.info("Rapport : %s", chemin)


if __name__ == "__main__":
    main()

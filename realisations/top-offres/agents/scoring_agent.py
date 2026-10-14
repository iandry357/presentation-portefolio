import hashlib
import logging
import time

import requests

from agents import llm_client
from pipeline import config
from pipeline.validators import quality

logger = logging.getLogger(__name__)

FICHIER_PROMPT = "scoring_v1.txt"  # le nom du fichier sert de version de prompt
NUM_CTX = 8192
NB_LOTS_ERREUR_MAX = 3  # lots consécutifs en erreur d'appel avant d'abandonner le run
ALERTES_LLM = ("salaire_incoherent", "titre_ambigu", "seniorite_incertaine", "autre")

SCHEMA_SCORING = {
    "type": "object",
    "properties": {
        "offres": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "numero": {"type": "integer"},
                    "score": {"type": "integer"},
                    "categorie": {"type": "string", "enum": list(quality.CATEGORIES)},
                    "raison": {"type": "string"},
                    "alertes": {"type": "array", "items": {"type": "string", "enum": list(ALERTES_LLM)}},
                },
                "required": ["numero", "score", "categorie", "raison", "alertes"],
            },
        }
    },
    "required": ["offres"],
}


def calculer_version_scoring(version_cibles: str) -> str:
    """Empreinte de (modèle de scoring, version du prompt, version des cibles validées)."""
    contenu = f"{config.MODELE_SCORING}|{FICHIER_PROMPT}|{version_cibles}"
    return hashlib.sha256(contenu.encode("utf-8")).hexdigest()[:12]


def _formater_cibles(cibles: list[dict]) -> str:
    return "\n".join(f"- {c['intitule']} ({c['niveau']}) : {c['description']}" for c in cibles)


def _formater_offre(numero: int, offre: dict) -> str:
    champs = [
        f"titre : {offre['titre']}",
        f"entreprise : {offre.get('entreprise_nom') or 'inconnue'}",
        f"lieu : {offre.get('localisation_libelle') or 'inconnu'}",
        f"contrat : {offre.get('contrat') or 'inconnu'}",
        f"salaire : {offre.get('salaire_libelle') or 'non précisé'}",
        f"annonceur : {offre.get('type_annonceur') or 'inconnu'}",
        f"activité : {offre.get('naf_libelle') or 'inconnue'}",
        f"cible la plus proche : {offre['cible_proche_intitule']} (similarité {offre['similarite']:.2f})",
    ]
    return f"{numero}. " + " | ".join(champs)


def _construire_message(contexte: dict, lot: list[dict]) -> str:
    offres = "\n".join(_formater_offre(i, o) for i, o in enumerate(lot, start=1))
    return (
        f"PROFIL DU CANDIDAT\n{contexte['resume_profil']}\n\n"
        f"CIBLES DE POSTES\n{_formater_cibles(contexte['cibles'])}\n\n"
        f"OFFRES À ÉVALUER\n{offres}"
    )


def _evaluer(lot: list[dict], contexte: dict, systeme: str) -> dict[int, dict]:
    """Évalue un lot ; retourne {numéro: évaluation validée} pour les offres correctement traitées."""
    reponse = llm_client.generer_json(
        config.MODELE_SCORING,
        systeme,
        _construire_message(contexte, lot),
        SCHEMA_SCORING,
        thinking=config.THINKING_SCORING,
        num_ctx=NUM_CTX,
    )
    evaluations = {}
    for element in reponse.get("offres", []):
        numero = element.get("numero") if isinstance(element, dict) else None
        if not isinstance(numero, int) or not 1 <= numero <= len(lot) or numero in evaluations:
            continue
        try:
            evaluations[numero] = quality.valider_evaluation(element)
        except ValueError as e:
            logger.debug("Évaluation de l'offre %d invalide : %s", numero, e)
    return evaluations


def _tenter(lot: list[dict], contexte: dict, systeme: str) -> tuple[dict[int, dict], str | None]:
    """(évaluations, statut d'échec) ; le statut vaut 'json_invalide' ou 'erreur' si l'appel entier échoue."""
    try:
        return _evaluer(lot, contexte, systeme), None
    except llm_client.LLMJsonInvalide:
        return {}, "json_invalide"
    except (llm_client.LLMError, requests.RequestException) as e:
        logger.warning("Appel LLM en erreur : %s", e)
        return {}, "erreur"


def _resultat(offre: dict, evaluation: dict | None, statut: str) -> dict:
    alertes = list(evaluation["alertes"]) if evaluation else []
    if evaluation and offre.get("type_annonceur") == "intermediaire" and "intermediaire" not in alertes:
        alertes.append("intermediaire")  # ajoutée par le code, pas par le LLM
    return {
        "id_unique": offre["id_unique"],
        "cible_proche": offre["cible_proche"],
        "similarite": offre["similarite"],
        "score": evaluation["score"] if evaluation else None,
        "categorie": evaluation["categorie"] if evaluation else None,
        "raison": evaluation["raison"] if evaluation else None,
        "alertes": alertes,
        "statut_llm": statut,
    }


def scorer_offres(offres: list[dict], contexte: dict) -> list[dict]:
    """Score les offres par lots. Une offre absente ou invalide dans la réponse est retentée seule une fois.
    contexte : {"resume_profil": str, "cibles": list[dict]}."""
    systeme = (config.PROMPTS_DIR / FICHIER_PROMPT).read_text(encoding="utf-8")
    taille = config.TAILLE_LOT_LLM
    nb_lots = (len(offres) + taille - 1) // taille
    resultats = []
    lots_en_erreur_consecutifs = 0

    for numero_lot, debut in enumerate(range(0, len(offres), taille), start=1):
        lot = offres[debut:debut + taille]
        top = time.monotonic()
        evaluations, statut_echec = _tenter(lot, contexte, systeme)

        if statut_echec == "erreur":
            lots_en_erreur_consecutifs += 1
            if lots_en_erreur_consecutifs >= NB_LOTS_ERREUR_MAX:
                raise RuntimeError(f"{NB_LOTS_ERREUR_MAX} lots consécutifs en erreur d'appel : LLM indisponible ?")
            resultats.extend(_resultat(o, None, "erreur") for o in lot)
            continue
        lots_en_erreur_consecutifs = 0

        compte = {"ok": 0, "json_invalide": 0, "erreur": 0}
        for numero, offre in enumerate(lot, start=1):
            evaluation = evaluations.get(numero)
            statut = "ok"
            if evaluation is None:
                seule, statut_seule = _tenter([offre], contexte, systeme)
                evaluation = seule.get(1)
                statut = "ok" if evaluation else (statut_seule or "json_invalide")
            compte[statut] += 1
            resultats.append(_resultat(offre, evaluation, statut))
        logger.info(
            "Lot %d/%d : %d ok, %d json_invalide, %d erreur (%.1f s)",
            numero_lot, nb_lots, compte["ok"], compte["json_invalide"], compte["erreur"], time.monotonic() - top,
        )
    return resultats

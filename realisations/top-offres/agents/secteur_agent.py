import logging

from agents import llm_client
from pipeline import config

logger = logging.getLogger(__name__)

FICHIER_PROMPT = "secteur_v1.txt"  # le nom du fichier sert de version de prompt
CONFIANCES = ("faible", "moyenne", "haute")
CONFIANCES_CONCLUANTES = ("moyenne", "haute")
NB_TENTATIVES = 2
NUM_CTX = 4096
MAX_CHARS_EXTRAIT = 400
MAX_CHARS_SECTEUR = 100

SCHEMA_SECTEUR = {
    "type": "object",
    "properties": {
        "secteur": {"type": "string"},
        "confiance": {"type": "string", "enum": list(CONFIANCES)},
    },
    "required": ["secteur", "confiance"],
}


def _formater_extraits(extraits: list[dict]) -> str:
    return "\n\n".join(
        f"[{i}] {e['titre']}\n{e['extrait'][:MAX_CHARS_EXTRAIT]}" for i, e in enumerate(extraits, start=1)
    )


def est_concluant(resultat: dict) -> bool:
    """Un secteur est conclu s'il est renseigné avec une confiance moyenne ou haute."""
    return bool(resultat["secteur"]) and resultat["confiance"] in CONFIANCES_CONCLUANTES


def determiner_secteur(nom: str, extraits: list[dict]) -> dict:
    """{secteur, confiance} d'après les extraits web ; secteur None et confiance faible si rien d'exploitable.
    Les erreurs d'appel à Ollama (LLMError) ne sont pas interceptées : l'appelant décide."""
    inconnu = {"secteur": None, "confiance": "faible"}
    if not extraits:
        return inconnu
    systeme = (config.PROMPTS_DIR / FICHIER_PROMPT).read_text(encoding="utf-8")
    utilisateur = f"Entreprise : {nom}\n\nExtraits de recherche web :\n\n{_formater_extraits(extraits)}"
    for tentative in range(1, NB_TENTATIVES + 1):
        try:
            reponse = llm_client.generer_json(
                config.MODELE_SECTEUR, systeme, utilisateur, SCHEMA_SECTEUR, thinking=False, num_ctx=NUM_CTX
            )
        except llm_client.LLMJsonInvalide as e:
            logger.warning("Secteur '%s' : réponse invalide (tentative %d/%d) : %s", nom, tentative, NB_TENTATIVES, e)
            continue
        secteur = str(reponse.get("secteur") or "").strip()[:MAX_CHARS_SECTEUR]
        confiance = reponse.get("confiance")
        if not secteur or confiance not in CONFIANCES:
            return inconnu
        return {"secteur": secteur, "confiance": confiance}
    return inconnu

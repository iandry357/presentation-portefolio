import hashlib
import json
import logging
from datetime import datetime, timezone

from agents import llm_client
from pipeline import config

logger = logging.getLogger(__name__)

NB_CIBLES_MIN = 5
NB_CIBLES_MAX = 12
NIVEAUX = ("coeur", "adjacent")
NB_TENTATIVES = 2
FICHIER_PROMPT = "cibles_v1.txt"  # le nom du fichier sert de version de prompt
CHAMPS_TEXTE = ("intitule", "justification", "description")

SCHEMA_CIBLES = {
    "type": "object",
    "properties": {
        "cibles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "intitule": {"type": "string"},
                    "niveau": {"type": "string", "enum": list(NIVEAUX)},
                    "justification": {"type": "string"},
                    "variantes_titres": {"type": "array", "items": {"type": "string"}},
                    "description": {"type": "string"},
                },
                "required": ["intitule", "niveau", "justification", "variantes_titres", "description"],
            },
        }
    },
    "required": ["cibles"],
}


def valider_cibles(cibles: list[dict]) -> None:
    """Lève ValueError si la liste ne respecte pas le contrat (section 8.3 du cahier)."""
    if not NB_CIBLES_MIN <= len(cibles) <= NB_CIBLES_MAX:
        raise ValueError(f"{len(cibles)} cibles (attendu {NB_CIBLES_MIN} à {NB_CIBLES_MAX})")
    for i, cible in enumerate(cibles, start=1):
        for champ in CHAMPS_TEXTE:
            if not str(cible.get(champ, "")).strip():
                raise ValueError(f"Cible {i} : champ '{champ}' vide")
        if cible.get("niveau") not in NIVEAUX:
            raise ValueError(f"Cible {i} : niveau '{cible.get('niveau')}' invalide")
        variantes = cible.get("variantes_titres")
        if (
            not isinstance(variantes, list)
            or not variantes
            or not all(isinstance(v, str) and v.strip() for v in variantes)
        ):
            raise ValueError(f"Cible {i} : variantes_titres vide ou invalide")


def deriver_cibles(texte_profil: str) -> list[dict]:
    """Demande au LLM fort les cibles de postes ; une nouvelle tentative si la sortie est invalide."""
    systeme = (config.PROMPTS_DIR / FICHIER_PROMPT).read_text(encoding="utf-8")
    utilisateur = f"Profil professionnel :\n\n{texte_profil}"
    derniere_erreur = None
    for tentative in range(1, NB_TENTATIVES + 1):
        logger.info(
            "Dérivation des cibles, tentative %d/%d (modèle %s)",
            tentative, NB_TENTATIVES, config.MODELE_CIBLES,
        )
        try:
            reponse = llm_client.generer_json(
                config.MODELE_CIBLES, systeme, utilisateur, SCHEMA_CIBLES, thinking=False
            )
            cibles = reponse["cibles"]
            valider_cibles(cibles)
            return cibles
        except (llm_client.LLMError, KeyError, TypeError, ValueError) as e:
            derniere_erreur = e
            logger.warning("Tentative %d invalide : %s", tentative, e)
    raise RuntimeError(f"Dérivation des cibles impossible : {derniere_erreur}")


def construire_version(cibles: list[dict]) -> dict:
    """Attribue cible_id (c01, c02...) et calcule version_cibles (date-heure UTC + empreinte du contenu)."""
    cree_le = datetime.now(timezone.utc)
    contenu = json.dumps(cibles, ensure_ascii=False, sort_keys=True)
    empreinte = hashlib.sha256(contenu.encode("utf-8")).hexdigest()[:8]
    return {
        "version_cibles": f"{cree_le:%Y%m%d-%H%M}-{empreinte}",
        "modele": config.MODELE_CIBLES,
        "cree_le": cree_le.isoformat(),
        "cibles": [{**c, "cible_id": f"c{i:02d}"} for i, c in enumerate(cibles, start=1)],
    }

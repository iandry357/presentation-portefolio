"""Assistant bailleur (Immobilier) : recherche dans le référentiel, réponse du LLM, contrôle des citations.

Le LLM ne désigne une source que par son numéro d'extrait. Le serveur vérifie les numéros, les renumérote dans l'ordre
d'apparition et construit lui-même la liste des sources depuis les métadonnées : une référence inventée ne peut pas sortir.
Une réponse sans citation valide devient un refus.
"""
import asyncio
import logging
from datetime import date

import re

from app.core.llm_client import generate_with_fallback
from app.services.immobilier_referentiel_recherche import rechercher
from routers.immobilier.assistant_schemas import AssistantReponse, SourceCitee

logger = logging.getLogger(__name__)

K_EXTRAITS = 8
MODELES = ["gemini", "mistral-medium"]
MAX_TOKENS = 4000  # à ma connaissance, Gemini 2.5 compte sa réflexion dans cette limite
TEMPERATURE = 0.1
MARQUEUR_REFUS = "AUCUNE_SOURCE"
MESSAGE_REFUS = (
    "Je n'ai pas trouvé de source dans mon corpus pour répondre à cette question. Il couvre la décence énergétique et le "
    "calendrier de location des logements classés F et G, le gel des loyers, le déficit foncier, le micro-foncier, la "
    "location meublée (LMNP), les plus-values immobilières et les aides à la rénovation énergétique."
)

SYSTEM_PROMPT = (
    "Tu es l'assistant immobilier de la page Immobilier de ce portfolio. Tu aides toute personne concernée par un bien "
    "(professionnel de l'immobilier, vendeur, acheteur, bailleur) sur la performance énergétique des logements, la "
    "fiscalité immobilière et les aides à la rénovation, uniquement à partir d'extraits de textes officiels numérotés. "
    "Ne présume ni le rôle de la personne ni qu'elle loue son bien."
)


def _extrait(numero, e):
    m = e["metadata"]
    version = f", version du {m['date_version']}" if m.get("date_version") else ""
    return f"[{numero}] {m['reference']} ({m['type_texte']}, {m['statut']}{version})\n{e['document']}"


def _prompt(question, historique, extraits):
    blocs = "\n\n".join(_extrait(i, e) for i, e in enumerate(extraits, 1))
    echanges = ""
    if historique:
        lignes = "\n".join(f"{'Utilisateur' if m['role'] == 'user' else 'Assistant'} : {m['content']}" for m in historique)
        echanges = f"\nConversation précédente :\n{lignes}\n"
    return f"""Extraits :
{blocs}
{echanges}
Question : {question}

Règles :
- Réponds uniquement avec ce que disent les extraits : aucune connaissance extérieure, aucun chiffre ni date absent des extraits. Recopie fidèlement les dates, classes et montants ; ne déduis ni date de fin ni cas que l'extrait n'écrit pas.
- Quand un extrait fixe un « niveau de performance minimal » par une classe énergétique (A est la meilleure classe, G la moins bonne), les logements de cette classe ou d'une meilleure classe sont autorisés et seules les classes moins bonnes sont exclues. Une date « à compter du » ouvre une règle, elle ne ferme pas la précédente par une date inventée.
- Ne mélange pas les alinéas : une condition écrite dans un alinéa (I., II., 1°, a)) ne s'applique pas à la règle d'un autre alinéa. Attribue à chaque règle uniquement les conditions de son propre alinéa.
- Fais suivre chaque affirmation du numéro de l'extrait qui la fonde, entre crochets : [2], ou [1][3] pour plusieurs.
- Priorité des sources : le texte légal (loi, décret, code) d'abord ; le BOFiP pour l'application ; une loi de finances pour dater un changement. En cas de contradiction, donne la source la plus récente et dis-le.
- Si les extraits ne permettent pas de répondre, ou si la question sort du périmètre (décence énergétique, fiscalité locative, aides à la rénovation), réponds exactement : {MARQUEUR_REFUS}
- Si les extraits ne répondent qu'en partie, réponds à la partie couverte et dis clairement ce qui manque.
- Quand un extrait établit directement la règle demandée, donne d'abord la réponse nette (oui ou non), puis explique en trois puces au plus, sans répéter la conclusion. Quand les extraits ne traitent qu'un aspect de la question (par exemple le loyer mais pas la décence), ne conclus pas « oui, c'est permis » : dis ce qui est établi et ce qui manque.
- La date du jour est le {date.today():%d/%m/%Y}. Si un extrait décrit une période, un délai ou un dispositif déjà terminé à cette date, dis-le explicitement au lieu de le présenter comme en cours, et précise que les textes plus récents ne figurent peut-être pas dans les extraits.
- Réponds en français, de façon claire : le terme du métier suivi d'une explication simple, des puces si cela aide, sans te présenter ni conclure.
- Réponds à la question posée, rien de plus : n'ajoute aucun sujet voisin qui n'est pas demandé (vente, audit, aides, loyers) même s'il figure dans les extraits.
"""


def _refus(modele=None):
    return AssistantReponse(reponse=MESSAGE_REFUS, sources=[], refus=True, modele=modele)


def _construire_reponse(texte, extraits, modele):
    """Renumérote les citations dans l'ordre d'apparition (une source = un numéro) ; refus si aucune n'est valide."""
    if MARQUEUR_REFUS in texte:
        return _refus(modele)
    numeros = {}   # (référence, url) -> numéro affiché
    metas = {}

    def remplacer(m):
        n = int(m.group(1))
        if not 1 <= n <= len(extraits):
            return ""
        meta = extraits[n - 1]["metadata"]
        cle = (meta["reference"], meta["url"])
        metas[cle] = meta
        return f"[{numeros.setdefault(cle, len(numeros) + 1)}]"

    corps = re.sub(r"\[(\d+)\]", remplacer, texte).strip()
    corps = re.sub(r"(\[\d+\])(?:\1)+", r"\1", corps)
    if not numeros:
        logger.warning("[immobilier_assistant] Réponse sans citation valide, refus : %.200s", texte)
        return _refus(modele)
    sources = [
        SourceCitee(
            reference=metas[cle]["reference"], type_texte=metas[cle]["type_texte"], statut=metas[cle]["statut"],
            date_version=metas[cle].get("date_version") or None, url=metas[cle]["url"],
        )
        for cle in sorted(numeros, key=numeros.get)
    ]
    return AssistantReponse(reponse=corps, sources=sources, refus=False, modele=modele)


async def repondre(question: str, historique: list[dict]) -> AssistantReponse:
    """Historique : derniers messages {role, content}. La recherche reprend la dernière question de l'utilisateur pour les relances."""
    precedentes = [m["content"] for m in historique if m["role"] == "user"]
    requete = f"{precedentes[-1]} {question}" if precedentes else question
    extraits = await rechercher(requete, K_EXTRAITS)
    # generate_with_fallback appelle LiteLLM de façon synchrone : on l'exécute dans un fil dédié pour ne pas figer
    # la boucle d'événements du backend pendant la réponse
    resultat = await asyncio.to_thread(
        asyncio.run,
        generate_with_fallback(
            system_prompt=SYSTEM_PROMPT, user_prompt=_prompt(question, historique, extraits),
            max_tokens=MAX_TOKENS, temperature=TEMPERATURE, models=MODELES,
        ),
    )
    return _construire_reponse(resultat["response"], extraits, resultat["provider_used"])

"""
assistant_agent.py — Orchestrateur RAG avec function calling (pattern ReAct)
pour le MVP gestion-patrimoine. Tourne côté ml-service (FastAPI, port 8008, OVH).

Architecture validée :
- Appel au LLM local (Qwen2.5-Instruct GGUF) via llama-server, API compatible
  OpenAI, en HTTP direct avec httpx — cohérent avec le pattern SG/Sanofi
  (cf. qwen_finetuned_client.py) : pas de paramètre `tools` natif, pas de LiteLLM.
- Function calling SIMULÉ par prompt (ReAct) : le modèle répond en JSON strict,
  soit une demande de recherche ({"action": "search_referentiel", ...}), soit
  une réponse finale ({"action": "reponse_finale", ...}). Ce fichier parse ce
  JSON et pilote la boucle — aucune dépendance à une config avancée de
  llama-server (--jinja, chat template tool-calling).
- Boucle limitée à MAX_ITERATIONS appels à search_referentiel.
- Anti-hallucination stricte : une réponse finale sans article cité est
  remplacée par un refus explicite.
- Stateless : l'appelant (ml-service /chat) fournit soit le profil (premier
  tour), soit l'historique complet (tours suivants) — rien n'est persisté ici.
- Premier tour déduit de l'absence d'historique (liste vide).

NOTE DE CONFIGURATION (à finaliser à l'étape déploiement OVH) :
LLAMA_SERVER_URL dépend du réseau Docker du service ml-service sur OVH
(gateway différente pour SG: 172.17.0.1, Sanofi: 172.21.0.1) et du port
attribué au llama-server dédié gestion-patrimoine (à choisir, distinct de
8005/8006 déjà pris). Valeur lue depuis la variable d'environnement
LLAMA_SERVER_URL, pas de valeur en dur.
"""

import json
import logging
import os
from typing import Optional
import time

import httpx
from pydantic import BaseModel, ValidationError

from ml.config import LLAMA_MAX_TOKENS, LLAMA_SERVER_URL, LLAMA_TIMEOUT_SEC
from .tools import search_referentiel  # interface validée, code à venir

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Constantes
# --------------------------------------------------------------------------

MAX_ITERATIONS = 3


# --------------------------------------------------------------------------
# Schémas Pydantic — les deux actions possibles du modèle
# --------------------------------------------------------------------------

class DemandeRecherche(BaseModel):
    action: str  # "search_referentiel"
    query: str


class ArticleCite(BaseModel):
    numero_article: str
    url_source: str


class ReponseFinale(BaseModel):
    action: str  # "reponse_finale"
    texte: str
    articles_cites: list[ArticleCite]


# --------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------

class AssistantAgentError(Exception):
    """Erreur remontée au endpoint /chat de ml-service (échec appel LLM)."""
    pass


# --------------------------------------------------------------------------
# Prompt système — instructions du protocole ReAct
# --------------------------------------------------------------------------

def _construire_system_prompt(thematique: str) -> str:
    return f"""Tu es un assistant d'ingénierie patrimoniale. Thématique de l'échange : {thematique}.

Tu dois répondre EXCLUSIVEMENT en JSON, sans aucun texte hors du JSON, selon
l'un de ces deux formats :

1. Pour rechercher un article de loi pertinent avant de répondre :
{{"action": "search_referentiel", "query": "<terme de recherche>"}}

2. Pour donner ta réponse finale (uniquement après avoir trouvé un article pertinent) :
{{"action": "reponse_finale", "texte": "<réponse>", "articles_cites": [{{"numero_article": "...", "url_source": "..."}}]}}

Règles strictes :
- Tu ne dois JAMAIS répondre sans avoir au préalable cherché et trouvé un article pertinent via "search_referentiel".
- Si après plusieurs recherches tu ne trouves aucun article pertinent, réponds avec le format "reponse_finale" en expliquant que tu ne peux pas répondre de manière fiable, et laisse "articles_cites" vide.
- N'invente jamais un numéro d'article ou une donnée absente des résultats de recherche fournis.
"""


# --------------------------------------------------------------------------
# Appel llama-server (pattern httpx direct, cf. qwen_finetuned_client.py)
# --------------------------------------------------------------------------

def _appeler_llama_server(messages: list[dict]) -> str:
    payload = {
        "model": "qwen",
        "messages": messages,
        "max_tokens": LLAMA_MAX_TOKENS,
    }
    try:
        response = httpx.post(LLAMA_SERVER_URL, json=payload, timeout=LLAMA_TIMEOUT_SEC)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Échec appel llama-server : %s", exc)
        raise AssistantAgentError(f"Échec appel llama-server : {exc}") from exc

    data = response.json()
    return data["choices"][0]["message"]["content"]


# --------------------------------------------------------------------------
# Réponse de repli (anti-hallucination / limite d'itérations atteinte)
# --------------------------------------------------------------------------

def _reponse_refus(motif: str, latence_ms: int) -> dict:
    return {
        "texte": f"Je ne peux pas répondre de manière fiable : {motif}",
        "articles_cites": [],
        "tokens_entree": 0,
        "tokens_sortie": 0,
        "latence_ms": latence_ms,
    }


# --------------------------------------------------------------------------
# Fonction principale — boucle ReAct
# --------------------------------------------------------------------------

def repondre(
    thematique: str,
    profil: Optional[dict] = None,
    historique: Optional[list[dict]] = None,
) -> dict:
    """
    Génère une réponse groundée sur referentiel_patrimoine, avec citation
    obligatoire d'article de loi.

    :param thematique: une des 5 thématiques (filtre appliqué à search_referentiel)
    :param profil: profil client issu de profil_agent — fourni uniquement au premier tour
    :param historique: liste de tours [{role, content}, ...] — fournie à partir du 2e tour
    :return: dict {"texte": str, "articles_cites": list[dict]}
    :raises AssistantAgentError: en cas d'échec de communication avec llama-server
    """
    historique = historique or []
    premier_tour = len(historique) == 0
    debut = time.perf_counter()

    messages: list[dict] = [{"role": "system", "content": _construire_system_prompt(thematique)}]

    if premier_tour:
        if profil is None:
            raise AssistantAgentError("Premier tour sans profil fourni.")
        messages.append({
            "role": "user",
            "content": f"Profil client à analyser : {json.dumps(profil, ensure_ascii=False)}",
        })
    else:
        messages.extend(historique)

    for _ in range(MAX_ITERATIONS):
        contenu_brut = _appeler_llama_server(messages)

        try:
            data = json.loads(contenu_brut)
        except json.JSONDecodeError:
            logger.warning("Réponse LLM non-JSON, relance avec correction : %s", contenu_brut)
            messages.append({"role": "assistant", "content": contenu_brut})
            messages.append({
                "role": "user",
                "content": "Réponse invalide : réponds uniquement avec le JSON attendu, sans aucun texte autour.",
            })
            continue

        action = data.get("action")

        if action == "search_referentiel":
            try:
                demande = DemandeRecherche.model_validate(data)
            except ValidationError as exc:
                messages.append({"role": "assistant", "content": contenu_brut})
                messages.append({"role": "user", "content": f"JSON invalide : {exc}. Corrige et renvoie."})
                continue

            resultats = search_referentiel(query=demande.query, thematique=thematique)
            messages.append({"role": "assistant", "content": contenu_brut})
            if resultats:
                messages.append({
                    "role": "user",
                    "content": f"Résultats de recherche : {json.dumps(resultats, ensure_ascii=False)}",
                })
            else:
                messages.append({
                    "role": "user",
                    "content": "Aucun résultat trouvé pour cette recherche. Reformule ou conclus avec un refus explicite.",
                })
            continue

        elif action == "reponse_finale":
            try:
                reponse = ReponseFinale.model_validate(data)
            except ValidationError as exc:
                messages.append({"role": "assistant", "content": contenu_brut})
                messages.append({"role": "user", "content": f"JSON invalide : {exc}. Corrige et renvoie."})
                continue

            latence_ms = int((time.perf_counter() - debut) * 1000)

            if not reponse.articles_cites:
                return _reponse_refus("aucun article pertinent trouvé dans le référentiel.", latence_ms)

            return {
                "texte": reponse.texte,
                "articles_cites": [a.model_dump() for a in reponse.articles_cites],
                "tokens_entree": 0,
                "tokens_sortie": 0,
                "latence_ms": latence_ms,
            }

        else:
            messages.append({"role": "assistant", "content": contenu_brut})
            messages.append({
                "role": "user",
                "content": 'Action inconnue. Utilise uniquement "search_referentiel" ou "reponse_finale".',
            })
            continue

    return _reponse_refus(
        "nombre maximal de recherches atteint sans résultat concluant.",
        int((time.perf_counter() - debut) * 1000),
    )
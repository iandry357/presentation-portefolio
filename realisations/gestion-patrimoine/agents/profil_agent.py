"""
profil_agent.py — Génération de profils clients synthétiques (RGPD-safe)
pour le MVP gestion-patrimoine.

Architecture validée :
- Appel LLM via LiteLLM (pas de LangChain LCEL) : primaire Mistral, fallback Gemini
- Validation stricte du JSON de sortie via Pydantic
- 1 retry automatique en cas d'échec de validation (message d'erreur réinjecté au LLM)
- Tirage aléatoire uniforme de la thématique si non fournie par l'appelant
- Clés API Mistral / Gemini récupérées via Scaleway Secret Manager en amont,
  injectées en variables d'environnement lues nativement par LiteLLM
  (MISTRAL_API_KEY, GEMINI_API_KEY) — aucune lecture de secret dans ce fichier.
"""

import json
import random
import logging
from typing import Optional, Union, Literal

import litellm
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Constantes
# --------------------------------------------------------------------------

THEMATIQUES = [
    "donations_successions",
    "ifi",
    "plus_values",
    "assurance_vie",
    "per",
]

MODELE_PRIMAIRE = "mistral/mistral-small-latest"
MODELE_FALLBACK = "gemini/gemini-2.5-flash"  # à aligner sur le modèle Gemini réellement utilisé ailleurs dans le portfolio

MAX_RETRY_VALIDATION = 1  # une seule tentative de correction après échec Pydantic


# --------------------------------------------------------------------------
# Schémas Pydantic — bloc "details" polymorphe selon la thématique
# --------------------------------------------------------------------------

class DetailsDonationsSuccessions(BaseModel):
    lien_parente: str
    montant: float


class DetailsIFI(BaseModel):
    valeur_patrimoine_immobilier_net: float


class DetailsPlusValues(BaseModel):
    nature_bien: str
    montant_plus_value: float


class DetailsAssuranceVie(BaseModel):
    primes_versees: float
    age_contrat: int


class DetailsPER(BaseModel):
    montant_verse: float
    age_depart_retraite_envisage: int


class ProfilDonationsSuccessions(BaseModel):
    thematique: Literal["donations_successions"]
    age: int
    situation_familiale: str
    patrimoine_global: float
    objectif: str
    details: DetailsDonationsSuccessions


class ProfilIFI(BaseModel):
    thematique: Literal["ifi"]
    age: int
    situation_familiale: str
    patrimoine_global: float
    objectif: str
    details: DetailsIFI


class ProfilPlusValues(BaseModel):
    thematique: Literal["plus_values"]
    age: int
    situation_familiale: str
    patrimoine_global: float
    objectif: str
    details: DetailsPlusValues


class ProfilAssuranceVie(BaseModel):
    thematique: Literal["assurance_vie"]
    age: int
    situation_familiale: str
    patrimoine_global: float
    objectif: str
    details: DetailsAssuranceVie


class ProfilPER(BaseModel):
    thematique: Literal["per"]
    age: int
    situation_familiale: str
    patrimoine_global: float
    objectif: str
    details: DetailsPER


ProfilPatrimoine = Union[
    ProfilDonationsSuccessions,
    ProfilIFI,
    ProfilPlusValues,
    ProfilAssuranceVie,
    ProfilPER,
]

_SCHEMA_PAR_THEMATIQUE = {
    "donations_successions": ProfilDonationsSuccessions,
    "ifi": ProfilIFI,
    "plus_values": ProfilPlusValues,
    "assurance_vie": ProfilAssuranceVie,
    "per": ProfilPER,
}


# --------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------

class ProfilAgentError(Exception):
    """Erreur remontée au backend après épuisement des tentatives."""
    pass


# --------------------------------------------------------------------------
# Construction du prompt
# --------------------------------------------------------------------------

def _construire_prompt(thematique: str, erreur_precedente: Optional[str] = None) -> str:
    schema_cls = _SCHEMA_PAR_THEMATIQUE[thematique]
    schema_json = schema_cls.model_json_schema()

    prompt = f"""Tu génères un profil client fictif RGPD-safe pour un copilote d'ingénierie patrimoniale.

Thématique imposée : {thematique}

Réponds UNIQUEMENT avec un objet JSON valide respectant strictement ce schéma :
{json.dumps(schema_json, ensure_ascii=False, indent=2)}

Aucun texte hors du JSON. Aucune donnée réelle ou identifiable — profil entièrement synthétique.
"""

    if erreur_precedente:
        prompt += f"""

Ta précédente réponse était invalide pour la raison suivante :
{erreur_precedente}

Corrige et renvoie un nouveau JSON strictement conforme au schéma.
"""

    return prompt


# --------------------------------------------------------------------------
# Appel LLM avec fallback Mistral → Gemini (géré nativement par LiteLLM)
# --------------------------------------------------------------------------

def _appeler_llm(prompt: str) -> str:
    response = litellm.completion(
        model=MODELE_PRIMAIRE,
        messages=[{"role": "user", "content": prompt}],
        fallbacks=[MODELE_FALLBACK],
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


# --------------------------------------------------------------------------
# Fonction principale
# --------------------------------------------------------------------------

def generer_profil(thematique: Optional[str] = None) -> dict:
    """
    Génère un profil client synthétique validé.

    :param thematique: une des valeurs de THEMATIQUES, ou None pour tirage aléatoire uniforme
    :return: dict conforme au schéma Pydantic de la thématique
    :raises ProfilAgentError: si l'appel LLM échoue (après fallback) ou si la
        validation Pydantic échoue après le retry
    """
    if thematique is None:
        thematique = random.choice(THEMATIQUES)
    elif thematique not in THEMATIQUES:
        raise ProfilAgentError(f"Thématique inconnue : {thematique}")

    schema_cls = _SCHEMA_PAR_THEMATIQUE[thematique]
    erreur_precedente: Optional[str] = None

    for tentative in range(MAX_RETRY_VALIDATION + 1):
        prompt = _construire_prompt(thematique, erreur_precedente)

        try:
            contenu_brut = _appeler_llm(prompt)
        except Exception as exc:
            logger.error("Échec appel LLM (tentative %s) : %s", tentative, exc)
            raise ProfilAgentError(f"Échec appel LLM (Mistral + fallback Gemini) : {exc}") from exc

        try:
            data = json.loads(contenu_brut)
            profil = schema_cls.model_validate(data)
            return profil.model_dump()
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("Validation Pydantic échouée (tentative %s) : %s", tentative, exc)
            erreur_precedente = str(exc)
            continue

    raise ProfilAgentError(
        f"Validation Pydantic échouée après {MAX_RETRY_VALIDATION + 1} tentative(s) : {erreur_precedente}"
    )
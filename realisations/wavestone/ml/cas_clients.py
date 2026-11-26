"""
Classification des cas clients — Wavestone
Catégories tirées des données, sans liste écrite à la main :
  ① étiquetage libre  : pour chaque cas client, un LLM donne un secteur et 1 ou 2 types de mission en quelques mots,
                         plus le client et un résumé d'une phrase ;
  ② consolidation     : un appel LLM par axe regroupe les étiquettes distinctes en NB_CATEGORIES_MIN à MAX catégories ;
  ③ affectation       : chaque cas reçoit la catégorie de ses étiquettes (code, sans LLM).
LLM : Mistral, Gemini en secours, via LiteLLM. Sortie : results/cas_clients.json (à copier dans backend/routers/wavestone/data/).
"""

import json
import logging
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime

import litellm

from bq_client import get_news

logger = logging.getLogger(__name__)

SECTION_CAS_CLIENTS = "clients_story"
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results", "cas_clients.json")
MAX_CHARS_TEXTE = 3000      # début du texte envoyé au LLM à l'étape ①
NB_MISSIONS_MAX = 2         # étiquettes de mission par cas
NB_CATEGORIES_MIN = 5       # fourchette de catégories demandée à l'étape ②, par axe
NB_CATEGORIES_MAX = 10
PAUSE_SECONDES = 1.0        # entre deux appels LLM (limites de débit)
AUTRE = "Autre"

AXES = {
    "secteur": "secteur d'activité du client",
    "mission": "type de mission menée par Wavestone",
}

MODELES = [
    ("mistral/mistral-small-latest", "MISTRAL_API_KEY"),
    ("gemini/gemini-1.5-flash",      "GEMINI_API_KEY"),
]


# ─────────────────────────────────────────
# LLM
# ─────────────────────────────────────────
def _ask_llm(prompt: str, max_tokens: int):
    for model, key_env in MODELES:
        api_key = os.getenv(key_env, "")
        if not api_key:
            continue
        try:
            response = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                api_key=api_key,
                max_tokens=max_tokens,
                temperature=0,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"[cas_clients] {model} failed : {e} — trying next")
    return None


def _parser(reponse) -> dict:
    """Extrait l'objet JSON de la réponse ; dictionnaire vide si illisible."""
    if not reponse:
        return {}
    m = re.search(r"\{.*\}", reponse, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def _norm(valeur):
    """Étiquette normalisée (minuscules, sans point final) ; None si vide."""
    if not isinstance(valeur, str):
        return None
    v = valeur.strip().rstrip(".").strip().lower()
    return v or None


# ─────────────────────────────────────────
# ① Étiquetage libre
# ─────────────────────────────────────────
def _prompt_etiquette(titre: str, texte: str) -> str:
    return (
        "Tu analyses un cas client publié par le cabinet de conseil Wavestone.\n"
        f"Titre : {titre}\n"
        f"Texte : {texte[:MAX_CHARS_TEXTE]}\n\n"
        "Réponds uniquement avec un objet JSON, sans texte autour, avec ces clés :\n"
        "- \"secteur\" : le secteur d'activité du client, libellé générique de 1 à 4 mots en français, sans nom d'entreprise\n"
        f"- \"missions\" : liste de 1 à {NB_MISSIONS_MAX} types de mission menée par Wavestone, chacun en 2 à 5 mots en français, "
        "génériques (la nature du travail, pas le nom du client), le principal d'abord\n"
        "- \"client\" : le nom du client s'il est cité, sinon une description courte en français (ex. « grand assureur américain »)\n"
        "- \"resume\" : une phrase en français (30 mots maximum) qui dit ce que Wavestone a fait et pour quel résultat, "
        "sans mise en forme Markdown, en t'appuyant uniquement sur le texte."
    )


def _etiqueter(doc: dict) -> dict:
    brut = _parser(_ask_llm(_prompt_etiquette(doc.get("title") or "", doc.get("content") or ""), max_tokens=300))
    missions = brut.get("missions") or []
    if isinstance(missions, str):
        missions = [missions]
    missions = list(dict.fromkeys(m for m in (_norm(x) for x in missions) if m))[:NB_MISSIONS_MAX]
    return {
        "ok":              bool(brut),
        "secteur_libre":   _norm(brut.get("secteur")),
        "missions_libres": missions,
        "client":          (brut.get("client") or "").strip() or None,
        "resume":          (brut.get("resume") or "").replace("**", "").strip() or None,
    }


# ─────────────────────────────────────────
# ② Consolidation
# ─────────────────────────────────────────
def _consolider(axe: str, etiquettes: Counter, nb_cas: int):
    """Regroupe les étiquettes d'un axe en catégories ; renvoie (catégories, {étiquette: catégorie})."""
    liste = etiquettes.most_common()
    lignes = "\n".join(f"{i}. {e} ({n})" for i, (e, n) in enumerate(liste, start=1))
    prompt = (
        f"Voici des étiquettes libres décrivant le {AXES[axe]} de {nb_cas} cas clients du cabinet de conseil Wavestone, "
        f"avec leur nombre d'occurrences :\n{lignes}\n\n"
        f"Regroupe-les en {NB_CATEGORIES_MIN} à {NB_CATEGORIES_MAX} catégories, chacune avec un libellé court en français "
        "(2 à 5 mots). Chaque étiquette va dans exactement une catégorie ; une catégorie réunit des étiquettes proches.\n"
        "Réponds uniquement avec un objet JSON, sans texte autour : "
        "{\"categories\": [\"libellé\", ...], \"affectation\": {\"numéro de l'étiquette\": \"libellé de la catégorie\", ...}}"
    )
    brut = _parser(_ask_llm(prompt, max_tokens=4000))
    categories = list(dict.fromkeys(
        c.strip() for c in (brut.get("categories") or []) if isinstance(c, str) and c.strip()
    ))
    if not NB_CATEGORIES_MIN <= len(categories) <= NB_CATEGORIES_MAX:
        print(f"[cas_clients] ⚠️ {axe} : {len(categories)} catégories, hors de la fourchette {NB_CATEGORIES_MIN}–{NB_CATEGORIES_MAX}")
    affectation = brut.get("affectation") or {}
    correspondance = {}
    for i, (etiquette, _) in enumerate(liste, start=1):
        cat = affectation.get(str(i))
        correspondance[etiquette] = cat.strip() if isinstance(cat, str) and cat.strip() in categories else AUTRE
    return categories, correspondance


def _afficher_consolidation(axe: str, etiquettes: Counter, correspondance: dict) -> None:
    groupes = defaultdict(list)
    for etiquette, n in etiquettes.most_common():
        groupes[correspondance[etiquette]].append(f"{etiquette} ({n})")
    print(f"\n[cas_clients] {axe} : {len(etiquettes)} étiquettes distinctes → {len(groupes)} catégories")
    for cat, membres in sorted(groupes.items(), key=lambda x: -len(x[1])):
        print(f"  ▸ {cat} : {', '.join(membres)}")


# ─────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────
def _charger_cas() -> list:
    """Premiers morceaux des cas clients d'articles_bruts."""
    cas = [
        d for d in get_news()
        if d.get("metadata", {}).get("section") == SECTION_CAS_CLIENTS
        and d.get("metadata", {}).get("chunk_index", 0) == 0
    ]
    print(f"[cas_clients] {len(cas)} cas clients")
    return cas


def run() -> dict:
    cas = _charger_cas()

    # ① Étiquetage libre
    etiquetes = []
    for i, doc in enumerate(cas, start=1):
        e = _etiqueter(doc)
        etiquetes.append(e)
        print(f"[cas_clients] {i:3d} [{doc.get('metadata', {}).get('langue')}] "
              f"{e['secteur_libre']} | {', '.join(e['missions_libres'])} — {doc.get('title')}")
        time.sleep(PAUSE_SECONDES)
    echecs = sum(not e["ok"] for e in etiquetes)

    # ② Consolidation
    secteurs_cnt = Counter(e["secteur_libre"] for e in etiquetes if e["secteur_libre"])
    missions_cnt = Counter(m for e in etiquetes for m in e["missions_libres"])
    secteurs, corr_secteurs = _consolider("secteur", secteurs_cnt, len(cas))
    types, corr_missions = _consolider("mission", missions_cnt, len(cas))
    _afficher_consolidation("secteur", secteurs_cnt, corr_secteurs)
    _afficher_consolidation("mission", missions_cnt, corr_missions)

    # ③ Affectation
    cas_out = []
    for doc, e in zip(cas, etiquetes):
        meta = doc.get("metadata", {})
        types_cas = list(dict.fromkeys(corr_missions.get(m, AUTRE) for m in e["missions_libres"])) or [AUTRE]
        cas_out.append({
            "id":              doc.get("id"),
            "title":           doc.get("title"),
            "date":            doc.get("date"),
            "url":             meta.get("url", ""),
            "lang":            meta.get("langue"),
            "secteur":         corr_secteurs.get(e["secteur_libre"], AUTRE),
            "types_mission":   types_cas,
            "secteur_libre":   e["secteur_libre"],
            "missions_libres": e["missions_libres"],
            "client":          e["client"],
            "resume":          e["resume"],
        })

    result = {
        "genere_le":     datetime.utcnow().isoformat(timespec="seconds"),
        "total":         len(cas_out),
        "secteurs":      secteurs + [AUTRE],
        "types_mission": types + [AUTRE],
        "cas":           cas_out,
    }
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n[cas_clients] Done — {len(cas_out)} cas, {echecs} réponses LLM illisibles → {RESULTS_PATH}")
    print("[cas_clients] Secteurs :")
    for s, n in Counter(c["secteur"] for c in cas_out).most_common():
        print(f"  {n:3d}  {s}")
    print("[cas_clients] Types de mission :")
    for t, n in Counter(t for c in cas_out for t in c["types_mission"]).most_common():
        print(f"  {n:3d}  {t}")
    return result


if __name__ == "__main__":
    run()
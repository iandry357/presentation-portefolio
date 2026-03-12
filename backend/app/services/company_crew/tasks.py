import json
import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser

from app.services.company_crew.agents import (
    make_discovery_llm,
    make_extractor_llm,
    make_synthesizer_llm,
    make_serper_tool,
    scrape_url,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# Schémas JSON fixes
# ------------------------------------------------------------

# DISCOVERY_SCHEMA = {
#     "siren": "string ou null",
#     "forme_juridique": "string ou null",
#     "date_creation": "string ou null",
#     "dirigeant": "string ou null",
#     "effectif": "string ou null",
#     "secteur_naf": "string ou null",
#     "urls": {
#         "site_officiel": "string ou null",
#         "linkedin": "string ou null",
#         "glassdoor": "string ou null",
#         "hellowork": "string ou null",
#         "societe_com": "string ou null",
#         "annuaire_entreprises": "string ou null",
#     },
# }

DISCOVERY_SCHEMA = {
    "siren": "string ou null",
    "forme_juridique": "string ou null",
    "date_creation": "string ou null",
    "dirigeant": "string ou null",
    "effectif": "string ou null",
    "chiffre_affaires": "string ou null",
    "secteur_naf": "string ou null",
    "domaine_activite": "string ou null",
    "valeurs": ["string"],
    "urls": {
        "site_officiel": "string ou null",
        "linkedin": "string ou null",
        "glassdoor": "string ou null",
        "hellowork": "string ou null",
        "societe_com": "string ou null",
        "annuaire_entreprises": "string ou null",
    },
    "serper_actualites": "string — contenu brut des résultats recherche actualités",
}

LEGAL_SCHEMA = {
    "sante_financiere": {
        "chiffre_affaires": "string ou null",
        "resultat_net": "string ou null",
        "evolution": "string ou null",
        "levees_de_fonds": "string ou null",
    },
    "activite": {
        "description": "string ou null",
        "core_business": "string ou null",
        "produits_services": ["string"],
        "cibles": "string ou null",
        "positionnement": "string ou null",
    },
    "image_employeur": {
        "glassdoor_note": "string ou null",
        "glassdoor_pros": ["string"],
        "glassdoor_cons": ["string"],
        "valeurs": ["string"],
        "retours_entretien": "string ou null",
    },
}

# ACTUALITES_SCHEMA = {
#     "articles": [
#         {
#             "titre": "string",
#             "source": "string",
#             "date": "string ou null",
#             "resume": "string",
#         }
#     ],
#     "signaux": {
#         "recrutement": "string ou null",
#         "expansion": "string ou null",
#         "autres": "string ou null",
#     },
# }
ACTUALITES_SCHEMA = {
    "articles": [
        {
            "titre": "string",
            "source": "string",
            "date": "string ou null",
            "resume": "string",
            "url": "string ou null",
        }
    ],
    "signaux": {
        "recrutement": "string ou null",
        "expansion": "string ou null",
        "autres": "string ou null",
    },
}


# ------------------------------------------------------------
# Chain 1 — Discovery
# ------------------------------------------------------------

def run_discovery_chain(company_name: str) -> dict:
    """
    Recherche Serper × 2 + browse annuaire-entreprises.
    Retourne le JSON discovery ou lève une exception.
    """
    serper = make_serper_tool()
    llm = make_discovery_llm()

    query1 = f"{company_name} SIREN site officiel LinkedIn"
    results1 = serper.run(query1)
    logger.info(f"[discovery] Serper recherche 1 OK — {company_name}")

    query2 = f"{company_name} chiffre affaires effectif secteur activité"
    results2 = serper.run(query2)
    logger.info(f"[discovery] Serper recherche 2 OK — {company_name}")

    query3 = f"{company_name} actualités 2025 2026"
    results3 = serper.run(query3)
    logger.info(f"[discovery] Serper recherche 3 OK — {company_name}")

    query4 = f"{company_name} avis employés culture entreprise valeurs"
    results4 = serper.run(query4)
    logger.info(f"[discovery] Serper recherche 4 OK — {company_name}")

    # Browse annuaire-entreprises (URL construite, pas de Serper)
    annuaire_url = (
        f"https://annuaire-entreprises.data.gouv.fr/rechercher"
        f"?terme={company_name.replace(' ', '+')}"
    )
    annuaire_text = scrape_url(annuaire_url)
    logger.info(f"[discovery] Browse annuaire OK — {company_name}")

    # Chain LCEL
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Tu es un expert en recherche d'informations sur les entreprises françaises. "
         "Tu extrais des données structurées depuis des résultats de recherche. "
         "Tu réponds UNIQUEMENT avec un objet JSON valide — aucun texte avant ou après. "
         "Les valeurs inconnues sont null, jamais inventées."),
        ("human",
        "Entreprise : {company_name}\n\n"
        "Résultats recherche identité :\n{results1}\n\n"
        "Résultats recherche données financières :\n{results2}\n\n"
        "Résultats recherche actualités :\n{results3}\n\n"
        "Résultats recherche image employeur :\n{results4}\n\n"
        "Données annuaire officiel :\n{annuaire_text}\n\n"
        "Retourne un JSON correspondant exactement à ce schéma :\n{schema}\n\n"
        "IMPORTANT : copie le contenu brut de 'Résultats recherche actualités' "
        "dans le champ 'serper_actualites' sans le modifier."),
    ])

    chain = prompt | llm | JsonOutputParser()

    return chain.invoke({
        "company_name": company_name,
        "results1": results1,
        "results2": results2,
        "results3": results3,
        "results4": results4,
        "annuaire_text": annuaire_text,
        "schema": json.dumps(DISCOVERY_SCHEMA, ensure_ascii=False, indent=2),
    })


# ------------------------------------------------------------
# Chain 2 — Extraction légale
# ------------------------------------------------------------

def run_extractor_chain(discovery: dict) -> dict:
    """
    Browse societe.com + site officiel + Glassdoor/HelloWork.
    Retourne le JSON legal_data. Dégradation gracieuse si page inaccessible.
    """
    llm = make_extractor_llm()
    urls = discovery.get("urls", {})

    # Browse chaque source — "" si inaccessible
    societe_text    = scrape_url(urls.get("societe_com") or "")
    site_text       = scrape_url(urls.get("site_officiel") or "")
    glassdoor_text  = scrape_url(urls.get("glassdoor") or "")
    hellowork_text  = (
        scrape_url(urls.get("hellowork") or "")
        if not glassdoor_text
        else ""
    )

    logger.info(f"[extractor] Browses terminés — societe={bool(societe_text)} "
                f"site={bool(site_text)} glassdoor={bool(glassdoor_text)}")

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Tu es un analyste spécialisé dans l'extraction d'informations d'entreprise. "
         "Tu extrais uniquement ce qui est explicitement présent dans les données fournies. "
         "Tu réponds UNIQUEMENT avec un objet JSON valide — aucun texte avant ou après. "
         "Les valeurs inconnues sont null, jamais inventées."),
        ("human",
         "Données societe.com :\n{societe_text}\n\n"
         "Données site officiel :\n{site_text}\n\n"
         "Données Glassdoor :\n{glassdoor_text}\n\n"
         "Données HelloWork :\n{hellowork_text}\n\n"
         "Retourne un JSON correspondant exactement à ce schéma :\n{schema}"),
    ])

    chain = prompt | llm | JsonOutputParser()

    return chain.invoke({
        "societe_text":   societe_text   or "Non disponible",
        "site_text":      site_text      or "Non disponible",
        "glassdoor_text": glassdoor_text or "Non disponible",
        "hellowork_text": hellowork_text or "Non disponible",
        "schema": json.dumps(LEGAL_SCHEMA, ensure_ascii=False, indent=2),
    })


# ------------------------------------------------------------
# Chain 3 — Actualités
# ------------------------------------------------------------

def run_actualites_chain(discovery: dict) -> dict:
    """
    Extrait les actualités depuis les snippets Serper déjà en discovery.
    Tente un browse du site officiel en complément si disponible.
    Zéro crédit Serper supplémentaire.
    """
    llm = make_extractor_llm()

    serper_actualites = discovery.get("serper_actualites", "")
    site_text = scrape_url(discovery.get("urls", {}).get("site_officiel") or "")

    logger.info(f"[actualites] serper={bool(serper_actualites)} site={bool(site_text)}")

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Tu extrais les actualités récentes d'une entreprise depuis des résultats de recherche. "
         "Tu te concentres sur les faits réels présents dans les données fournies. "
         "Tu n'inventes JAMAIS d'actualité — si aucune donnée réelle n'est disponible, "
         "tu retournes articles: []. "
         "Tu réponds UNIQUEMENT avec un objet JSON valide — aucun texte avant ou après. "
         "Maximum 5 articles. Les valeurs inconnues sont null."),
        ("human",
         "Résultats recherche actualités :\n{serper_actualites}\n\n"
         "Données site officiel :\n{site_text}\n\n"
         "Retourne un JSON correspondant exactement à ce schéma :\n{schema}"),
    ])

    chain = prompt | llm | JsonOutputParser()

    return chain.invoke({
        "serper_actualites": serper_actualites or "Non disponible",
        "site_text":         site_text         or "Non disponible",
        "schema": json.dumps(ACTUALITES_SCHEMA, ensure_ascii=False, indent=2),
    })


# ------------------------------------------------------------
# Chain 4 — Synthèse mémo
# ------------------------------------------------------------

def run_synthesizer_chain(
    discovery: dict,
    legal: dict,
    actualites: dict,
    instruction: str | None = None,
    offer_context: str | None = None,
    profile_context: str | None = None,
) -> str:
    """
    Rédige le mémo Markdown final.
    instruction optionnelle — fournie lors d'un recalcul.
    """
    llm = make_synthesizer_llm()

    instruction_block = (
        f"\nINSTRUCTION SPÉCIALE POUR CE RECALCUL :\n{instruction}\n"
        if instruction
        else ""
    )

    offer_block = (
        f"\nCONTEXTE DE L'OFFRE :\n{offer_context}\n"
        if offer_context
        else ""
    )

    profile_block = (
        f"\nPROFIL DU CANDIDAT (expériences) :\n{profile_context}\n"
        if profile_context
        else ""
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Tu es un coach carrière expert qui aide les candidats à préparer leurs entretiens. "
         "Tu rédiges un mémo structuré, clair et actionnable. "
         "Tu n'inventes jamais d'informations — tu indiques 'Information non disponible' "
        "si une donnée est absente. "
        "Pour les actualités, si une URL est disponible, tu la formates en Markdown : [titre](url). "
        "Tu réponds UNIQUEMENT avec le mémo Markdown — pas de balises ```markdown```."),
        ("human",
        "DONNÉES IDENTITÉ :\n{discovery}\n\n"
        "DONNÉES LÉGALES & ACTIVITÉ :\n{legal}\n\n"
        "ACTUALITÉS & COMMUNICATION :\n{actualites}\n\n"
        "{offer_block}"
        "{profile_block}"
        "{instruction_block}"
        "STRUCTURE OBLIGATOIRE DU MÉMO :\n"
        "## 1. Faits officiels\n"
        "## 2. Activité & positionnement\n"
        "## 3. Image employeur\n"
        "## 4. Communication publique & actualités\n"
        "   (inclure le lien cliquable [titre](url) pour chaque article si URL disponible)\n"
        "## 5. Questions intelligentes à poser\n"
        "   (basées sur l'offre et les valeurs/activité de l'entreprise si disponibles)\n"
        "## 6. Points à mettre en avant\n"
        "   (basés sur le profil candidat et les attentes de l'entreprise si disponibles)\n\n"
        "RÈGLES STRICTES :\n"
        "- Si une donnée est absente, écrire 'Information non disponible' — ne jamais inventer\n"
        "- Les sections 5 et 6 doivent utiliser le contexte offre et profil si fournis\n"
        "- Si offre et profil sont absents, rédiger les sections 5 et 6 de façon générique\n"
        "- Longueur cible : 400 à 600 mots. Commence directement par ## 1."),
    ])

    chain = prompt | llm | StrOutputParser()

    return chain.invoke({
        "discovery":          json.dumps(discovery,  ensure_ascii=False, indent=2),
        "legal":              json.dumps(legal,       ensure_ascii=False, indent=2),
        "actualites":         json.dumps(actualites,  ensure_ascii=False, indent=2),
        "instruction_block":  instruction_block,
        "offer_block":       offer_block,
        "profile_block":     profile_block,
    })
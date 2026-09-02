"""
legifrance_collector.py

Collecte des articles du Code Général des Impôts (CGI) pertinents pour la
base de connaissances "referentiel_patrimoine", via l'API officielle
Légifrance (portail PISTE).

Mécanisme (v2 — validé après tests réels avec test_piste_connection.py) :
    1. POST /consult/code/tableMatieres (textId=CGI, sctId="")
       -> arbre complet de la table des matières : sections récursives,
          chaque section porte ses propres articles (id, num, etat) et ses
          sous-sections. Le texte des articles (content) n'est PAS inclus.
    2. Parcours récursif de l'arbre : chaque titre de section est comparé
       aux mots-clés thématiques (config.THEMATIQUES). Les articles de toute
       branche matchée (et de ses sous-sections) sont retenus, tagués avec
       la/les thématique(s) qui ont matché.
    3. Filtrage sur etat == "VIGUEUR" (déjà disponible dans l'arbre, sans
       appel supplémentaire).
    4. POST /consult/getArticle pour chaque article retenu -> texte complet.

Sortie : un fichier JSON (config.RAW_ARTICLES_PATH) consommé ensuite par
transformation/chunking.py. Ce script ne fait QUE la collecte brute — pas
de chunking, pas de chargement BigQuery/ChromaDB (responsabilité de
loaders/).

Historique : la première version de ce fichier utilisait POST /search,
qui s'est révélé inadapté (ne renvoie qu'un sous-ensemble tronqué
d'articles par recherche, moreArticlesCount non exploitable). Remplacé
par le mécanisme table des matières ci-dessus après diagnostic avec
test_piste_connection.py.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

import requests

from config import (
    PISTE_ENV,
    PISTE_CLIENT_ID,
    PISTE_CLIENT_SECRET,
    CODE_TEXT_ID,
    THEMATIQUES,
    DELAI_ENTRE_APPELS_SEC,
    RAW_ARTICLES_PATH,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("legifrance_collector")


# ---------------------------------------------------------------------------
# Client API PISTE / Légifrance
# ---------------------------------------------------------------------------

class LegifranceClient:
    """Client minimal pour l'API Légifrance via PISTE (OAuth2 client credentials)."""

    def __init__(self):
        if not PISTE_CLIENT_ID or not PISTE_CLIENT_SECRET:
            raise ValueError(
                "PISTE_CLIENT_ID et PISTE_CLIENT_SECRET doivent être définis "
                "dans le fichier .env"
            )

        if PISTE_ENV == "production":
            self.token_url = "https://oauth.piste.gouv.fr/api/oauth/token"
            self.base_url = "https://api.piste.gouv.fr"
        else:
            self.token_url = "https://sandbox-oauth.piste.gouv.fr/api/oauth/token"
            self.base_url = "https://sandbox-api.piste.gouv.fr"

        self.api_url = f"{self.base_url}/dila/legifrance/lf-engine-app"

        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    def _get_access_token(self) -> str:
        if self._access_token and self._token_expires_at and datetime.now() < self._token_expires_at:
            return self._access_token

        response = requests.post(
            self.token_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": PISTE_CLIENT_ID,
                "client_secret": PISTE_CLIENT_SECRET,
                "scope": "openid",
            },
            timeout=30,
        )
        response.raise_for_status()
        token_data = response.json()

        self._access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        self._token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)

        return self._access_token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get_table_matieres(self, text_id: str) -> Dict[str, Any]:
        """POST /consult/code/tableMatieres — arbre complet de la table des matières d'un code."""
        payload = {
            "date": int(time.time() * 1000),
            "sctId": "",
            "textId": text_id,
        }
        response = requests.post(
            f"{self.api_url}/consult/code/tableMatieres",
            headers=self._headers(),
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def get_article(self, article_id: str) -> Dict[str, Any]:
        """POST /consult/getArticle — récupère le contenu complet d'un article."""
        response = requests.post(
            f"{self.api_url}/consult/getArticle",
            headers=self._headers(),
            json={"id": article_id},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


# ---------------------------------------------------------------------------
# Parcours de l'arbre et filtrage thématique
# ---------------------------------------------------------------------------

def titre_matche_thematiques(titre: str) -> Set[str]:
    """Retourne l'ensemble des thématiques dont un des mots-clés apparaît dans le titre."""
    if not titre:
        return set()
    titre_normalise = titre.lower()
    thematiques_matchees = set()
    for thematique, mots_cles in THEMATIQUES.items():
        for mot_cle in mots_cles:
            if mot_cle.lower() in titre_normalise:
                thematiques_matchees.add(thematique)
                break
    return thematiques_matchees


def collecter_articles_descendants(section: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Collecte récursivement tous les articles d'une section et de ses sous-sections."""
    articles = list(section.get("articles", []))
    for sous_section in section.get("sections", []):
        articles.extend(collecter_articles_descendants(sous_section))
    return articles


def parcourir_arbre(
    section: Dict[str, Any],
    articles_par_thematique: Dict[str, Set[str]],
) -> None:
    """
    Parcourt récursivement l'arbre de la table des matières.
    Quand le titre d'une section matche une ou plusieurs thématiques, tous
    les articles de cette section ET de ses sous-sections sont tagués avec
    ces thématiques. Le parcours continue en profondeur dans tous les cas,
    pour ne pas manquer une thématique différente plus bas dans l'arbre.
    """
    thematiques_matchees = titre_matche_thematiques(section.get("title", ""))

    if thematiques_matchees:
        for article in collecter_articles_descendants(section):
            article_id = article.get("id")
            if not article_id:
                continue
            for thematique in thematiques_matchees:
                articles_par_thematique.setdefault(article_id, set()).add(thematique)

    for sous_section in section.get("sections", []):
        parcourir_arbre(sous_section, articles_par_thematique)


def collecter_articles_bruts() -> List[Dict[str, Any]]:
    """Orchestration complète de la collecte."""
    client = LegifranceClient()

    logger.info("Récupération de la table des matières du CGI (textId=%s)", CODE_TEXT_ID)
    arbre = client.get_table_matieres(CODE_TEXT_ID)

    # ⚠️ La racine de l'arbre a la même forme qu'une section (title, sections)
    # d'après la réponse observée lors des tests.
    ids_par_thematique: Dict[str, Set[str]] = {}
    parcourir_arbre(arbre, ids_par_thematique)

    logger.info("Total d'articles uniques matchés (avant filtrage abrogés) : %d", len(ids_par_thematique))

    # Le statut ("etat") de chaque article est déjà connu depuis l'arbre —
    # on le retrouve en reparcourant les articles collectés pour éviter un
    # appel réseau juste pour ça. On reconstruit un index id -> noeud article.
    index_articles: Dict[str, Dict[str, Any]] = {}

    def indexer(section: Dict[str, Any]) -> None:
        for article in section.get("articles", []):
            article_id = article.get("id")
            if article_id:
                index_articles[article_id] = article
        for sous_section in section.get("sections", []):
            indexer(sous_section)

    indexer(arbre)

    articles_collectes: List[Dict[str, Any]] = []

    for article_id, thematiques_matchees in ids_par_thematique.items():
        noeud = index_articles.get(article_id, {})
        etat = noeud.get("etat")

        if etat and etat.upper() != "VIGUEUR":
            logger.info("Article %s exclu (statut=%s)", article_id, etat)
            continue

        try:
            article_complet = client.get_article(article_id)
        except requests.exceptions.RequestException as e:
            logger.warning("Échec de récupération de l'article %s : %s", article_id, e)
            continue

        # ⚠️ Structure de /consult/getArticle pas encore confirmée par un test
        # réel (contrairement à tableMatieres) — .get() partout par prudence,
        # à ajuster si le contenu n'apparaît pas là où attendu.
        article = article_complet.get("article", article_complet)

        articles_collectes.append({
            "id": article_id,
            "numero": noeud.get("num") or article.get("num"),
            "texte": article.get("content") or article.get("texte"),
            "etat": etat,
            "date_debut": noeud.get("dateDebut"),
            "date_fin": noeud.get("dateFin"),
            "thematiques": sorted(thematiques_matchees),
            "url_source": f"https://www.legifrance.gouv.fr/codes/article_lc/{article_id}",
        })

        time.sleep(DELAI_ENTRE_APPELS_SEC)

    logger.info("Total d'articles retenus après filtrage : %d", len(articles_collectes))
    return articles_collectes


def main():
    articles = collecter_articles_bruts()

    with open(RAW_ARTICLES_PATH, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    logger.info("Collecte terminée. %d articles écrits dans %s", len(articles), RAW_ARTICLES_PATH)


if __name__ == "__main__":
    main()
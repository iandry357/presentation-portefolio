"""Collecte du corpus juridique (API Légifrance / PISTE) : textes consolidés, codes (CGI, CCH) et lois de finances.

Sortie : DOSSIER_CORPUS/piste_brut.json, une entrée par version d'article retenue (texte brut + métadonnées), sans découpage
(transformation.py). Un article de la liste explicite absent de PISTE arrête la collecte avant toute écriture.
"""
import json
import logging
import re
import time
from collections import Counter
from datetime import datetime, timedelta

import requests

from pipeline.referentiel.config import (
    ANNEE_LF_MIN, ARTICLES_CCH, ARTICLES_CGI, CCH_TEXT_ID, CGI_TEXT_ID, DELAI_APPELS, DOSSIER_CORPUS, ETAT_A_VENIR,
    ETATS_EN_VIGUEUR, FICHIER_PISTE_BRUT, LIBELLE_CCH, LIBELLE_CGI, PISTE_CLIENT_ID, PISTE_CLIENT_SECRET, PISTE_ENV,
    TEXTES_LEGI, THEME_LOIS_FINANCES, TIMEOUT, TITRE_REGEX_COMPILES, URL_LEGIFRANCE_CODES, URL_LEGIFRANCE_JORF,
    URL_LEGIFRANCE_LODA,
)

logger = logging.getLogger(__name__)


class ClientPiste:
    """Client minimal de l'API Légifrance via PISTE (OAuth2 client credentials, jeton renouvelé avant expiration)."""

    def __init__(self, env):
        if not PISTE_CLIENT_ID or not PISTE_CLIENT_SECRET:
            raise ValueError("PISTE_CLIENT_ID et PISTE_CLIENT_SECRET doivent être définis dans pipeline/.env")
        prefixe = "" if env == "production" else "sandbox-"
        self.url_jeton = f"https://{prefixe}oauth.piste.gouv.fr/api/oauth/token"
        self.url_api = f"https://{prefixe}api.piste.gouv.fr/dila/legifrance/lf-engine-app"
        self._jeton, self._expire = None, datetime.min

    def _entetes(self):
        if datetime.now() >= self._expire:
            r = requests.post(
                self.url_jeton, headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={"grant_type": "client_credentials", "client_id": PISTE_CLIENT_ID, "client_secret": PISTE_CLIENT_SECRET, "scope": "openid"},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            jeton = r.json()
            self._jeton = jeton["access_token"]
            self._expire = datetime.now() + timedelta(seconds=jeton.get("expires_in", 3600) - 60)
        return {"Authorization": f"Bearer {self._jeton}", "Content-Type": "application/json", "Accept": "application/json"}

    def appeler(self, chemin, payload, essais=3):
        for essai in range(1, essais + 1):
            try:
                r = requests.post(f"{self.url_api}{chemin}", headers=self._entetes(), json=payload, timeout=TIMEOUT)
                r.raise_for_status()
                time.sleep(DELAI_APPELS)
                return r.json()
            except requests.exceptions.RequestException as e:
                if essai == essais:
                    raise
                logger.warning("%s : %s (essai %d/%d)", chemin, e, essai, essais)
                time.sleep(2 ** essai)


def _maintenant_ms():
    return int(time.time() * 1000)


def _date(valeur):
    """Date AAAA-MM-JJ depuis un horodatage en millisecondes ou une chaîne ISO ; None si illisible."""
    try:
        if isinstance(valeur, (int, float)):
            return (datetime(1970, 1, 1) + timedelta(milliseconds=valeur)).strftime("%Y-%m-%d")
        return str(valeur)[:10] if valeur else None
    except (OverflowError, ValueError):
        return None


def _sans_balises(titre):
    return re.sub(r"</?mark>", "", titre or "")


def _titre_loi(titre):
    """Titre du texte sans la mention d'article qui le suit (« … - art. 47 »)."""
    return re.split(r"\s*[-–(,]?\s*art(?:icle|\.)\s*\d", titre or "", maxsplit=1, flags=re.I)[0].strip()


def _articles_de(section):
    """Tous les articles d'une section et de ses sous-sections (nœuds de la table des matières)."""
    articles = list(section.get("articles", []))
    for sous in section.get("sections", []):
        articles.extend(_articles_de(sous))
    return articles


def _article(client, article_id):
    reponse = client.appeler("/consult/getArticle", {"id": article_id})
    return reponse.get("article", reponse)


def _enregistrement(modele, article, num, theme, article_id, etat_noeud=None, **extras):
    return {
        **{k: v for k, v in modele.items() if k != "url_base"},
        "reference": f"{modele['libelle']}, art. {num}",
        "article": num, "article_id": article.get("id") or article_id, "etat": article.get("etat") or etat_noeud,
        "date_debut": _date(article.get("dateDebut")), "date_fin": _date(article.get("dateFin")),
        "theme": theme, "url": f"{modele['url_base']}{article.get('id') or article_id}",
        "texte_brut": str(article.get("texte") or article.get("content") or "").strip(), **extras,
    }


def _collecter_cibles(client, noeuds, cibles, modele, avec_versions=False):
    """Un enregistrement par version retenue (en vigueur, en vigueur différé ou à venir) de chaque article cible.
    Renvoie (enregistrements, manquants) ; un manquant est un numéro absent de l'arbre, quel que soit son état."""
    par_num = {}
    for n in noeuds:
        par_num.setdefault(str(n.get("num", "")).strip(), []).append(n)
    enregistrements, manquants = [], []
    for num, theme in cibles.items():
        if num not in par_num:
            manquants.append(f"{modele['libelle']}, art. {num}")
            continue
        retenus = [n for n in par_num[num] if n.get("etat") in (*ETATS_EN_VIGUEUR, ETAT_A_VENIR)]
        if not retenus:
            logger.info("%s, art. %s : aucune version en vigueur (états %s), écarté", modele["libelle"], num, {n.get("etat") for n in par_num[num]})
        for n in retenus:
            article = _article(client, n["id"])
            extras = {}
            if avec_versions:
                extras["versions"] = [{"id": v["id"], "date_debut": _date(v.get("dateDebut"))} for v in article.get("articleVersions") or [] if v.get("id")]
            enregistrements.append(_enregistrement(modele, article, num, theme, n["id"], etat_noeud=n.get("etat"), **extras))
    return enregistrements, manquants


def _identifier_texte(client, nom, cfg):
    """Identifiant LEGITEXT de la version la plus récente (à ce jour) du texte, retrouvé par recherche de titre.
    Les textes qui « modifient » le texte visé sont écartés par titre_regex, appliqué au titre sans balises <mark>."""
    candidats, page = {}, 1
    while True:
        payload = {
            "fond": "LODA_DATE",
            "recherche": {
                "champs": [{"typeChamp": "TITLE", "criteres": [{"typeRecherche": "TOUS_LES_MOTS_DANS_UN_CHAMP", "valeur": cfg["requete"], "operateur": "ET"}], "operateur": "ET"}],
                "filtres": [], "pageNumber": page, "pageSize": 100, "operateur": "ET", "sort": "PERTINENCE", "typePagination": "DEFAUT",
            },
        }
        reponse = client.appeler("/search", payload)
        resultats = reponse.get("results") or []
        for res in resultats:
            for t in res.get("titles") or []:
                if res.get("nature") == cfg["nature"] and TITRE_REGEX_COMPILES[nom].match(_sans_balises(t.get("title"))):
                    try:
                        candidats[t["id"]] = (datetime.strptime(t["id"].split("_")[1], "%d-%m-%Y"), res.get("etat"))
                    except (IndexError, ValueError):
                        continue
        if not resultats or page * 100 >= (reponse.get("totalResultNumber") or 0):
            break
        page += 1
    valides = {i: v for i, v in candidats.items() if v[0] <= datetime.now()}
    if not valides:
        raise ValueError(f"{nom} : aucune version trouvée dans PISTE")
    texte_id = max(valides, key=lambda i: valides[i][0])
    if valides[texte_id][1] != "VIGUEUR":
        logger.warning("%s : version la plus récente %s à l'état %s", nom, texte_id, valides[texte_id][1])
    logger.info("%s : %d versions, retenue %s", nom, len(valides), texte_id)
    return texte_id


def _structure(client, texte_id):
    """Arbre d'un texte consolidé (lawDecree), avec l'identifiant daté puis sans date."""
    for identifiant in (texte_id, texte_id.split("_")[0]):
        try:
            arbre = client.appeler("/consult/lawDecree", {"textId": identifiant, "date": _maintenant_ms()})
        except requests.exceptions.RequestException:
            continue
        if arbre:
            return arbre
    raise ValueError(f"{texte_id} : structure introuvable (lawDecree)")


def _collecter_textes(client):
    enregistrements, manquants = [], []
    for nom, cfg in TEXTES_LEGI.items():
        texte_id = _identifier_texte(client, nom, cfg)
        noeuds = _articles_de(_structure(client, texte_id))
        cibles = cfg["articles"] or {str(n.get("num", "")).strip(): cfg["theme"] for n in noeuds}
        modele = {"source": "piste", "type_texte": cfg["type_texte"], "texte": nom, "libelle": cfg["libelle"], "id_texte": texte_id, "url_base": URL_LEGIFRANCE_LODA}
        lignes, absents = _collecter_cibles(client, noeuds, cibles, modele)
        logger.info("%s : %d articles collectés", nom, len(lignes))
        enregistrements += lignes
        manquants += absents
    return enregistrements, manquants


def _collecter_code(client, texte_id, nom, libelle, cibles, avec_versions=False):
    arbre = client.appeler("/consult/code/tableMatieres", {"date": _maintenant_ms(), "sctId": "", "textId": texte_id})
    modele = {"source": "piste", "type_texte": "code", "texte": nom, "libelle": libelle, "id_texte": texte_id, "url_base": URL_LEGIFRANCE_CODES}
    lignes, absents = _collecter_cibles(client, _articles_de(arbre), cibles, modele, avec_versions)
    logger.info("%s : %d versions d'articles collectées", nom, len(lignes))
    return lignes, absents


def _liens_lois(client, enregistrements_cgi):
    """Articles de loi qui modifient les articles cibles du CGI depuis ANNEE_LF_MIN (lienModifications des versions),
    regroupés par (loi, article de loi) : un article de loi peut apparaître sous plusieurs identifiants."""
    minimum = f"{ANNEE_LF_MIN}-01-01"
    versions = {}
    for e in enregistrements_cgi:
        versions[e["article_id"]] = (e["article"], e["date_debut"])
        for v in e["versions"]:
            versions[v["id"]] = (e["article"], v["date_debut"])
    liens = {}
    for id_version, (num_cgi, debut) in sorted(versions.items(), key=lambda kv: kv[1][1] or ""):
        if not debut or debut < minimum:
            continue
        for lien in _article(client, id_version).get("lienModifications") or []:
            if lien.get("natureText") != "LOI" or not lien.get("articleId"):
                continue
            loi, article_loi = _titre_loi(lien.get("textTitle")), str(lien.get("articleNum") or "").strip()
            ligne = liens.setdefault((loi, article_loi), {"id": lien["articleId"], "articles_cgi": set(), "effets": set()})
            ligne["articles_cgi"].add(num_cgi)
            if lien.get("dateDebutCible"):
                ligne["effets"].add(_date(lien["dateDebutCible"]))
    return liens


def _lois_de_finances(client, enregistrements_cgi):
    """Texte d'origine au JORF des articles de lois de finances liés aux articles cibles du CGI (R0, bloc 5e)."""
    enregistrements, manquants, arbres = [], [], {}
    for (loi, article_loi), lien in _liens_lois(client, enregistrements_cgi).items():
        titres = [t for t in _article(client, lien["id"]).get("textTitles") or [] if "de finances" in str(t.get("titreLong") or t.get("titre") or "").lower()]
        if not titres:
            logger.info("%s, art. %s : pas une loi de finances, écarté", loi, article_loi)
            continue
        cid = titres[0].get("id")
        if cid not in arbres:
            arbres[cid] = _articles_de(client.appeler("/consult/jorf", {"textCid": cid}))
        noeud = next((n for n in arbres[cid] if str(n.get("num", "")).strip() == article_loi), None)
        if not noeud:
            manquants.append(f"{loi}, art. {article_loi}")
            continue
        modele = {"source": "piste", "type_texte": "loi de finances", "texte": loi, "libelle": loi, "id_texte": cid, "url_base": URL_LEGIFRANCE_JORF}
        enregistrements.append(_enregistrement(
            modele, _article(client, noeud["id"]), article_loi, THEME_LOIS_FINANCES, noeud["id"],
            articles_cgi=sorted(lien["articles_cgi"]), effet=min(lien["effets"]) if lien["effets"] else None,
        ))
    logger.info("Lois de finances : %d articles de loi collectés", len(enregistrements))
    return enregistrements, manquants


def collecter(force=False, env=None):
    """Collecte complète ; renvoie le chemin du JSON. Réutilise le fichier s'il existe, sauf force."""
    chemin = DOSSIER_CORPUS / FICHIER_PISTE_BRUT
    if chemin.exists() and not force:
        logger.info("%s existe déjà (--force pour recollecter)", chemin.name)
        return chemin
    DOSSIER_CORPUS.mkdir(parents=True, exist_ok=True)
    env = env or PISTE_ENV
    client = ClientPiste(env)

    enregistrements, manquants = _collecter_textes(client)
    lignes, absents = _collecter_code(client, CCH_TEXT_ID, "CCH", LIBELLE_CCH, ARTICLES_CCH)
    enregistrements, manquants = enregistrements + lignes, manquants + absents
    cgi, absents = _collecter_code(client, CGI_TEXT_ID, "CGI", LIBELLE_CGI, ARTICLES_CGI, avec_versions=True)
    enregistrements, manquants = enregistrements + cgi, manquants + absents
    lois, absents = _lois_de_finances(client, cgi)
    enregistrements, manquants = enregistrements + lois, manquants + absents

    if manquants:
        raise ValueError("Articles introuvables dans PISTE : " + " ; ".join(manquants))
    for e in enregistrements:
        e.pop("versions", None)  # servait à repérer les lois de finances
    temporaire = chemin.with_suffix(".json.tmp")
    temporaire.write_text(json.dumps(
        {"collecte_le": datetime.now().isoformat(timespec="seconds"), "piste_env": env, "enregistrements": enregistrements},
        ensure_ascii=False, indent=2,
    ), encoding="utf-8")
    temporaire.replace(chemin)
    logger.info("%d enregistrements écrits dans %s : %s", len(enregistrements), chemin.name, dict(Counter(e["type_texte"] for e in enregistrements)))
    return chemin

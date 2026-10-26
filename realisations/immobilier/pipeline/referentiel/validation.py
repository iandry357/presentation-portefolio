"""Contrôle qualité du corpus avant chargement (cahier §6) : lit chunks.json et arrête au premier lot d'erreurs.

Erreurs (arrêt) : métadonnée obligatoire absente, thème inconnu, date ou URL mal formée, identifiant en double, document vide,
article de la liste validée sans chunk, préfixe BOFiP sans chunk. Alertes (journal seulement) : chunk au-delà de
MOTS_MAX_ALERTE ou sous MOTS_MIN_ALERTE mots. Les comptages par type et par thème sont écrits dans les logs.
"""
import json
import logging
import re
from collections import Counter

from pipeline.referentiel.config import (
    ARTICLES_CCH, ARTICLES_CGI, DOSSIER_CORPUS, FICHIER_CHUNKS, LIBELLE_CCH, LIBELLE_CGI, MOTS_MAX_CHUNK, PREFIXES_BOFIP,
    TEXTES_LEGI, THEMES,
)

logger = logging.getLogger(__name__)

CHAMPS_OBLIGATOIRES = ("source", "type_texte", "reference", "theme", "statut", "date_version", "url", "identifiant", "collecte_le")
MOTS_MAX_ALERTE = int(MOTS_MAX_CHUNK * 1.3)
MOTS_MIN_ALERTE = 20
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _references_attendues():
    """Références des articles de la liste explicite validée le 2026-10-25 (textes consolidés, CCH, CGI)."""
    attendues = {f"{cfg['libelle']}, art. {num}" for cfg in TEXTES_LEGI.values() for num in (cfg["articles"] or {})}
    attendues |= {f"{LIBELLE_CCH}, art. {num}" for num in ARTICLES_CCH}
    attendues |= {f"{LIBELLE_CGI}, art. {num}" for num in ARTICLES_CGI}
    return attendues


def valider(chemin=None):
    """Contrôle chunks.json ; renvoie les comptages ou lève ValueError avec la liste des erreurs."""
    chemin = chemin or DOSSIER_CORPUS / FICHIER_CHUNKS
    chunks = json.loads(chemin.read_text(encoding="utf-8"))["chunks"]
    erreurs, alertes = [], []

    erreurs += [f"identifiant en double : {i}" for i, n in Counter(c["id"] for c in chunks).items() if n > 1]
    for c in chunks:
        m = c["metadata"]
        manquants = [k for k in CHAMPS_OBLIGATOIRES if not m.get(k)]
        if manquants:
            erreurs.append(f"{c['id']} : métadonnées manquantes {manquants}")
        if m.get("theme") and m["theme"] not in THEMES:
            erreurs.append(f"{c['id']} : thème inconnu « {m['theme']} »")
        for champ in ("date_version", "date_effet"):
            if m.get(champ) and not _DATE.fullmatch(m[champ]):
                erreurs.append(f"{c['id']} : {champ} illisible « {m[champ]} »")
        if m.get("url") and not m["url"].startswith("http"):
            erreurs.append(f"{c['id']} : URL illisible « {m['url']} »")
        if not c["document"].strip():
            erreurs.append(f"{c['id']} : document vide")
        mots = m.get("mots", 0)
        if mots > MOTS_MAX_ALERTE:
            alertes.append(f"{m['reference']} (partie {m['partie']}/{m['parties']}) : {mots} mots")
        elif mots < MOTS_MIN_ALERTE:
            alertes.append(f"{m['reference']} (partie {m['partie']}/{m['parties']}) : seulement {mots} mots")

    absents = sorted(_references_attendues() - {c["metadata"]["reference"] for c in chunks})
    if absents:
        erreurs.append("articles de la liste validée sans chunk : " + " ; ".join(absents))
    identifiants_bofip = [c["metadata"]["identifiant"] for c in chunks if c["metadata"]["source"] == "bofip"]
    for prefixe in PREFIXES_BOFIP:
        if not any(i == prefixe or i.startswith(prefixe + "-") for i in identifiants_bofip):
            erreurs.append(f"préfixe BOFiP sans chunk : {prefixe}")

    par_type = Counter(c["metadata"]["type_texte"] for c in chunks)
    par_theme = Counter(c["metadata"]["theme"] for c in chunks)
    logger.info("%d chunks, %d mots", len(chunks), sum(c["metadata"]["mots"] for c in chunks))
    logger.info("Par type : %s", dict(par_type))
    logger.info("Par thème : %s", dict(par_theme))
    for alerte in alertes:
        logger.warning("Alerte : %s", alerte)
    if erreurs:
        raise ValueError(f"{len(erreurs)} erreur(s) de validation :\n" + "\n".join(erreurs[:50]))
    return {"chunks": len(chunks), "par_type": dict(par_type), "par_theme": dict(par_theme), "alertes": len(alertes)}

"""Transformation du corpus brut (PISTE + BOFiP) en chunks avec métadonnées obligatoires.

Entrées : DOSSIER_CORPUS/piste_brut.json et bofip_brut.csv. Sortie : DOSSIER_CORPUS/chunks.json, une entrée par chunk
{id, document, metadata}. Les métadonnées sont plates (str / int), sans None : ChromaDB les refuse.
Découpage : 1 chunk = 1 article jusqu'à MOTS_MAX_CHUNK mots ; au-delà, regroupement de segments (I., 1°, a)) puis repli par
phrases. BOFiP : regroupement de paragraphes numérotés (§). Un état PISTE inattendu arrête la transformation.
"""
import json
import logging
import re
from collections import Counter
from datetime import date, datetime

import polars as pl

from pipeline.referentiel.config import (
    DOSSIER_CORPUS, FICHIER_BOFIP_BRUT, FICHIER_CHUNKS, FICHIER_PISTE_BRUT, MOTS_CHUNK_BOFIP, MOTS_MAX_CHUNK,
    PREFIXES_BOFIP, STATUT_EN_VIGUEUR,
)

logger = logging.getLogger(__name__)

# États PISTE acceptés -> statut. INITIALE : article de loi au JORF (texte d'origine). Tout autre état est une erreur.
STATUTS_PISTE = {"VIGUEUR": STATUT_EN_VIGUEUR, "ABROGE_DIFF": STATUT_EN_VIGUEUR, "INITIALE": STATUT_EN_VIGUEUR}

# Marqueurs d'alinéa : chiffres romains (I.), degrés (1°), lettres (a. ou a)), retenus après une frontière de phrase
_MARQUEUR = re.compile(r"(?:(?P<romain>[IVXLCDM]{1,5})\.|(?P<degre>\d{1,2})°|(?P<lettre>[a-h])[\.\)])")
_FRONTIERES = {".", ":", ";"}
_AUTRE_ARTICLE = re.compile(r"articles?\s+\d")
_SUFFIXES = "bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies"
MOTS_MIN_ARTICLE = 20  # article PISTE plus court (formule d'exécution, entrée en vigueur) : écarté
MOTS_MIN_CHUNK = 40  # un chunk plus court est rattaché à son voisin si le résultat reste sous 1,3 × MOTS_MAX_CHUNK
# Numéro de paragraphe BOFiP collé au texte qui suit (« …spéciaux.10Les contribuables »)
_NUMERO = re.compile(r"(?:(?<=[^\s\d])|^)(\d{1,4})(?=[A-ZÉÈÀÂÊÎÔÛÇ«“‘(])")


def _mots(texte):
    return len(texte.split())


def _debuts_de_segments(texte):
    debuts = []
    for m in _MARQUEUR.finditer(texte):
        j = m.start() - 1
        while j >= 0 and texte[j].isspace():
            j -= 1
        if j < 0 or texte[j] in _FRONTIERES:
            debuts.append(m.start())
    return debuts


def _segments(texte):
    """Segments aux marqueurs d'alinéa ; le texte avant le premier marqueur est conservé. Un seul segment si moins de deux marqueurs."""
    debuts = _debuts_de_segments(texte)
    if len(debuts) < 2:
        return [texte]
    bornes = ([0] if debuts[0] > 0 else []) + debuts + [len(texte)]
    return [s for s in (texte[bornes[i]:bornes[i + 1]].strip() for i in range(len(bornes) - 1)) if s]


def _par_mots(texte, seuil):
    """Coupe un texte sans ponctuation exploitable (tableau, annexe) par tranches de seuil mots."""
    mots = texte.split()
    return [" ".join(mots[i:i + seuil]) for i in range(0, len(mots), seuil)]


def _phrases(texte, seuil):
    """Regroupe des phrases consécutives jusqu'à seuil mots ; une phrase plus longue que seuil est coupée par tranches de mots."""
    phrases = [p.strip() for p in re.split(r"(?<=[.!?])\s+", texte) if p.strip()]
    groupes, courant, n = [], [], 0
    for phrase in phrases:
        m = _mots(phrase)
        if m > seuil:
            if courant:
                groupes.append(" ".join(courant))
                courant, n = [], 0
            groupes += _par_mots(phrase, seuil)
            continue
        if courant and n + m > seuil:
            groupes.append(" ".join(courant))
            courant, n = [], 0
        courant.append(phrase)
        n += m
    if courant:
        groupes.append(" ".join(courant))
    return groupes or [texte]


def _assembler(segments, seuil):
    """Regroupe des segments consécutifs sans dépasser seuil mots ; un segment plus long est coupé par phrases."""
    chunks, courant, n = [], [], 0
    for segment in segments:
        m = _mots(segment)
        if m > seuil:
            chunks += _phrases(" ".join([*courant, segment]), seuil)
            courant, n = [], 0
            continue
        if courant and n + m > seuil:
            chunks.append(" ".join(courant))
            courant, n = [], 0
        courant.append(segment)
        n += m
    if courant:
        chunks.append(" ".join(courant))
    return chunks


def _fusionner_petits(chunks, seuil):
    """Rattache un chunk de moins de MOTS_MIN_CHUNK mots à son voisin si le résultat reste sous 1,3 × seuil."""
    fusionnes = []
    for chunk in chunks:
        if (
            fusionnes and (_mots(chunk) < MOTS_MIN_CHUNK or _mots(fusionnes[-1]) < MOTS_MIN_CHUNK)
            and _mots(fusionnes[-1]) + _mots(chunk) <= 1.3 * seuil
        ):
            fusionnes[-1] = f"{fusionnes[-1]} {chunk}"
        else:
            fusionnes.append(chunk)
    return fusionnes


def decouper(texte, seuil=MOTS_MAX_CHUNK):
    return [texte] if _mots(texte) <= seuil else _fusionner_petits(_assembler(_segments(texte), seuil), seuil)


def _motif_cible(articles_cgi):
    """Citation d'un des articles cibles du CGI (« article 31 », « articles 156 », « article 39 C »), hors « 31 bis », « 31-2 »."""
    alternatives = "|".join(re.escape(n) for n in articles_cgi)
    return re.compile(rf"articles?\s+(?:{alternatives})(?![\w-])(?!\s+(?:{_SUFFIXES}))")


_BLOCS_LETTRES = r"(?<=[.:;])\s+(?=[A-H]\.\s?[-―–])"
_BLOCS_DEGRES = r"(?<=[.:;])\s+(?=\d{1,2}°\s)"


_BLOCS_LETTRES = r"(?<=[.:;])\s+(?=[A-H]\.\s?[-―–])"
_BLOCS_DEGRES = r"(?<=[.:;])\s+(?=\d{1,2}°\s)"


def _decisions(blocs, cible):
    """True (garder) / False (écarter) par bloc, ou None si aucun bloc ne cite une cible. Bloc qui cite une cible : gardé ;
    qui cite seulement d'autres articles : écarté ; sans citation : hérite du bloc précédent (les premiers suivent le premier décisif)."""
    decisions = [True if cible.search(b) else (False if _AUTRE_ARTICLE.search(b) else None) for b in blocs]
    if True not in decisions:
        return None
    courant, gardes = next(d for d in decisions if d is not None), []
    for d in decisions:
        courant = courant if d is None else d
        gardes.append(courant)
    return gardes


def _filtrer_loi_finances(e):
    """Texte d'un article de loi de finances réduit aux blocs qui concernent les articles cibles du CGI. Blocs « A.- », « B.- »
    s'il y en a au moins deux, sinon « 1° », « 2° »… Dans un bloc « A.- » dont l'en-tête ne cite aucune cible (« I.- Le code
    général des impôts est ainsi modifié : »), on affine par « 1° », « 2° »… ; si l'en-tête cite une cible, tout le bloc est gardé."""
    texte = e["texte_brut"]
    if _mots(texte) <= MOTS_MAX_CHUNK:
        return texte
    cible = _motif_cible(e["articles_cgi"])
    blocs, par_lettres = re.split(_BLOCS_LETTRES, texte), True
    if len(blocs) < 3:
        blocs, par_lettres = re.split(_BLOCS_DEGRES, texte), False
    gardes = _decisions(blocs, cible)
    if gardes is None:
        logger.warning("%s : aucun bloc ne cite %s, article gardé entier", e["reference"], e["articles_cgi"])
        return texte
    retenus = []
    for bloc, garde in zip(blocs, gardes):
        if not garde:
            logger.debug("  écarté : %s…", bloc[:80])
            continue
        sous = re.split(_BLOCS_DEGRES, bloc)
        if par_lettres and len(sous) >= 3 and not cible.search(sous[0]):
            affines = _decisions(sous, cible)
            if affines is not None:
                bloc = " ".join(s for s, g in zip(sous, affines) if g)
        retenus.append(bloc)
    retenu = " ".join(retenus)
    logger.info("%s : %d mots gardés sur %d (%d blocs)", e["reference"], _mots(retenu), _mots(texte), len(blocs))
    return retenu


def _entete(reference, theme, complement="", partie=0, parties=1):
    suffixe = f" (partie {partie}/{parties})" if parties > 1 else ""
    return f"{reference}{suffixe} — {theme.replace('_', ' ')}{complement}"


def _chunks_piste(enregistrements, collecte_le):
    chunks = []
    for e in enregistrements:
        statut = STATUTS_PISTE.get(e["etat"])
        if statut is None:
            raise ValueError(f"{e['reference']} : état PISTE inattendu « {e['etat']} »")
        if _mots(e["texte_brut"]) < MOTS_MIN_ARTICLE:
            logger.info("%s : %d mots, écarté (formule d'exécution ou d'entrée en vigueur)", e["reference"], _mots(e["texte_brut"]))
            continue
        loi_finances = e["type_texte"] == "loi de finances"
        texte = _filtrer_loi_finances(e) if loi_finances else e["texte_brut"]
        date_version = (e.get("effet") if loi_finances else e["date_debut"]) or ""
        valable_jusqua = e["date_fin"] if e["etat"] == "ABROGE_DIFF" else ""
        complement = ""
        if loi_finances:
            complement = f" (modifie l'article {', '.join(e['articles_cgi'])} du CGI, effet {date_version})"
        elif valable_jusqua:
            complement = f" (en vigueur jusqu'au {valable_jusqua})"
        parties = decouper(texte)
        for i, partie in enumerate(parties, start=1):
            chunks.append({
                "id": f"{e['article_id']}_{i}",
                "document": f"{_entete(e['reference'], e['theme'], complement, i, len(parties))}\n\n{partie}",
                "metadata": {
                    "source": "piste", "type_texte": e["type_texte"], "reference": e["reference"], "theme": e["theme"],
                    "statut": statut, "date_version": date_version, "date_effet": date_version, "valable_jusqu_au": valable_jusqua,
                    "url": e["url"], "identifiant": e["article_id"], "texte": e["texte"],
                    "articles_cgi": ", ".join(e.get("articles_cgi") or []), "partie": i, "parties": len(parties),
                    "mots": _mots(partie), "collecte_le": collecte_le,
                },
            })
    return chunks


def _paragraphes(contenu):
    """[(numéro, texte)] : paragraphes numérotés (§) d'un document BOFiP. Numéros acceptés dans l'ordre : 1 ou 10 en premier,
    puis un multiple de 10 supérieur au précédent, d'au plus 50. Le texte avant le premier numéro est rattaché au § 1."""
    contenu = re.sub(r"\[node:[^\]]*\]\s*:?\s*", "", contenu).strip()
    marques, dernier = [], None
    for m in _NUMERO.finditer(contenu):
        valeur = int(m.group(1))
        ok = valeur in (1, 10) if dernier is None else (dernier < valeur <= dernier + 50 and valeur % 10 == 0)
        if ok:
            marques.append((valeur, m.start(), m.end()))
            dernier = valeur
    if not marques:
        return [(1, contenu)]
    paragraphes = [
        [valeur, contenu[fin:marques[i + 1][1] if i + 1 < len(marques) else len(contenu)].strip()]
        for i, (valeur, _, fin) in enumerate(marques)
    ]
    avant = contenu[:marques[0][1]].strip()
    if avant:
        if marques[0][0] == 1:
            paragraphes[0][1] = f"{avant} {paragraphes[0][1]}"
        else:
            paragraphes.insert(0, [1, avant])
    return [(valeur, texte) for valeur, texte in paragraphes if texte]


def _chunks_bofip(df, collecte_le):
    chunks = []
    for ligne in df.iter_rows(named=True):
        groupes, courant, n = [], [], 0
        for numero, texte in _paragraphes(ligne["contenu"]):
            m = _mots(texte)
            if m > MOTS_MAX_CHUNK:  # paragraphe trop long : coupé par phrases, même numéro
                if courant:
                    groupes.append(courant)
                    courant, n = [], 0
                groupes += [[(numero, partie)] for partie in _phrases(texte, MOTS_MAX_CHUNK)]
                continue
            if courant and (n >= MOTS_CHUNK_BOFIP or n + m > MOTS_MAX_CHUNK):
                groupes.append(courant)
                courant, n = [], 0
            courant.append((numero, texte))
            n += m
        if courant:
            groupes.append(courant)
        identifiant, theme = ligne["identifiant_juridique"], PREFIXES_BOFIP[ligne["prefixe"]]
        for i, groupe in enumerate(groupes, start=1):
            premier, dernier = groupe[0][0], groupe[-1][0]
            rang = f"§ {premier}" if premier == dernier else f"§ {premier} à {dernier}"
            reference = f"{identifiant}, {rang}"
            texte = " ".join(t for _, t in groupe)
            chunks.append({
                "id": f"bofip:{identifiant}:{i}",
                "document": f"{_entete(reference, theme, ' — ' + ligne['titre'])}\n\n{texte}",
                "metadata": {
                    "source": "bofip", "type_texte": "BOFiP", "reference": reference, "theme": theme,
                    "statut": STATUT_EN_VIGUEUR, "date_version": ligne["debut_de_validite"], "date_effet": ligne["debut_de_validite"],
                    "valable_jusqu_au": "", "url": ligne["permalien"], "identifiant": identifiant, "texte": ligne["titre"],
                    "articles_cgi": "", "partie": i, "parties": len(groupes), "mots": _mots(texte), "collecte_le": collecte_le,
                },
            })
    return chunks


def transformer():
    """Transforme les deux collectes en chunks ; renvoie le chemin de chunks.json."""
    chemin_piste, chemin_bofip = DOSSIER_CORPUS / FICHIER_PISTE_BRUT, DOSSIER_CORPUS / FICHIER_BOFIP_BRUT
    for chemin in (chemin_piste, chemin_bofip):
        if not chemin.exists():
            raise FileNotFoundError(f"{chemin} introuvable : lancer d'abord la collecte")
    brut = json.loads(chemin_piste.read_text(encoding="utf-8"))
    chunks = _chunks_piste(brut["enregistrements"], brut["collecte_le"][:10])
    bofip = pl.read_csv(chemin_bofip, separator=";", infer_schema_length=0).with_columns(pl.col("contenu").fill_null(""))
    chunks += _chunks_bofip(bofip, date.fromtimestamp(chemin_bofip.stat().st_mtime).isoformat())

    sortie = DOSSIER_CORPUS / FICHIER_CHUNKS
    sortie.write_text(json.dumps(
        {"genere_le": datetime.now().isoformat(timespec="seconds"), "chunks": chunks}, ensure_ascii=False, indent=2,
    ), encoding="utf-8")
    logger.info("%d chunks écrits dans %s : %s", len(chunks), sortie.name, dict(Counter(c["metadata"]["type_texte"] for c in chunks)))
    return sortie

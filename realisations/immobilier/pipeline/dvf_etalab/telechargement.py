import csv
import gzip
import hashlib
import json
import logging
from datetime import datetime

import requests

from pipeline.dvf_etalab.config import DOSSIER_DVF, LIVRAISONS, TIMEOUT

logger = logging.getLogger(__name__)


def _sha1(chemin):
    sha = hashlib.sha1()
    with open(chemin, "rb") as f:
        for morceau in iter(lambda: f.read(1 << 20), b""):
            sha.update(morceau)
    return sha.hexdigest()


def _telecharger(url, cible, sha1_attendu):
    """Téléchargement en flux dans un fichier temporaire, renommé seulement si le sha1 correspond au sha1 publié."""
    temporaire = cible.with_suffix(cible.suffix + ".tmp")
    sha = hashlib.sha1()
    try:
        with requests.get(url, timeout=TIMEOUT, stream=True) as r:
            r.raise_for_status()
            with open(temporaire, "wb") as f:
                for morceau in r.iter_content(chunk_size=1 << 20):
                    f.write(morceau)
                    sha.update(morceau)
        if sha.hexdigest() != sha1_attendu:
            raise ValueError(f"{url} : sha1 {sha.hexdigest()} différent du sha1 publié {sha1_attendu}")
        temporaire.replace(cible)
    finally:
        temporaire.unlink(missing_ok=True)


def _filtrer(brut, cible, departement):
    """Copie en flux les lignes du département (colonne code_departement) d'un fichier national. Retourne leur nombre."""
    temporaire = cible.with_suffix(".csv.tmp")
    nb = 0
    try:
        with gzip.open(brut, "rt", encoding="utf-8", newline="") as entree, \
                open(temporaire, "w", encoding="utf-8", newline="") as sortie:
            lecteur, ecrivain = csv.reader(entree), csv.writer(sortie)
            entete = next(lecteur)
            ecrivain.writerow(entete)
            colonne = entete.index("code_departement")
            for ligne in lecteur:
                if ligne[colonne] == departement:
                    ecrivain.writerow(ligne)
                    nb += 1
        temporaire.replace(cible)
    finally:
        temporaire.unlink(missing_ok=True)
    return nb


def _compter(chemin):
    with open(chemin, encoding="utf-8", newline="") as f:
        return sum(1 for _ in csv.reader(f)) - 1  # sans l'en-tête


def preparer(livraison, departement, force=False):
    """Fichiers nationaux de la livraison (téléchargés si absents, sha1 vérifié) puis filtrés sur le département.
    Retourne {étiquette : {chemin, sha1, lignes, taille_octets}}."""
    fichiers = LIVRAISONS[livraison]["fichiers"]
    dossier = DOSSIER_DVF / livraison
    dossier_brut = dossier / "brut"
    dossier_filtre = dossier / departement
    dossier_brut.mkdir(parents=True, exist_ok=True)
    dossier_filtre.mkdir(parents=True, exist_ok=True)

    resultats = {}
    for etiquette, source in fichiers.items():
        brut = dossier_brut / f"{etiquette}.csv.gz"
        filtre = dossier_filtre / f"{etiquette}.csv"
        if force or not brut.exists():
            logger.info("%s : téléchargement", etiquette)
            _telecharger(source["url"], brut, source["sha1"])
        elif _sha1(brut) != source["sha1"]:
            raise ValueError(f"{brut} : sha1 différent du sha1 publié (relancer avec --force)")

        nb = _compter(filtre) if filtre.exists() and not force else _filtrer(brut, filtre, departement)
        attendu = source["lignes"].get(departement)
        if attendu is not None and nb != attendu:
            raise ValueError(f"{etiquette} (département {departement}) : {nb} lignes au lieu de {attendu}")
        if attendu is None:
            logger.info("%s : nombre de lignes non contrôlé (valeur attendue à renseigner dans config.py)", etiquette)
        resultats[etiquette] = {
            "chemin": filtre, "sha1": source["sha1"], "lignes": nb, "taille_octets": brut.stat().st_size,
        }
        logger.info("%s : %d lignes pour le département %s", etiquette, nb, departement)

    manifeste = {
        etiquette: {"url": fichiers[etiquette]["url"], **{k: v for k, v in r.items() if k != "chemin"}}
        for etiquette, r in resultats.items()
    }
    manifeste["prepare_le"] = datetime.now().isoformat(timespec="seconds")
    (dossier_filtre / "manifeste.json").write_text(json.dumps(manifeste, indent=2, ensure_ascii=False), encoding="utf-8")
    return resultats

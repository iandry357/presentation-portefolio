import csv
import hashlib
import json
import logging
from datetime import datetime

import requests

from pipeline.loyers.config import (
    DOSSIER_LOYERS, FICHIER_CSV, FICHIER_MANIFESTE, PARAMETRES_EXPORT, TIMEOUT, URL_BASE, URL_EXPORT,
)

logger = logging.getLogger(__name__)


def _sha1(chemin):
    sha = hashlib.sha1()
    with open(chemin, "rb") as f:
        for morceau in iter(lambda: f.read(1 << 20), b""):
            sha.update(morceau)
    return sha.hexdigest()


def _metadonnees():
    """Date de mise à jour et nombre d'enregistrements publiés par le jeu (champ metas.default)."""
    r = requests.get(URL_BASE, timeout=TIMEOUT)
    r.raise_for_status()
    meta = r.json()["metas"]["default"]
    return {"modifie_le": meta["modified"], "traite_le": meta["data_processed"], "lignes_publiees": meta["records_count"]}


def _telecharger(cible):
    """Téléchargement en flux dans un fichier temporaire, renommé une fois complet."""
    temporaire = cible.with_suffix(cible.suffix + ".tmp")
    try:
        with requests.get(URL_EXPORT, params=PARAMETRES_EXPORT, timeout=TIMEOUT, stream=True) as r:
            r.raise_for_status()
            with open(temporaire, "wb") as f:
                for morceau in r.iter_content(chunk_size=1 << 20):
                    f.write(morceau)
        temporaire.replace(cible)
    finally:
        temporaire.unlink(missing_ok=True)


def _compter(chemin):
    with open(chemin, encoding="utf-8", newline="") as f:
        return sum(1 for _ in csv.reader(f, delimiter=";")) - 1  # sans l'en-tête


def preparer(force=False):
    """CSV du jeu (téléchargé s'il est absent), dont le nombre de lignes est contrôlé contre les métadonnées publiées.
    Retourne {chemin, sha1, lignes, taille_octets, modifie_le, traite_le}."""
    DOSSIER_LOYERS.mkdir(parents=True, exist_ok=True)
    meta = _metadonnees()
    chemin = DOSSIER_LOYERS / FICHIER_CSV
    if force or not chemin.exists():
        logger.info("Téléchargement de %s", URL_EXPORT)
        _telecharger(chemin)

    lignes = _compter(chemin)
    if lignes != meta["lignes_publiees"]:
        raise ValueError(f"{chemin.name} : {lignes} lignes au lieu de {meta['lignes_publiees']} publiées (relancer avec --force)")
    resultat = {
        "chemin": chemin, "sha1": _sha1(chemin), "lignes": lignes, "taille_octets": chemin.stat().st_size,
        "modifie_le": meta["modifie_le"], "traite_le": meta["traite_le"],
    }
    manifeste = {"url": URL_EXPORT, **{k: v for k, v in resultat.items() if k != "chemin"}}
    manifeste["prepare_le"] = datetime.now().isoformat(timespec="seconds")
    (DOSSIER_LOYERS / FICHIER_MANIFESTE).write_text(json.dumps(manifeste, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("%s : %d lignes, mis à jour le %s", chemin.name, lignes, meta["modifie_le"][:10])
    return resultat

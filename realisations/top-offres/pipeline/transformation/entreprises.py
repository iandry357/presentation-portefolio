import logging
import re
import unicodedata
from datetime import datetime, timezone

from pipeline import config
from pipeline.collectors import entreprises_collector, exclues_collector
from pipeline.loaders import bigquery_loader

logger = logging.getLogger(__name__)

SEUIL_CONFIANCE = 0.7
CONFIANCE_AMBIGUE_MAX = 0.5
NAF_INTERMEDIAIRE = "78.10Z"
NAF_HOLDING = "70.10Z"
RANG_TAILLE = {"GE": 3, "ETI": 2, "PME": 1}

SECTIONS_NAF = {
    "A": "Agriculture, sylviculture et pêche",
    "B": "Industries extractives",
    "C": "Industrie manufacturière",
    "D": "Production et distribution d'électricité, de gaz, de vapeur et d'air conditionné",
    "E": "Production et distribution d'eau ; assainissement, gestion des déchets et dépollution",
    "F": "Construction",
    "G": "Commerce ; réparation d'automobiles et de motocycles",
    "H": "Transports et entreposage",
    "I": "Hébergement et restauration",
    "J": "Information et communication",
    "K": "Activités financières et d'assurance",
    "L": "Activités immobilières",
    "M": "Activités spécialisées, scientifiques et techniques",
    "N": "Activités de services administratifs et de soutien",
    "O": "Administration publique",
    "P": "Enseignement",
    "Q": "Santé humaine et action sociale",
    "R": "Arts, spectacles et activités récréatives",
    "S": "Autres activités de services",
    "T": "Activités des ménages en tant qu'employeurs",
    "U": "Activités extra-territoriales",
}


def normaliser(texte: str | None) -> str:
    """Même règle que la macro dbt `normaliser` (dbt/macros/normaliser.sql) : à garder synchronisées."""
    if not texte:
        return ""
    decompose = unicodedata.normalize("NFD", texte.lower())
    sans_accents = "".join(c for c in decompose if not unicodedata.category(c).startswith("M"))
    sans_genre = re.sub(r"\b(h|f|m)\s*[/-]\s*(h|f)(\s*[/-]\s*(x|d|nb))?\b", " ", sans_accents)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", sans_genre)).strip()


def est_intermediaire_connu(nom_normalise: str, intermediaires: set[str]) -> bool:
    return any(nom_normalise == i or nom_normalise.startswith(i + " ") for i in intermediaires)


def _score_nom(nom_normalise: str, candidat: dict) -> float:
    """1,0 : nom identique ; 0,85 : tous les mots de l'un dans l'autre ; sinon similarité de mots (Jaccard)."""
    jetons_offre = set(nom_normalise.split())
    meilleur = 0.0
    for nom in (candidat.get("nom_complet"), candidat.get("nom_raison_sociale"), candidat.get("sigle")):
        nom_candidat = normaliser(nom)
        jetons = set(nom_candidat.split())
        if not jetons or not jetons_offre:
            continue
        if nom_candidat == nom_normalise:
            return 1.0
        if jetons_offre <= jetons or jetons <= jetons_offre:
            meilleur = max(meilleur, 0.85)
        else:
            meilleur = max(meilleur, len(jetons_offre & jetons) / len(jetons_offre | jetons))
    return meilleur


def _est_candidat_valide(candidat: dict) -> bool:
    """Établissement actif et personne morale (les entrepreneurs individuels, nature juridique 1xxx, sont écartés)."""
    return (
        candidat.get("etat_administratif") == "A"
        and not str(candidat.get("nature_juridique") or "").startswith("1")
    )


def _rang_taille(candidat: dict) -> int:
    return RANG_TAILLE.get(candidat.get("categorie_entreprise"), 0)


def choisir_candidat(nom_normalise: str, departement: str | None, candidats: list[dict]) -> tuple[dict | None, float]:
    valides = [c for c in candidats if _est_candidat_valide(c)]
    if not valides:
        return None, 0.0
    notes = [(_score_nom(nom_normalise, c), c) for c in valides]
    meilleur = max(note for note, _ in notes)
    if meilleur < SEUIL_CONFIANCE:
        return None, meilleur
    ex_aequo = [c for note, c in notes if note == meilleur]
    taille_max = max(_rang_taille(c) for c in ex_aequo)
    finalistes = [c for c in ex_aequo if _rang_taille(c) == taille_max]
    choisi = max(finalistes, key=lambda c: (c.get("siege") or {}).get("departement") == departement)
    confiance = meilleur
    if len({c.get("activite_principale") for c in finalistes}) > 1:
        confiance = min(confiance, CONFIANCE_AMBIGUE_MAX)
    return choisi, confiance


def enrichir_entreprise(entreprise: dict, intermediaires: set[str]) -> dict:
    """Ligne entreprises_ref pour une entreprise {nom_normalise, nom_source, departement}.
    Lève ErreurAPIEntreprises si l'API est inutilisable (rien n'est alors mis en cache)."""
    nom_normalise = entreprise["nom_normalise"]
    ligne = {
        "nom_normalise": nom_normalise,
        "nom_source": entreprise["nom_source"],
        "siren": None,
        "naf_code": None,
        "naf_libelle": None,
        "categorie": None,
        "tranche_effectif": None,
        "type_annonceur": "inconnu",
        "origine": "non_trouve",
        "confiance": 0.0,
        "maj_le": datetime.now(timezone.utc).isoformat(),
    }
    if est_intermediaire_connu(nom_normalise, intermediaires):
        return {**ligne, "type_annonceur": "intermediaire", "origine": "dictionnaire", "confiance": 1.0}

    candidats = entreprises_collector.rechercher(entreprise["nom_source"])
    candidat, confiance = choisir_candidat(nom_normalise, entreprise.get("departement"), candidats)
    if candidat is None or confiance < SEUIL_CONFIANCE:
        return {**ligne, "confiance": confiance}

    naf = candidat.get("activite_principale")
    ligne.update(
        siren=candidat.get("siren"),
        categorie=candidat.get("categorie_entreprise"),
        tranche_effectif=candidat.get("tranche_effectif_salarie"),
        type_annonceur="intermediaire" if naf == NAF_INTERMEDIAIRE else "employeur_direct",
        origine="api",
        confiance=confiance,
    )
    if naf != NAF_HOLDING:  # NAF d'une holding : domaine d'activité non exploité
        ligne["naf_code"] = naf
        ligne["naf_libelle"] = SECTIONS_NAF.get(candidat.get("section_activite_principale"))
    return ligne


def enrichir_entreprises(entreprises: list[dict]) -> dict:
    """Enrichit les entreprises absentes du cache (ou trop anciennes), dans l'ordre fourni, dans la limite de
    MAX_APPELS_API_PAR_RUN appels à l'API. Les intermédiaires du seed ne comptent pas dans le plafond."""
    en_cache = bigquery_loader.lire_cles_en_cache(
        [e["nom_normalise"] for e in entreprises if e["nom_normalise"]], config.CACHE_ENTREPRISE_JOURS
    )
    intermediaires = bigquery_loader.lire_intermediaires()
    a_traiter = [e for e in entreprises if e["nom_normalise"] and e["nom_normalise"] not in en_cache]

    lignes, nb_appels, nb_erreurs, nb_reportees = [], 0, 0, 0
    for entreprise in a_traiter:
        connue = est_intermediaire_connu(entreprise["nom_normalise"], intermediaires)
        if not connue:
            if nb_appels >= config.MAX_APPELS_API_PAR_RUN:
                nb_reportees += 1
                continue
            nb_appels += 1
        try:
            lignes.append(enrichir_entreprise(entreprise, intermediaires))
        except entreprises_collector.ErreurAPIEntreprises as e:
            nb_erreurs += 1
            logger.warning("Entreprise '%s' non enrichie : %s", entreprise["nom_source"], e)

    bigquery_loader.ecrire_entreprises_ref(lignes)
    bilan = {
        "demandees": len(entreprises),
        "en_cache": len(entreprises) - len(a_traiter),
        "enrichies": len(lignes),
        "appels_api": nb_appels,
        "reportees": nb_reportees,
        "erreurs": nb_erreurs,
    }
    logger.info("Entreprises : %s", bilan)
    return bilan


def construire_lignes_exclues(noms: list[str]) -> list[dict]:
    synchronise_le = datetime.now(timezone.utc).isoformat()
    return [{"nom": nom, "nom_normalise": normaliser(nom), "synchronise_le": synchronise_le} for nom in noms]


def synchroniser_exclues() -> int:
    """Copie la liste GCS dans top_offres.entreprises_exclues (table remplacée à chaque run)."""
    lignes = construire_lignes_exclues(exclues_collector.lire_exclues())
    bigquery_loader.remplacer_exclues(lignes)
    return len(lignes)

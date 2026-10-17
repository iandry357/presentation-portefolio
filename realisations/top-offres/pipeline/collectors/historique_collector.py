import logging
import re
from collections import Counter

import psycopg2

from pipeline import config
from pipeline.transformation.entreprises import normaliser

logger = logging.getLogger(__name__)

STATUTS_POSITIFS = ("postule", "enregistre")


def _departement(code_postal: str | None) -> str | None:
    """Deux premiers chiffres d'un code postal à 5 chiffres, sinon None."""
    code = (code_postal or "").strip()
    return code[:2] if re.fullmatch(r"\d{5}", code) else None


def lire_positifs() -> list[dict]:
    """Offres de job_offers au statut postule ou enregistre (lecture seule), au format des offres à scorer.
    id_unique = 'pg-<id>' ; `statut` et `source` (normalisée) servent au rapport d'évaluation."""
    conn = psycopg2.connect(
        host=config.PG_HOST,
        port=config.PG_PORT,
        dbname=config.PG_DB,
        user=config.PG_USER,
        password=config.PG_PASSWORD,
        sslmode="require",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, status, source_offer, title, company_name, location_label, location_postal_code, "
                "contract_type, contract_label, salary_label "
                "FROM job_offers WHERE status = ANY(%s) ORDER BY id",
                (list(STATUTS_POSITIFS),),
            )
            colonnes = [c[0] for c in cur.description]
            lignes = [dict(zip(colonnes, ligne)) for ligne in cur.fetchall()]
    finally:
        conn.close()

    positifs = []
    for ligne in lignes:
        positifs.append({
            "id_unique": f"pg-{ligne['id']}",
            "statut": ligne["status"],
            "source": re.sub(r"\d+", "", normaliser(ligne["source_offer"])).strip() or "inconnue",
            "titre": ligne["title"],
            "entreprise_nom": ligne["company_name"],
            "entreprise_normalise": normaliser(ligne["company_name"]),
            "localisation_libelle": ligne["location_label"],
            "departement": _departement(ligne["location_postal_code"]),
            "type_contrat": ligne["contract_type"],
            "type_contrat_libelle": ligne["contract_label"],
            "contrat": " / ".join(filter(None, [ligne["contract_type"], ligne["contract_label"]])),
            "salaire_libelle": ligne["salary_label"],
        })
    logger.info("Positifs lus : %d %s", len(positifs), dict(Counter(p["statut"] for p in positifs)))
    return positifs

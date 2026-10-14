import logging

import psycopg2

from pipeline import config

logger = logging.getLogger(__name__)


def collecter_experiences() -> list[dict]:
    """Lit la table experiences (lecture seule), de la plus récente à la plus ancienne."""
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
                "SELECT role, start_date, end_date, context, technologies "
                "FROM experiences ORDER BY start_date DESC"
            )
            colonnes = [c[0] for c in cur.description]
            experiences = [dict(zip(colonnes, ligne)) for ligne in cur.fetchall()]
    finally:
        conn.close()
    logger.info("Profil : %d expériences lues", len(experiences))
    return experiences


def construire_texte_profil(experiences: list[dict]) -> str:
    """Texte profil transmis au LLM (l'entreprise est volontairement exclue)."""
    blocs = []
    for exp in experiences:
        debut = str(exp["start_date"]) if exp["start_date"] else "?"
        fin = str(exp["end_date"]) if exp["end_date"] else "aujourd'hui"
        technologies = ", ".join(exp["technologies"]) if exp["technologies"] else "non précisées"
        blocs.append(
            f"[EXPERIENCE] {exp['role']}\n"
            f"Période : {debut} à {fin}\n"
            f"Contexte : {exp['context'] or ''}\n"
            f"Technologies : {technologies}"
        )
    return "\n\n".join(blocs)

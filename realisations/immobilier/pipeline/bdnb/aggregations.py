import logging

from google.cloud import bigquery

from pipeline.bdnb.config import (
    AGG_DEPERDITIONS, AGG_GEOCODAGE, AGG_PARC_ENERGIE, AGG_PARC_PERIODE, AGG_STATS,
    BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH, POSTES_DEPERDITION,
)

logger = logging.getLogger(__name__)


def _client():
    return bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)


def _table(nom):
    return f"`{GCP_PROJECT_ID}.{BQ_DATASET}.{nom}`"


def _une_ligne(requete):
    return next(iter(_client().query(requete).result()))


def _creer_table(nom, requete):
    """Crée ou remplace une table à partir d'une requête SELECT. Retourne le nombre de lignes."""
    client = _client()
    client.query(f"CREATE OR REPLACE TABLE {_table(nom)} AS {requete}").result()
    nb_lignes = client.get_table(f"{GCP_PROJECT_ID}.{BQ_DATASET}.{nom}").num_rows
    logger.info("Table agrégée %s : %d lignes", nom, nb_lignes)
    return nb_lignes


def construire_agg_parc():
    """Parc DPE retenu : période x étiquette, énergie de chauffage x étiquette, déperditions par poste et période."""
    dpe = _table("bdnb_dpe_logement")
    _creer_table(AGG_PARC_PERIODE, f"""
        SELECT
            periode_construction_dpe AS periode_construction,
            classe_bilan_dpe AS etiquette,
            COUNT(*) AS nb_dpe,
            CURRENT_TIMESTAMP() AS date_maj
        FROM {dpe}
        GROUP BY periode_construction, etiquette
    """)
    _creer_table(AGG_PARC_ENERGIE, f"""
        SELECT
            COALESCE(type_energie_chauffage, 'non renseigné') AS energie_chauffage,
            classe_bilan_dpe AS etiquette,
            COUNT(*) AS nb_dpe,
            CURRENT_TIMESTAMP() AS date_maj
        FROM {dpe}
        GROUP BY energie_chauffage, etiquette
    """)

    # Déperditions : part moyenne de chaque poste, sur les logements dont les 6 postes sont renseignés
    colonnes = list(POSTES_DEPERDITION.values())
    renseignes = " AND ".join(f"{c} IS NOT NULL" for c in colonnes)
    postes = ", ".join(f"STRUCT('{poste}' AS poste, {col} AS valeur)" for poste, col in POSTES_DEPERDITION.items())
    ligne = _une_ligne(f"SELECT COUNTIF({renseignes}) AS retenus, COUNT(*) AS total FROM {dpe}")
    logger.info(
        "Déperditions : %d logements sur %d avec les %d postes renseignés",
        ligne["retenus"], ligne["total"], len(colonnes),
    )
    return _creer_table(AGG_DEPERDITIONS, f"""
        WITH logements AS (
            SELECT periode_construction_dpe AS periode_construction, {", ".join(colonnes)},
                   {" + ".join(colonnes)} AS total
            FROM {dpe}
            WHERE {renseignes}
        )
        SELECT
            periode_construction,
            p.poste,
            COUNT(*) AS nb_logements,
            ROUND(AVG(p.valeur / total), 4) AS part_moyenne,
            CURRENT_TIMESTAMP() AS date_maj
        FROM logements, UNNEST([{postes}]) AS p
        WHERE total > 0
        GROUP BY periode_construction, p.poste
    """)


def construire_agg_stats():
    """Fiabilité du géocodage des liens DPE vers bâtiment, et compteurs du bandeau."""
    _creer_table(AGG_GEOCODAGE, f"""
        SELECT
            COALESCE(fiabilite_geocodage, 'non renseigné') AS fiabilite,
            COALESCE(type_appariement, 'non renseigné') AS appariement,
            COUNT(*) AS nb_liens,
            CURRENT_TIMESTAMP() AS date_maj
        FROM {_table("bdnb_rel_dpe_batiment")}
        GROUP BY fiabilite, appariement
    """)
    return _creer_table(AGG_STATS, f"""
        SELECT
            (SELECT COUNT(*) FROM {_table("bdnb_batiment_groupe")}) AS nb_batiments,
            (SELECT COUNT(*) FROM {_table("bdnb_dpe_logement")}) AS nb_dpe,
            (SELECT COUNT(*) FROM {_table("bdnb_adresse")}) AS nb_adresses,
            CURRENT_TIMESTAMP() AS date_maj
    """)


def construire_agregats():
    construire_agg_parc()
    construire_agg_stats()

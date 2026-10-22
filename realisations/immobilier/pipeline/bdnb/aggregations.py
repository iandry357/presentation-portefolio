import logging

from google.cloud import bigquery

from pipeline.bdnb.config import (
    AGG_DEPERDITIONS, AGG_GEOCODAGE, AGG_PARC_ENERGIE, AGG_PARC_PERIODE, AGG_PRIX_DPE, AGG_PRIX_ECART, AGG_STATS,
    BQ_DATASET, DATE_VENTE_MIN, GCP_PROJECT_ID, GCP_SA_KEY_PATH, POSTES_DEPERDITION, PRIX_M2_MAX, PRIX_M2_MIN,
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


def _ventes_par_classe():
    """CTE : une ligne par vente retenue (depuis DATE_VENTE_MIN, prix dans les bornes) avec la classe médiane
    des DPE de son bâtiment. Médiane basse : pour un nombre pair de DPE, la meilleure des deux classes centrales."""
    return f"""
        WITH classe_batiment AS (
            SELECT r.batiment_groupe_id,
                   ARRAY_AGG(d.classe_bilan_dpe ORDER BY d.classe_bilan_dpe) AS classes
            FROM {_table("bdnb_rel_dpe_batiment")} r
            JOIN {_table("bdnb_dpe_logement")} d USING (identifiant_dpe)
            WHERE d.classe_bilan_dpe IS NOT NULL
            GROUP BY r.batiment_groupe_id
        ),
        ventes_par_classe AS (
            SELECT c.classes[OFFSET(DIV(ARRAY_LENGTH(c.classes) - 1, 2))] AS classe_dpe, v.prix_m2_local
            FROM {_table("bdnb_dvf_representatif")} v
            JOIN classe_batiment c USING (batiment_groupe_id)
            WHERE v.date_mutation >= DATE '{DATE_VENTE_MIN}'
              AND v.prix_m2_local BETWEEN {PRIX_M2_MIN} AND {PRIX_M2_MAX}
        )
    """


def construire_agg_prix_dpe():
    """Prix au m² par classe DPE du bâtiment, et écart F+G / D (médianes calculées sur toutes les ventes du groupe)."""
    ligne = _une_ligne(f"""
        SELECT COUNTIF(prix_m2_local BETWEEN {PRIX_M2_MIN} AND {PRIX_M2_MAX}) AS retenues,
               COUNTIF(prix_m2_local IS NULL OR prix_m2_local NOT BETWEEN {PRIX_M2_MIN} AND {PRIX_M2_MAX}) AS ecartees
        FROM {_table("bdnb_dvf_representatif")}
        WHERE date_mutation >= DATE '{DATE_VENTE_MIN}'
    """)
    logger.info(
        "Ventes depuis %s : retenues=%d écartées=%d (prix absent ou hors %d-%d €/m²)",
        DATE_VENTE_MIN, ligne["retenues"], ligne["ecartees"], PRIX_M2_MIN, PRIX_M2_MAX,
    )

    cte = _ventes_par_classe()
    _creer_table(AGG_PRIX_DPE, f"""{cte}
        SELECT
            classe_dpe,
            COUNT(*) AS nb_ventes,
            ROUND(APPROX_QUANTILES(prix_m2_local, 2)[OFFSET(1)], 0) AS prix_m2_median,
            CURRENT_TIMESTAMP() AS date_maj
        FROM ventes_par_classe
        GROUP BY classe_dpe
    """)
    return _creer_table(AGG_PRIX_ECART, f"""{cte}
        SELECT
            COUNTIF(classe_dpe IN ('F', 'G')) AS nb_fg,
            ROUND(APPROX_QUANTILES(IF(classe_dpe IN ('F', 'G'), prix_m2_local, NULL), 2)[OFFSET(1)], 0) AS prix_m2_median_fg,
            COUNTIF(classe_dpe = 'D') AS nb_d,
            ROUND(APPROX_QUANTILES(IF(classe_dpe = 'D', prix_m2_local, NULL), 2)[OFFSET(1)], 0) AS prix_m2_median_d,
            DATE '{DATE_VENTE_MIN}' AS date_vente_min,
            {PRIX_M2_MIN} AS prix_m2_min,
            {PRIX_M2_MAX} AS prix_m2_max,            
            CURRENT_TIMESTAMP() AS date_maj
        FROM ventes_par_classe
    """)


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
            (SELECT COUNT(*) FROM {_table("bdnb_dvf_representatif")}) AS nb_transactions,
            CURRENT_TIMESTAMP() AS date_maj
    """)


def construire_agregats():
    construire_agg_prix_dpe()
    construire_agg_parc()
    construire_agg_stats()

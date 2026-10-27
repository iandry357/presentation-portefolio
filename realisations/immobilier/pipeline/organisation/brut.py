import logging

from google.cloud import bigquery

from pipeline.organisation.config import (
    BDNB_ADRESSE, BDNB_ATTRIBUTS_BATIMENT, BDNB_BATIMENT_GROUPE, BDNB_REL_BATIMENT_ADRESSE, BQ_DATASET,
    GCP_PROJECT_ID, GCP_SA_KEY_PATH, NATURE_VENTE, TABLE_DVF, TYPE_LOCAL_COMMERCIAL, TYPES_LOGEMENT,
    VUE_BATIMENT_BRUT, VUE_DVF_BRUT, VUE_VENTES,
)

logger = logging.getLogger(__name__)

# Vues « tableau brut » : les jeux lus tels quels (aucune borne de prix, aucune fenêtre de dates).
# L'arrondissement se déduit du code commune INSEE (75101 -> 1) : valable pour Paris seulement.


def _client():
    return bigquery.Client.from_service_account_json(str(GCP_SA_KEY_PATH), project=GCP_PROJECT_ID)


def _table(nom):
    return f"`{GCP_PROJECT_ID}.{BQ_DATASET}.{nom}`"


def _litteral(valeur):
    """Texte SQL entre apostrophes (échappées avec un antislash, comme en GoogleSQL)."""
    return "'" + str(valeur).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _types_logement():
    return ", ".join(_litteral(t) for t in TYPES_LOGEMENT)


def _cle_adresse():
    """Expression SQL de la clé d'adresse au format BAN, identique à celle de pipeline/dvf_etalab/rattachement.py."""
    return """IF(adresse_numero IS NULL OR adresse_code_voie IS NULL, NULL,
              CONCAT(code_commune, '_', LOWER(adresse_code_voie), '_', LPAD(CAST(adresse_numero AS STRING), 5, '0'),
                     IF(IFNULL(adresse_suffixe, '') = '', '', CONCAT('_', LOWER(SUBSTR(adresse_suffixe, 1, 1))))))"""


def _compter(client, requete):
    return dict(next(iter(client.query(requete).result())))


def creer_vue_dvf(client):
    """Une ligne par vente d'un logement (règle V1 : un seul logement, aucun local commercial), colonnes du fichier
    en plus de celles de la vue V1 (adresse, coordonnées, lots, Carrez). Le prix au m² n'est pas borné."""
    client.query(f"""
        CREATE OR REPLACE VIEW {_table(VUE_DVF_BRUT)} AS
        WITH lignes AS (
            SELECT livraison, code_departement, id_mutation, id_parcelle, adresse_numero, adresse_suffixe,
                   adresse_nom_voie, adresse_code_voie, code_commune, code_postal, date_mutation, valeur_fonciere,
                   surface_reelle_bati, nombre_pieces_principales, nombre_lots, lot1_surface_carrez, type_local,
                   latitude, longitude,
                   COUNTIF(type_local IN ({_types_logement()}))
                       OVER (PARTITION BY livraison, code_departement, id_mutation) AS nb_logements,
                   LOGICAL_OR(type_local = {_litteral(TYPE_LOCAL_COMMERCIAL)})
                       OVER (PARTITION BY livraison, code_departement, id_mutation) AS a_commercial
            FROM {_table(TABLE_DVF)}
            WHERE nature_mutation = {_litteral(NATURE_VENTE)}
        )
        SELECT livraison, code_departement, id_mutation, id_parcelle, {_cle_adresse()} AS cle_adresse,
               date_mutation, type_local, nombre_pieces_principales, surface_reelle_bati, valeur_fonciere,
               SAFE_DIVIDE(valeur_fonciere, IF(surface_reelle_bati > 0, surface_reelle_bati, NULL)) AS prix_m2,
               SAFE_CAST(code_commune AS INT64) - 75100 AS arrondissement,
               code_postal, nombre_lots, lot1_surface_carrez, adresse_numero, adresse_nom_voie, latitude, longitude
        FROM lignes
        WHERE nb_logements = 1 AND NOT IFNULL(a_commercial, FALSE) AND type_local IN ({_types_logement()})
    """).result()
    logger.info("Vue %s créée", VUE_DVF_BRUT)


def creer_vue_batiment(client):
    """Une ligne par immeuble (bdnb_batiment_attributs) avec l'arrondissement, l'emprise, l'IRIS et les adresses
    concaténées (un immeuble peut en avoir plusieurs)."""
    client.query(f"""
        CREATE OR REPLACE VIEW {_table(VUE_BATIMENT_BRUT)} AS
        WITH adresses AS (
            SELECT r.batiment_groupe_id,
                   STRING_AGG(DISTINCT a.libelle_adresse, ' ; ' ORDER BY a.libelle_adresse) AS adresses
            FROM {_table(BDNB_REL_BATIMENT_ADRESSE)} r
            JOIN {_table(BDNB_ADRESSE)} a ON a.cle_interop_adr = r.cle_interop_adr
            GROUP BY r.batiment_groupe_id
        )
        SELECT t.batiment_groupe_id,
               SAFE_CAST(g.code_commune_insee AS INT64) - 75100 AS arrondissement,
               t.annee_construction, t.annee_arrondie, t.epoque_ff, t.usage_batiment, t.nb_niveau, t.nb_log, t.hauteur,
               t.copro_rnc, t.taille_copro, t.periode_rnc, t.inondation, t.patrimoine,
               g.s_geom_groupe, g.code_iris, d.adresses
        FROM {_table(BDNB_ATTRIBUTS_BATIMENT)} t
        JOIN {_table(BDNB_BATIMENT_GROUPE)} g ON g.batiment_groupe_id = t.batiment_groupe_id
        LEFT JOIN adresses d ON d.batiment_groupe_id = t.batiment_groupe_id
    """).result()
    logger.info("Vue %s créée", VUE_BATIMENT_BRUT)


def verifier(client):
    """Arrêt au premier écart : la vue DVF brute applique la règle V1, elle a donc autant de lignes que la vue V1 ;
    la vue Bâtiment a une ligne par immeuble de bdnb_batiment_attributs, sans doublon."""
    brut = _compter(client, f"SELECT COUNT(*) AS n FROM {_table(VUE_DVF_BRUT)}")["n"]
    v1 = _compter(client, f"SELECT COUNT(*) AS n FROM {_table(VUE_VENTES)}")["n"]
    if brut != v1:
        raise ValueError(f"{VUE_DVF_BRUT} : {brut} lignes pour {v1} dans la vue V1 {VUE_VENTES}")
    bati = _compter(client, f"SELECT COUNT(*) AS lignes, COUNT(DISTINCT batiment_groupe_id) AS distincts FROM {_table(VUE_BATIMENT_BRUT)}")
    attendu = _compter(client, f"SELECT COUNT(*) AS n FROM {_table(BDNB_ATTRIBUTS_BATIMENT)}")["n"]
    if bati["lignes"] != attendu or bati["distincts"] != attendu:
        raise ValueError(
            f"{VUE_BATIMENT_BRUT} : {bati['lignes']} lignes dont {bati['distincts']} immeubles distincts pour {attendu} attendus"
        )
    logger.info("Vues conformes : %d ventes (= vue V1), %d immeubles", brut, attendu)
    return brut, attendu


def construire_vues():
    client = _client()
    creer_vue_dvf(client)
    creer_vue_batiment(client)
    return verifier(client)

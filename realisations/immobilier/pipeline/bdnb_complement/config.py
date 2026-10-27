from pathlib import Path

from dotenv import load_dotenv

# Même couture que pipeline/bdnb/config.py : le .env de la V1 est dans pipeline/ et pipeline.config lit
# l'environnement dès l'import, il faut donc le charger avant. Seule dépendance vers la V1 : ces 3 constantes.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from pipeline.config import BQ_DATASET, GCP_PROJECT_ID, GCP_SA_KEY_PATH  # noqa: E402

# Données locales (non versionnées, exclues du build Docker par .dockerignore)
DOSSIER_BDNB = Path(__file__).resolve().parent.parent / "data" / "bdnb"
DOSSIER_PARQUET = DOSSIER_BDNB / "parquet"
DOSSIER_CHARGEMENT = DOSSIER_BDNB / "chargement_complement"  # Parquet temporaires envoyés à BigQuery

# Une colonne dont le nom correspond n'est jamais chargée, même si elle figure dans une liste blanche
MOTIF_COLONNES_INTERDITES = r"denomination|siren|siret|l_nom|nom_copro|nom_pdl|nom_demandeur|numero_immat"

# Tables cibles BigQuery. colonnes : liste blanche (aucune autre colonne n'est chargée) ;
# cluster[0] : clé, une ligne par valeur (contrôlé) ; lignes : valeur attendue (relevée à l'étape 0, 2026-10-27).
TABLES = {
    "bdnb_ffo_bat": {
        "source": "batiment_groupe_ffo_bat",
        "colonnes": ["batiment_groupe_id", "annee_construction", "nb_niveau", "nb_log", "usage_niveau_1_txt"],
        "cluster": ["batiment_groupe_id"],
        "lignes": 70765,
    },
    "bdnb_bdtopo_bat": {
        "source": "batiment_groupe_bdtopo_bat",
        "colonnes": ["batiment_groupe_id", "hauteur_mean", "max_hauteur"],
        "cluster": ["batiment_groupe_id"],
        "lignes": 74009,
    },
    "bdnb_rnc": {
        "source": "batiment_groupe_rnc",
        "colonnes": ["batiment_groupe_id", "nb_log", "nb_lot_tot", "periode_construction_max"],
        "cluster": ["batiment_groupe_id"],
        "lignes": 43712,
    },
    "bdnb_risques": {
        "source": "batiment_groupe_risques",
        "colonnes": ["batiment_groupe_id", "alea_debordement"],
        "cluster": ["batiment_groupe_id"],
        "lignes": 74212,
    },
    "bdnb_urbanisme": {
        "source": "batiment_groupe_urbanisme",
        "colonnes": ["batiment_groupe_id", "monument_historique", "zone_plu_bati_patrimonial"],
        "cluster": ["batiment_groupe_id"],
        "lignes": 72341,
    },
    "bdnb_parcelle_sitadel": {
        "source": "parcelle_sitadel",
        "colonnes": [
            "parcelle_id", "nombre_dau", "annee_premiere_dau_identifiee", "annee_derniere_dau_identifiee",
            "travaux_sur_construction_existante", "demolition", "indicateur_extension",
            "indicateur_surelevation_ou_nivsupp", "nature_derniere_dau", "bdnb_obsolete", "annee_construction_obsolete",
        ],
        "cluster": ["parcelle_id"],
        "lignes": 11485,
    },
}


# Tables lues (dataset BQ_DATASET) : tables de ce paquet et tables de pipeline/bdnb
BDNB_BATIMENT_GROUPE = "bdnb_batiment_groupe"
BDNB_REL_BATIMENT_PARCELLE = "bdnb_rel_batiment_parcelle"

# Tables écrites par l'étape attributs (recréées à chaque exécution)
TABLE_ATTRIBUTS_BATIMENT = "bdnb_batiment_attributs"
TABLE_ATTRIBUTS_PARCELLE = "bdnb_parcelle_attributs"
TABLE_CUBE_BATI = "agg_analyse_bati"  # cube des ventes avec attributs du bâti (étape cube), recréé à chaque exécution

# Époque de construction d'après l'année des fichiers fonciers : libellés de l'encadrement des loyers
# (pipeline/loyers/config.py) précédés d'un rang de tri ; (année maximale incluse, libellé), puis le libellé au-delà.
# Pour joindre aux loyers, retirer le rang (REGEXP_REPLACE(epoque_ff, r'^\d ', '')).
EPOQUES_BORNES = [(1945, "1 Avant 1946"), (1970, "2 1946-1970"), (1990, "3 1971-1990")]
EPOQUE_DERNIERE = "4 Apres 1990"
PAS_ANNEE_ARRONDIE = 10  # une année multiple de ce pas est marquée « arrondie » (BDNB : 1900, 1880, 1890… très fréquentes)

# Taille de copropriété d'après le nombre de logements du registre : bornes basses incluses, libellés préfixés pour l'ordre
TRANCHES_COPRO = [10, 20, 50]
LIBELLES_COPRO = ["1 moins de 10", "2 de 10 à 19", "3 de 20 à 49", "4 50 et plus"]

# Inondation par débordement (BDNB) : valeur de la colonne -> libellé ; absence de valeur = aucun aléa cartographié
MODALITES_DEBORDEMENT = {"Faible": "faible", "Moyen": "moyen ou fort", "Fort": "moyen ou fort"}
ORDRE_INONDATION = ["aucun", "faible", "moyen ou fort"]  # du moins au plus exposé
# Patrimoine : monument historique prime sur le bâti patrimonial du PLU
ORDRE_PATRIMOINE = ["aucun", "bâti patrimonial (PLU)", "monument historique"]
VALEURS_BOOLEENNES = {"0", "1"}  # monument_historique et zone_plu_bati_patrimonial

# Contrôles de l'étape attributs, relevés à l'exploration (millésime BDNB 2026-02.b, Paris) ; à mettre à jour avec le millésime
ATTENDU_BATIMENTS = 74212
ATTENDU_SANS_ANNEE = 8699
ATTENDU_COPRO = 43712
ATTENDU_INONDATION = {"aucun": 57110, "faible": 10701, "moyen ou fort": 6401}

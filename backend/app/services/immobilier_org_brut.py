"""
Tableaux bruts de la nouvelle organisation de la page Immobilier (accès privé, jamais en cache).
Trois jeux lus tels quels dans les vues construites par pipeline/organisation/brut.py : un arrondissement obligatoire,
période facultative, colonnes en liste blanche (catalogue JEUX), plafond de lignes.
Même compte de service et mêmes outils que immobilier_bigquery.py.
"""

import csv
import io
import logging
from datetime import date
from typing import Optional

from google.cloud import bigquery

from app.services.immobilier_bigquery import _get_bq_client, _serialiser, _table

logger = logging.getLogger(__name__)

# Paramètres
PLAFOND_LIGNES = 50_000      # au-delà : demande refusée (jamais de troncature silencieuse)
LIGNES_APERCU = 100
FORMATS = ["excel", "standard"]   # excel : « ; », BOM UTF-8, virgule décimale ; standard : « , », point décimal
FORMAT_DEFAUT = "excel"


class ErreurBrut(ValueError):
    """Demande refusée (jeu, colonne, période ou taille) : message affichable tel quel."""


def _col(nom, libelle, description, defaut=False, sensible=False):
    return {"nom": nom, "libelle": libelle, "description": description, "defaut": defaut, "sensible": sensible}


def _d(nom, libelle, description):
    """Colonne affichée par défaut."""
    return _col(nom, libelle, description, defaut=True)


def _o(nom, libelle, description):
    """Colonne en option."""
    return _col(nom, libelle, description)


def _s(nom, libelle, description):
    """Colonne en option, sensible (adresse, coordonnées, identifiants) : exposée derrière le code d'accès comme le reste."""
    return _col(nom, libelle, description, sensible=True)


# Catalogue : liste blanche des colonnes de chaque jeu (les noms viennent de la vue lue). L'ordre est celui des colonnes de l'export.
JEUX = {
    "dvf": {
        "libelle": "Ventes (DVF)",
        "source": "DVF Etalab : ventes d'un seul logement, sans local commercial, prix au m² non borné",
        "table": "org_dvf_brut",
        "colonne_date": "date_mutation",
        "tri": "date_mutation, id_parcelle",
        "colonnes": [
            _d("date_mutation", "Date de la vente", "Date de la mutation (signature de l'acte)."),
            _d("type_local", "Type de logement", "Appartement ou Maison."),
            _d("nombre_pieces_principales", "Pièces", "Nombre de pièces principales déclaré."),
            _d("surface_reelle_bati", "Surface (m²)", "Surface réelle bâtie déclarée dans l'acte."),
            _d("valeur_fonciere", "Prix de vente (€)", "Valeur foncière déclarée, telle que publiée."),
            _d("prix_m2", "Prix au m² (€)", "Prix de vente divisé par la surface réelle bâtie. Non borné : les analyses écartent les ventes sous 2 000 €/m² ou au-dessus de 30 000 €/m², pas ce tableau."),
            _d("arrondissement", "Arrondissement", "Arrondissement de Paris (1 à 20), déduit du code commune INSEE."),
            _o("code_postal", "Code postal", "Code postal de l'adresse du bien."),
            _o("nombre_lots", "Nombre de lots", "Nombre de lots de copropriété de la vente."),
            _o("lot1_surface_carrez", "Surface Carrez du lot 1 (m²)", "Surface Carrez du premier lot, quand elle est renseignée."),
            _s("latitude", "Latitude", "Latitude du bien, géolocalisée par Etalab."),
            _s("longitude", "Longitude", "Longitude du bien, géolocalisée par Etalab."),
            _s("adresse_numero", "Numéro de voie", "Numéro dans la voie."),
            _s("adresse_nom_voie", "Nom de la voie", "Nom de la voie."),
            _s("id_parcelle", "Parcelle cadastrale", "Identifiant de la parcelle cadastrale."),
            _s("cle_adresse", "Clé d'adresse", "Clé d'adresse au format de la Base Adresse Nationale (commune, voie, numéro) : sert à rattacher la vente à un immeuble de la BDNB."),
        ],
    },
    "dpe": {
        "libelle": "Diagnostics de performance énergétique (DPE)",
        "source": "DPE ADEME : tous les DPE de Paris depuis le début de la période, un DPE par ligne",
        "table": "org_dpe_brut",
        "colonne_date": "date_etablissement_dpe",
        "tri": "date_etablissement_dpe, numero_dpe",
        "colonnes": [
            _d("date_etablissement_dpe", "Date du DPE", "Date d'établissement du diagnostic."),
            _d("arrondissement", "Arrondissement", "Arrondissement de Paris (1 à 20), déduit du code INSEE de l'adresse."),
            _d("etiquette_dpe", "Étiquette énergie", "Classe de A (la moins énergivore) à G, calculée sur la consommation d'énergie primaire et les émissions de gaz à effet de serre."),
            _d("etiquette_ges", "Étiquette climat", "Classe de A à G selon les émissions de gaz à effet de serre."),
            _d("conso_5_usages_par_m2_ep", "Consommation (kWh EP/m²/an)", "Consommation d'énergie primaire pour les cinq usages (chauffage, eau chaude, refroidissement, éclairage, auxiliaires), par m² et par an."),
            _d("emission_ges_5_usages_par_m2", "Émissions de GES (kg CO₂e/m²/an)", "Émissions de gaz à effet de serre pour les cinq usages, par m² et par an."),
            _d("niveau_dpe", "Niveau du DPE", "Calculé d'après la méthode d'application : logement individuel, logement déduit de l'immeuble (DPE généré à partir du DPE de l'immeuble) ou immeuble."),
            _d("type_batiment", "Type de bâtiment", "appartement, maison ou immeuble."),
            _d("periode_construction", "Période de construction", "Tranche de période de construction du bâtiment (avant 1948, 1948-1974, ...)."),
            _d("surface_habitable_logement", "Surface habitable (m²)", "Surface habitable du logement diagnostiqué."),
            _o("methode_application_dpe", "Méthode d'application", "Méthode de calcul du DPE (appartement individuel, maison individuelle, généré à partir du DPE de l'immeuble, immeuble collectif)."),
            _o("conso_5_usages_ep", "Consommation totale (kWh EP/an)", "Consommation d'énergie primaire des cinq usages, pour tout le logement."),
            _o("conso_5_usages_par_m2_ef", "Consommation finale (kWh EF/m²/an)", "Consommation d'énergie finale (celle qui figure sur les factures) des cinq usages, par m² et par an."),
            _o("emission_ges_5_usages", "Émissions de GES totales (kg CO₂e/an)", "Émissions de gaz à effet de serre des cinq usages, pour tout le logement."),
            _o("annee_construction", "Année de construction", "Année de construction déclarée ou estimée."),
            _o("typologie_logement", "Typologie", "Typologie du logement (T1, T2, ...), vide dans la grande majorité des DPE."),
            _o("surface_habitable_immeuble", "Surface habitable de l'immeuble (m²)", "Surface habitable de l'immeuble, pour les DPE d'immeuble."),
            _o("nombre_appartement", "Appartements de l'immeuble", "Nombre d'appartements de l'immeuble."),
            _o("nombre_niveau_immeuble", "Niveaux de l'immeuble", "Nombre de niveaux de l'immeuble."),
            _o("nombre_niveau_logement", "Niveaux du logement", "Nombre de niveaux du logement."),
            _o("numero_etage_appartement", "Étage", "Numéro d'étage de l'appartement."),
            _o("position_logement_dans_immeuble", "Position dans l'immeuble", "Position du logement dans l'immeuble (étage courant, dernier étage, rez-de-chaussée, ...)."),
            _o("hauteur_sous_plafond", "Hauteur sous plafond (m)", "Hauteur sous plafond."),
            _o("classe_altitude", "Altitude", "Classe d'altitude du bâtiment."),
            _o("zone_climatique", "Zone climatique", "Zone climatique réglementaire (H1a, H1b, ...)."),
            _o("appartement_non_visite", "Appartement non visité", "1 si le diagnostiqueur n'a pas visité l'appartement (DPE établi à partir de l'immeuble), 0 sinon."),
            _o("type_energie_principale_chauffage", "Énergie du chauffage", "Énergie principale du chauffage."),
            _o("type_generateur_chauffage_principal", "Générateur de chauffage", "Type de générateur du chauffage principal."),
            _o("type_installation_chauffage", "Installation de chauffage", "Chauffage individuel, collectif ou mixte."),
            _o("type_installation_ecs", "Installation d'eau chaude", "Production d'eau chaude sanitaire individuelle, collective ou mixte."),
            _o("type_energie_principale_ecs", "Énergie de l'eau chaude", "Énergie principale de l'eau chaude sanitaire."),
            _o("type_generateur_chauffage_principal_ecs", "Générateur d'eau chaude", "Type de générateur de l'eau chaude sanitaire."),
            _o("conso_chauffage_ep", "Consommation de chauffage (kWh EP/an)", "Consommation d'énergie primaire du chauffage."),
            _o("conso_ecs_ep", "Consommation d'eau chaude (kWh EP/an)", "Consommation d'énergie primaire de l'eau chaude sanitaire."),
            _o("conso_chauffage_ef", "Consommation de chauffage (kWh EF/an)", "Consommation d'énergie finale du chauffage."),
            _o("conso_ecs_ef", "Consommation d'eau chaude (kWh EF/an)", "Consommation d'énergie finale de l'eau chaude sanitaire."),
            _o("emission_ges_chauffage", "Émissions du chauffage (kg CO₂e/an)", "Émissions de gaz à effet de serre du chauffage."),
            _o("emission_ges_ecs", "Émissions de l'eau chaude (kg CO₂e/an)", "Émissions de gaz à effet de serre de l'eau chaude sanitaire."),
            _o("type_energie_n1", "Énergie 1", "Première énergie utilisée dans le logement, par ordre de consommation."),
            _o("type_energie_n2", "Énergie 2", "Deuxième énergie utilisée."),
            _o("type_energie_n3", "Énergie 3", "Troisième énergie utilisée."),
            _o("flag_chauffage_electrique", "Chauffage électrique", "Vrai si l'énergie principale du chauffage est l'électricité (indicateur calculé à la collecte)."),
            _o("flag_post_reforme_2026", "DPE après la réforme de 2026", "Vrai si le DPE est établi à partir du 2026-01-01 (indicateur calculé à la collecte)."),
            _o("deperditions_enveloppe", "Déperditions de l'enveloppe (W/K)", "Déperditions thermiques totales de l'enveloppe du logement."),
            _o("deperditions_murs", "Déperditions des murs (W/K)", "Part des déperditions due aux murs."),
            _o("deperditions_planchers_hauts", "Déperditions des planchers hauts (W/K)", "Part des déperditions due aux planchers hauts (toit, combles)."),
            _o("deperditions_planchers_bas", "Déperditions des planchers bas (W/K)", "Part des déperditions due aux planchers bas."),
            _o("deperditions_portes", "Déperditions des portes (W/K)", "Part des déperditions due aux portes."),
            _o("deperditions_baies_vitrees", "Déperditions des baies vitrées (W/K)", "Part des déperditions due aux fenêtres et baies vitrées."),
            _o("deperditions_ponts_thermiques", "Déperditions des ponts thermiques (W/K)", "Part des déperditions due aux ponts thermiques."),
            _o("deperditions_renouvellement_air", "Déperditions par renouvellement d'air (W/K)", "Part des déperditions due à la ventilation et aux infiltrations d'air."),
            _o("qualite_isolation_enveloppe", "Isolation de l'enveloppe", "Qualité d'isolation de l'enveloppe : insuffisante, moyenne, bonne ou très bonne."),
            _o("qualite_isolation_murs", "Isolation des murs", "Qualité d'isolation des murs."),
            _o("qualite_isolation_plancher_haut_comble_amenage", "Isolation du plancher haut (combles aménagés)", "Qualité d'isolation du plancher haut sous combles aménagés."),
            _o("qualite_isolation_plancher_haut_comble_perdu", "Isolation du plancher haut (combles perdus)", "Qualité d'isolation du plancher haut sous combles perdus."),
            _o("qualite_isolation_plancher_haut_toit_terrasse", "Isolation du plancher haut (toit-terrasse)", "Qualité d'isolation du plancher haut en toit-terrasse."),
            _o("qualite_isolation_plancher_bas", "Isolation du plancher bas", "Qualité d'isolation du plancher bas."),
            _o("qualite_isolation_menuiseries", "Isolation des menuiseries", "Qualité d'isolation des fenêtres et portes."),
            _o("ubat_w_par_m2_k", "Ubat (W/m²·K)", "Coefficient moyen de déperdition thermique du bâtiment : plus il est bas, mieux le bâtiment est isolé."),
            _o("isolation_toiture", "Toiture isolée", "Indicateur 1/0 d'isolation de la toiture."),
            _o("inertie_lourde", "Inertie lourde", "Indicateur 1/0 d'inertie thermique lourde."),
            _o("classe_inertie_batiment", "Classe d'inertie", "Inertie thermique du bâtiment : légère, moyenne, lourde ou très lourde."),
            _o("logement_traversant", "Logement traversant", "1 si le logement est traversant, 0 sinon."),
            _o("indicateur_confort_ete", "Confort d'été", "Indicateur de confort d'été : insuffisant, moyen ou bon."),
            _o("protection_solaire_exterieure", "Protection solaire extérieure", "1 si le logement dispose d'une protection solaire extérieure, 0 sinon."),
            _o("cout_total_5_usages", "Coût des cinq usages (€/an)", "Coût annuel conventionnel des cinq usages. Estimation du DPE, pas une facture."),
            _o("cout_chauffage", "Coût du chauffage (€/an)", "Coût annuel conventionnel du chauffage."),
            _o("cout_ecs", "Coût de l'eau chaude (€/an)", "Coût annuel conventionnel de l'eau chaude sanitaire."),
            _o("cout_refroidissement", "Coût du refroidissement (€/an)", "Coût annuel conventionnel du refroidissement."),
            _o("cout_eclairage", "Coût de l'éclairage (€/an)", "Coût annuel conventionnel de l'éclairage."),
            _o("cout_auxiliaires", "Coût des auxiliaires (€/an)", "Coût annuel conventionnel des auxiliaires (pompes, ventilateurs)."),
            _o("type_ventilation", "Ventilation", "Type de ventilation du logement."),
            _o("type_generateur_froid", "Générateur de froid", "Type de générateur de froid, s'il y en a un."),
            _o("type_energie_climatisation", "Énergie de la climatisation", "Énergie utilisée par la climatisation."),
            _o("surface_climatisee", "Surface climatisée (m²)", "Surface refroidie par un système de climatisation."),
            _o("categorie_enr", "Énergie renouvelable", "Catégorie de système d'énergie renouvelable (pompe à chaleur, solaire thermique, bois, ...)."),
            _o("presence_production_pv", "Production photovoltaïque", "1 si le logement produit de l'électricité photovoltaïque, 0 sinon."),
            _o("surface_totale_capteurs_pv", "Surface de capteurs photovoltaïques (m²)", "Surface totale des capteurs photovoltaïques."),
            _o("production_electricite_pv_kwhep_par_an", "Production photovoltaïque (kWh EP/an)", "Production annuelle d'électricité photovoltaïque, en énergie primaire."),
            _o("electricite_pv_autoconsommee", "Électricité photovoltaïque autoconsommée", "Électricité photovoltaïque consommée sur place."),
            _o("systeme_production_electricite_origine_renouvelable", "Système de production renouvelable", "Système de production d'électricité d'origine renouvelable."),
            _s("numero_dpe", "Numéro du DPE", "Identifiant unique du DPE à l'ADEME."),
            _s("numero_dpe_remplace", "DPE remplacé", "Numéro du DPE que celui-ci remplace, quand il en remplace un."),
            _s("numero_dpe_immeuble_associe", "DPE de l'immeuble associé", "Numéro du DPE de l'immeuble dont le logement est issu."),
            _s("numero_immatriculation_copropriete", "Immatriculation de la copropriété", "Numéro du registre national des copropriétés."),
            _s("adresse_ban", "Adresse", "Adresse normalisée par la Base Adresse Nationale."),
            _s("numero_voie_ban", "Numéro de voie", "Numéro dans la voie."),
            _s("nom_rue_ban", "Nom de la voie", "Nom de la voie."),
            _s("identifiant_ban", "Identifiant BAN", "Identifiant de l'adresse dans la Base Adresse Nationale."),
            _s("coordonnee_cartographique_x_ban", "Coordonnée X (Lambert 93)", "Abscisse de l'adresse en Lambert 93."),
            _s("coordonnee_cartographique_y_ban", "Coordonnée Y (Lambert 93)", "Ordonnée de l'adresse en Lambert 93."),
        ],
    },
    "batiment": {
        "libelle": "Bâtiments (BDNB)",
        "source": "BDNB (CSTB) : un immeuble par ligne, état du parc au millésime, sans date",
        "table": "org_batiment_brut",
        "colonne_date": None,
        "tri": "batiment_groupe_id",
        "colonnes": [
            _d("arrondissement", "Arrondissement", "Arrondissement de Paris (1 à 20), déduit du code commune INSEE."),
            _d("epoque_ff", "Époque de construction", "Époque de construction d'après les Fichiers fonciers."),
            _d("usage_batiment", "Usage", "Usage principal du bâtiment."),
            _d("taille_copro", "Taille de la copropriété", "Classe de taille de la copropriété."),
            _d("inondation", "Inondation", "Indicateur de risque d'inondation de la BDNB."),
            _d("patrimoine", "Patrimoine", "Indicateur de protection patrimoniale de la BDNB."),
            _d("nb_log", "Logements", "Nombre de logements de l'immeuble."),
            _o("annee_construction", "Année de construction", "Année de construction connue, absente pour une partie des immeubles."),
            _o("annee_arrondie", "Année arrondie", "Année de construction arrondie."),
            _o("nb_niveau", "Niveaux", "Nombre de niveaux du bâtiment."),
            _o("hauteur", "Hauteur (m)", "Hauteur du bâtiment."),
            _o("copro_rnc", "Copropriété immatriculée", "Copropriété présente au registre national des copropriétés."),
            _o("periode_rnc", "Période d'immatriculation", "Période d'immatriculation au registre national des copropriétés."),
            _o("s_geom_groupe", "Emprise au sol (m²)", "Surface de l'emprise du bâtiment."),
            _o("code_iris", "Code IRIS", "Code de l'îlot regroupé pour l'information statistique."),
            _s("batiment_groupe_id", "Identifiant BDNB", "Identifiant de l'immeuble dans la BDNB."),
            _s("adresses", "Adresses", "Adresses de l'immeuble (plusieurs possibles, séparées par « ; »)."),
        ],
    },
}


def _jeu(jeu: str) -> dict:
    if jeu not in JEUX:
        raise ErreurBrut(f"Jeu inconnu : {jeu} (jeux : {', '.join(JEUX)})")
    return JEUX[jeu]


def colonne_date(jeu: str) -> Optional[str]:
    """Colonne à laquelle s'applique la période du jeu, ou None (jeu sans date)."""
    return _jeu(jeu)["colonne_date"]


def choisir_colonnes(jeu: str, noms: Optional[list[str]]) -> list[dict]:
    """Colonnes demandées, dans l'ordre du catalogue ; par défaut celles marquées « défaut ». Une colonne inconnue est refusée."""
    colonnes = _jeu(jeu)["colonnes"]
    if not noms:
        return [c for c in colonnes if c["defaut"]]
    connues = {c["nom"] for c in colonnes}
    inconnues = sorted(set(noms) - connues)
    if inconnues:
        raise ErreurBrut(f"Colonnes inconnues pour {jeu} : {inconnues}")
    return [c for c in colonnes if c["nom"] in set(noms)]


def _filtre(definition: dict, arrondissement: int, debut: Optional[date], fin: Optional[date]):
    """Clause WHERE et paramètres : seuls les noms du catalogue sont écrits dans le texte SQL, les valeurs sont des paramètres."""
    clauses = ["arrondissement = @arrondissement"]
    parametres = [bigquery.ScalarQueryParameter("arrondissement", "INT64", arrondissement)]
    colonne = definition["colonne_date"]
    if colonne and debut:
        clauses.append(f"{colonne} >= @debut")
        parametres.append(bigquery.ScalarQueryParameter("debut", "DATE", debut))
    if colonne and fin:
        clauses.append(f"{colonne} <= @fin")
        parametres.append(bigquery.ScalarQueryParameter("fin", "DATE", fin))
    return " AND ".join(clauses), parametres


def compter(jeu: str, arrondissement: int, debut: Optional[date], fin: Optional[date]) -> int:
    """Nombre de lignes du jeu pour l'arrondissement et la période."""
    definition = _jeu(jeu)
    where, parametres = _filtre(definition, arrondissement, debut, fin)
    requete = f"SELECT COUNT(*) AS n FROM {_table(definition['table'])} WHERE {where}"
    resultat = _get_bq_client().query(requete, job_config=bigquery.QueryJobConfig(query_parameters=parametres)).result()
    return next(iter(resultat))["n"]


def lire(
    jeu: str, arrondissement: int, debut: Optional[date], fin: Optional[date], colonnes: list[dict], limite: int,
) -> list[dict]:
    """Lignes du jeu (colonnes choisies, ordre déterministe, au plus `limite`)."""
    definition = _jeu(jeu)
    where, parametres = _filtre(definition, arrondissement, debut, fin)
    requete = (
        f"SELECT {', '.join(c['nom'] for c in colonnes)} FROM {_table(definition['table'])} "
        f"WHERE {where} ORDER BY {definition['tri']} LIMIT {int(limite)}"
    )
    resultat = _get_bq_client().query(requete, job_config=bigquery.QueryJobConfig(query_parameters=parametres)).result()
    lignes = _serialiser(resultat)
    logger.info(f"[immobilier_org_brut] {len(lignes)} lignes {jeu} lues (arrondissement {arrondissement})")
    return lignes


def _cellule(valeur, format_csv: str):
    if valeur is None:
        return ""
    if isinstance(valeur, bool):
        return ("VRAI" if valeur else "FAUX") if format_csv == "excel" else str(valeur).lower()
    if isinstance(valeur, float) and format_csv == "excel":
        return str(valeur).replace(".", ",")
    return valeur


def csv_bytes(lignes: list[dict], colonnes: list[dict], format_csv: str, libelles: bool) -> bytes:
    """CSV de l'export : en-têtes aux noms techniques (ou aux libellés), format excel (« ; », BOM, virgule décimale) ou standard."""
    excel = format_csv == "excel"
    sortie = io.StringIO(newline="")
    ecrivain = csv.writer(sortie, delimiter=";" if excel else ",", lineterminator="\r\n")
    ecrivain.writerow([c["libelle"] if libelles else c["nom"] for c in colonnes])
    for ligne in lignes:
        ecrivain.writerow([_cellule(ligne[c["nom"]], format_csv) for c in colonnes])
    return sortie.getvalue().encode("utf-8-sig" if excel else "utf-8")

"""Étape 0 : métadonnées BigQuery (lecture seule), dry-run, puis échantillon -> input/offers_sample.csv.
--jours N : offres publiées depuis N jours (défaut common.JOURS_MAX, 0 = pas de filtre)."""
import argparse
import csv
import sys
import time
from collections import Counter

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

import common

COLONNES = ["id_unique", "titre", "entreprise_nom", "url_offre", "liste", "date_publication", "source", "type_annonceur",
            "localisation_libelle", "groupe_doublon", "type_entreprise"]
COLONNES_OBLIGATOIRES = ["id_unique", "titre", "entreprise_nom", "url_offre"]


def lire_table(client, ref):
    """Métadonnées d'une table 'dataset.table', ou None si elle n'existe pas."""
    try:
        return client.get_table(f"{common.GCP_PROJECT_ID}.{ref}")
    except NotFound:
        return None


def afficher_schema(table):
    print(f"\n{table.full_table_id} : {table.num_rows} lignes, {table.num_bytes or 0} octets")
    for champ in table.schema:
        print(f"  - {champ.name} ({champ.field_type})")


def construire_requete(table, n, jours):
    presentes = {c.name for c in table.schema}
    manquantes_obl = [c for c in COLONNES_OBLIGATOIRES if c not in presentes]
    if manquantes_obl:
        sys.exit(f"Colonnes obligatoires absentes de {table.table_id} : {manquantes_obl}")
    manquantes = [c for c in COLONNES if c not in presentes]
    if manquantes:
        print(f"\nATTENTION colonnes absentes (remplacées par NULL) : {manquantes}")

    selection = ",\n  ".join(c if c in presentes else f"CAST(NULL AS STRING) AS {c}" for c in COLONNES)
    cle = "entreprise_normalise" if "entreprise_normalise" in presentes else "LOWER(TRIM(entreprise_nom))"
    priorite = "(COALESCE(liste, '') = 'a_lire')" if "liste" in presentes else "FALSE"
    tri = "date_publication" if "date_publication" in presentes else "id_unique"
    filtre_liste = " AND COALESCE(liste, '') != 'masque'" if "liste" in presentes else ""
    filtre_date = ""
    if jours and "date_publication" in presentes:
        filtre_date = f" AND SAFE_CAST(date_publication AS DATE) >= DATE_SUB(CURRENT_DATE(), INTERVAL {jours} DAY)"
    if common.UNE_PAR_ENTREPRISE:
        qualify = f"QUALIFY ROW_NUMBER() OVER (PARTITION BY {cle} ORDER BY {priorite} DESC, {tri} DESC) = 1\n"
    elif "date_run" in presentes:
        qualify = "QUALIFY ROW_NUMBER() OVER (PARTITION BY id_unique ORDER BY date_run DESC) = 1\n"  # une ligne par offre si le mart garde plusieurs runs
    else:
        qualify = ""
    table_sql = table.full_table_id.replace(":", ".")

    return f"""
SELECT
  {selection}
FROM `{table_sql}`
WHERE url_offre IS NOT NULL AND TRIM(url_offre) != ''
  AND entreprise_nom IS NOT NULL AND TRIM(entreprise_nom) != ''{filtre_liste}{filtre_date}
{qualify}ORDER BY {priorite} DESC, {tri} DESC
LIMIT {n}
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jours", type=int, default=common.JOURS_MAX,
                        help="offres publiées depuis N jours (1 = hier et aujourd'hui, 0 = pas de filtre)")
    args = parser.parse_args()
    if not common.GCP_PROJECT_ID:
        sys.exit("Variable GCP_PROJECT_ID absente.")
    debut = time.perf_counter()
    common.creer_dossiers()
    client = bigquery.Client(project=common.GCP_PROJECT_ID)

    mart = lire_table(client, common.TABLE_PRINCIPALE)
    if mart is not None:
        afficher_schema(mart)
    else:
        print(f"\n{common.TABLE_PRINCIPALE} introuvable.")
    ref = lire_table(client, common.TABLE_ENTREPRISES)
    if ref is not None:
        afficher_schema(ref)

    if mart is not None and (mart.num_rows or 0) > 0:
        table = mart
    else:
        table = lire_table(client, common.TABLE_REPLI)
        if table is None:
            sys.exit(f"{common.TABLE_PRINCIPALE} vide ou absente, et {common.TABLE_REPLI} introuvable.")
        afficher_schema(table)
        print(f"\nREPLI sur {common.TABLE_REPLI} (mart absent ou vide) : pas de liste, type_annonceur = inconnu.")
    print(f"\nTable utilisée : {table.full_table_id}")

    if table is mart and "type_annonceur" in {c.name for c in table.schema}:
        print("type_annonceur déjà présent dans le mart (jointure entreprises_ref faite par dbt) : pas de jointure ici.")

    sql = construire_requete(table, common.NB_OFFRES, args.jours)
    print(sql)

    estimation = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
    octets = estimation.total_bytes_processed
    print(f"Dry-run : {octets} octets estimés ({octets / 1024 ** 2:.1f} Mo)")
    if octets > common.MAX_OCTETS_REQUETE:
        sys.exit("Requête > 1 Go : arrêt.")

    lignes = list(client.query(sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=common.MAX_OCTETS_REQUETE)).result())
    with open(common.FICHIER_ECHANTILLON, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLONNES)
        for r in lignes:
            w.writerow(["" if r[c] is None else str(r[c]) for c in COLONNES])

    print(f"\n{len(lignes)} offres écrites dans {common.FICHIER_ECHANTILLON}")
    for c in ("liste", "type_annonceur", "source"):
        print(f"  {c} : {dict(Counter(r[c] for r in lignes))}")
    common.journaliser("00_inspect_schema", debut, offres=len(lignes), jours=args.jours,
                       une_par_entreprise=common.UNE_PAR_ENTREPRISE, octets_estimes=octets)


if __name__ == "__main__":
    main()

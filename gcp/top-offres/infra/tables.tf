resource "google_bigquery_table" "cibles" {
  dataset_id          = google_bigquery_dataset.top_offres.dataset_id
  table_id            = "cibles"
  deletion_protection = true

  schema = jsonencode([
    { name = "version_cibles", type = "STRING" },
    { name = "cible_id", type = "STRING" },
    { name = "intitule", type = "STRING" },
    { name = "niveau", type = "STRING" },
    { name = "justification", type = "STRING" },
    { name = "variantes_titres", type = "STRING", mode = "REPEATED" },
    { name = "description", type = "STRING" },
    { name = "modele", type = "STRING" },
    { name = "statut", type = "STRING" },
    { name = "cree_le", type = "TIMESTAMP" },
    { name = "valide_le", type = "TIMESTAMP" },
  ])

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_table" "entreprises_exclues" {
  dataset_id          = google_bigquery_dataset.top_offres.dataset_id
  table_id            = "entreprises_exclues"
  deletion_protection = true

  schema = jsonencode([
    { name = "nom", type = "STRING" },
    { name = "nom_normalise", type = "STRING" },
    { name = "synchronise_le", type = "TIMESTAMP" },
  ])

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_table" "entreprises_ref" {
  dataset_id          = google_bigquery_dataset.top_offres.dataset_id
  table_id            = "entreprises_ref"
  deletion_protection = true

  schema = jsonencode([
    { name = "nom_normalise", type = "STRING" },
    { name = "nom_source", type = "STRING" },
    { name = "siren", type = "STRING" },
    { name = "naf_code", type = "STRING" },
    { name = "naf_libelle", type = "STRING" },
    { name = "categorie", type = "STRING" },
    { name = "tranche_effectif", type = "STRING" },
    { name = "type_annonceur", type = "STRING" },
    { name = "origine", type = "STRING" },
    { name = "confiance", type = "FLOAT" },
    { name = "maj_le", type = "TIMESTAMP" },
    { name = "secteur", type = "STRING" },
    { name = "secteur_source", type = "STRING" },
    { name = "secteur_confiance", type = "STRING" },
    { name = "secteur_essai", type = "INTEGER" },
  ])

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_table" "offres_scores_staging" {
  dataset_id          = google_bigquery_dataset.top_offres.dataset_id
  table_id            = "offres_scores_staging"
  deletion_protection = true

  schema = jsonencode([
    { name = "run_id", type = "STRING" },
    { name = "id_unique", type = "STRING" },
    { name = "cible_proche", type = "STRING" },
    { name = "similarite", type = "FLOAT" },
    { name = "score", type = "INTEGER" },
    { name = "categorie", type = "STRING" },
    { name = "raison", type = "STRING" },
    { name = "alertes", type = "STRING", mode = "REPEATED" },
    { name = "statut_llm", type = "STRING" },
    { name = "modele", type = "STRING" },
    { name = "version_prompt", type = "STRING" },
    { name = "version_cibles", type = "STRING" },
    { name = "version_scoring", type = "STRING" },
    { name = "score_le", type = "TIMESTAMP" },
  ])

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_table" "runs" {
  dataset_id          = google_bigquery_dataset.top_offres.dataset_id
  table_id            = "runs"
  deletion_protection = true

  schema = jsonencode([
    { name = "run_id", type = "STRING" },
    { name = "mode", type = "STRING" },
    { name = "fenetre_debut", type = "TIMESTAMP" },
    { name = "fenetre_fin", type = "TIMESTAMP" },
    { name = "forcer", type = "BOOLEAN" },
    { name = "appliquer_exclusions", type = "BOOLEAN" },
    { name = "modele_scoring", type = "STRING" },
    { name = "version_prompt", type = "STRING" },
    { name = "version_cibles", type = "STRING" },
    { name = "version_scoring", type = "STRING" },
    { name = "nb_lues", type = "INTEGER" },
    { name = "nb_filtrees", type = "INTEGER" },
    { name = "nb_a_scorer", type = "INTEGER" },
    { name = "nb_scorees_ok", type = "INTEGER" },
    { name = "nb_erreurs", type = "INTEGER" },
    { name = "verdict", type = "STRING" },
    { name = "message", type = "STRING" },
    { name = "debut", type = "TIMESTAMP" },
    { name = "fin", type = "TIMESTAMP" },
    { name = "duree_s", type = "FLOAT" },
  ])

  lifecycle {
    prevent_destroy = true
  }
}

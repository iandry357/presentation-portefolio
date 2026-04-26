# Dataset — créé en Phase 1, importé ici
resource "google_bigquery_dataset" "emploi_marche" {
  dataset_id  = "emploi_marche"
  location    = var.region_bq
  project     = var.project_id
  description = "Offres d'emploi marché data & IA — source de vérité analytique"

  delete_contents_on_destroy = false

  lifecycle {
    prevent_destroy = true
  }
}

# Table offres_brutes — créée en Phase 1, importée ici
resource "google_bigquery_table" "offres_brutes" {
  dataset_id          = google_bigquery_dataset.emploi_marche.dataset_id
  table_id            = "offres_brutes"
  project             = var.project_id
  deletion_protection = true

  time_partitioning {
    type  = "DAY"
    field = "date_publication"
  }

  clustering = ["source", "code_rome"]

  schema = file("${path.module}/../sync_job/sources/BigQuerySchema.json")

  lifecycle {
    prevent_destroy = true
  }
}
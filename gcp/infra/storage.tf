# Bucket de configuration — créé en Phase 1, importé ici
resource "google_storage_bucket" "config" {
  name          = "portfolio-emploi-config"
  location      = var.region
  project       = var.project_id
  force_destroy = false

  uniform_bucket_level_access = true

  versioning {
    enabled = false
  }


  lifecycle {
    prevent_destroy = true
  }


}
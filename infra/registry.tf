resource "scaleway_registry_namespace" "main" {
  name       = var.registry_name
  region     = var.region
  project_id = var.project_id
  is_public  = false

  lifecycle {
    prevent_destroy = true
  }
}
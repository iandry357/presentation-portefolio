resource "scaleway_object_bucket" "tfstate" {
  name       = var.tfstate_bucket_name
  region     = var.region
  project_id = var.project_id

  versioning {
    enabled = true
  }

  tags = {
    purpose = "terraform-state"
    project = "portfolio"
  }
}

output "tfstate_bucket_name" {
  value = scaleway_object_bucket.tfstate.name
}

output "tfstate_bucket_region" {
  value = var.region
}
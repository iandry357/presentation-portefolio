resource "scaleway_rdb_instance" "main" {
  name               = var.db_name
  node_type          = "db-dev-s"
  engine             = "PostgreSQL-16"
  region             = var.region
  project_id         = var.project_id
  is_ha_cluster      = false
  disable_backup     = false
  volume_type        = "sbs_5k"
  encryption_at_rest = true

  backup_schedule_frequency = 72
  backup_schedule_retention = 3

  lifecycle {
    prevent_destroy = true
  }
}
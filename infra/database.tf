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

# Utilisateur lecture seule pour le worker local Top Offres (lecture du profil, table experiences)
resource "scaleway_rdb_user" "top_offres_reader" {
  instance_id = scaleway_rdb_instance.main.id
  name        = var.top_offres_db_user
  password    = var.top_offres_db_password
  is_admin    = false
}

resource "scaleway_rdb_privilege" "top_offres_reader" {
  instance_id   = scaleway_rdb_instance.main.id
  user_name     = scaleway_rdb_user.top_offres_reader.name
  database_name = "rdb"
  permission    = "readonly"
}
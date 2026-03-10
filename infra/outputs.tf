output "backend_url" {
  description = "URL publique du backend"
  value       = scaleway_container.backend.domain_name
}

output "frontend_url" {
  description = "URL publique du frontend"
  value       = scaleway_container.frontend.domain_name
}

output "registry_endpoint" {
  description = "Endpoint du Container Registry"
  value       = scaleway_registry_namespace.main.endpoint
}

output "db_endpoint" {
  description = "Endpoint PostgreSQL"
  value       = scaleway_rdb_instance.main.load_balancer[0].ip
  sensitive   = true
}
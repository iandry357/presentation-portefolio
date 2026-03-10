resource "scaleway_container_namespace" "main" {
  name       = var.namespace_name
  region     = var.region
  project_id = var.project_id
}

resource "scaleway_container" "backend" {
  name         = "portfolio-cv-backend"
  namespace_id = scaleway_container_namespace.main.id
  region       = var.region

  registry_image = var.backend_image
  port           = 8080
  protocol       = "http1"
  privacy        = "public"
  min_scale      = 1
  max_scale      = 2
  memory_limit   = 1024
  cpu_limit      = 500
  timeout        = 300
  scaling_option {
    concurrent_requests_threshold = 80
  }

  environment_variables = {
    API_HOST                  = "0.0.0.0"
    API_PORT                  = "8000"
    CORS_ORIGINS              = var.cors_origins
    EMBEDDING_DIMENSIONS      = "1024"
    EMBEDDING_MODEL           = "voyage-3"
    ENVIRONMENT               = "production"
    LANGSMITH_PROJECT         = "portfolio-rag"
    LOG_LEVEL                 = "INFO"
    POSTGRES_DB               = "rdb"
    POSTGRES_HOST             = "51.159.112.249"
    POSTGRES_PORT             = "7312"
    POSTGRES_USER             = var.db_user
    RETRIEVAL_SCORE_THRESHOLD = "0.1"
    RETRIEVAL_TOP_K           = "5"
  }

  secret_environment_variables = {
    GEMINI_API_KEY               = var.gemini_api_key
    SECRET_KEY                   = var.secret_key
    MISTRAL_API_KEY              = var.mistral_api_key
    GROQ_API_KEY                 = var.groq_api_key
    LANGSMITH_API_KEY            = var.langsmith_api_key
    VOYAGE_API_KEY               = var.voyage_api_key
    FRANCE_TRAVAIL_CLIENT_ID     = var.france_travail_client_id
    FRANCE_TRAVAIL_CLIENT_SECRET = var.france_travail_client_secret
    DATABASE_URL                 = var.database_url
    OPENAI_API_KEY               = var.openai_api_key
    POSTGRES_PASSWORD            = var.postgres_password
  }

  lifecycle {
    ignore_changes = [registry_image]
  }
}

resource "scaleway_container" "frontend" {
  name         = "portfolio-cv-frontend"
  namespace_id = scaleway_container_namespace.main.id
  region       = var.region

  port         = 8080
  protocol     = "http1"
  privacy      = "public"
  min_scale    = 0
  max_scale    = 2
  memory_limit = 256
  cpu_limit    = 250
  timeout      = 300
  scaling_option {
    concurrent_requests_threshold = 80
  }

  lifecycle {
    ignore_changes = [registry_image]
  }
}
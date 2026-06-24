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
    API_HOST                                 = "0.0.0.0"
    API_PORT                                 = "8000"
    CORS_ORIGINS                             = var.cors_origins
    EMBEDDING_DIMENSIONS                     = "1024"
    EMBEDDING_MODEL                          = "voyage-4"
    ENVIRONMENT                              = "production"
    LANGSMITH_PROJECT                        = "portfolio-rag"
    LANGCHAIN_TRACING_V2                     = "true"
    LANGFUSE_HOST                            = "https://cloud.langfuse.com"
    LOG_LEVEL                                = "INFO"
    POSTGRES_DB                              = "rdb"
    POSTGRES_HOST                            = var.postgres_host
    POSTGRES_PORT                            = "7312"
    POSTGRES_USER                            = var.db_user
    RETRIEVAL_SCORE_THRESHOLD                = "0.1"
    RETRIEVAL_TOP_K                          = "5"
    CHROMA_HOST                              = "51.68.130.23"
    CHROMA_PORT                              = "8000"
    CHROMA_USER                              = "portefolio"
    CHROMA_COLLECTION_SANOFI_CLINICAL_TRIALS = "sanofi_clinical_trials"
    CHROMA_COLLECTION_SANOFI_PUBMED          = "sanofi_pubmed"
    CHROMA_COLLECTION_SANOFI_NEWS            = "sanofi_news"
    CHROMA_COLLECTION_SANOFI_PRESS_RELEASES  = "sanofi_press_releases"
    BQ_DATASET_SANOFI_CLINICAL_TRIALS        = "sanofi_clinical_trials"
    BQ_DATASET_SANOFI_PUBMED                 = "sanofi_pubmed"
    BQ_DATASET_SANOFI_NEWS                   = "sanofi_news"
    OVH_ML_HOST                              = "51.68.130.23"
    OVH_ML_PORT                              = "8001"
    CHROMA_COLLECTION_SAVENCIA               = "savencia_veille"
    BQ_DATASET_SAVENCIA                      = "savencia_veille"
    OVH_ML_PORT_SAVENCIA                     = "8002"
    CHROMA_COLLECTION_SG                     = "sg_assurances_news"
    OVH_ML_PORT_SG                           = "8003"
    EMBEDDING_SERVICE_PORT                   = "8004"
    OVH_ORCHESTRATOR_PORT                    = "8080"
  }

  secret_environment_variables = {
    GEMINI_API_KEY                    = var.gemini_api_key
    SECRET_KEY                        = var.secret_key
    MISTRAL_API_KEY                   = var.mistral_api_key
    GROQ_API_KEY                      = var.groq_api_key
    LANGSMITH_API_KEY                 = var.langsmith_api_key
    LANGFUSE_PUBLIC_KEY               = var.langfuse_public_key
    LANGFUSE_SECRET_KEY               = var.langfuse_secret_key
    VOYAGE_API_KEY                    = var.voyage_api_key
    FRANCE_TRAVAIL_CLIENT_ID          = var.france_travail_client_id
    FRANCE_TRAVAIL_CLIENT_SECRET      = var.france_travail_client_secret
    DATABASE_URL                      = var.database_url
    OPENAI_API_KEY                    = var.openai_api_key
    POSTGRES_PASSWORD                 = var.postgres_password
    SERPER_API_KEY                    = var.serper_api_key
    GCP_SERVICE_ACCOUNT_JSON          = var.gcp_service_account_json
    GCP_SERVICE_ACCOUNT_JSON_SANOFI   = var.gcp_service_account_json_sanofi
    CHROMA_PASSWORD                   = var.chroma_password
    GCP_SERVICE_ACCOUNT_JSON_SAVENCIA = var.gcp_service_account_json_savencia
    GCP_SERVICE_ACCOUNT_JSON_SG       = var.gcp_service_account_json_sg
  }

  lifecycle {
    ignore_changes = [registry_image]
  }
}

resource "scaleway_container" "frontend" {
  name         = "portfolio-cv-frontend"
  namespace_id = scaleway_container_namespace.main.id
  region       = var.region

  port           = 8080
  protocol       = "http1"
  privacy        = "public"
  min_scale      = 0
  max_scale      = 2
  memory_limit   = 256
  cpu_limit      = 250
  timeout        = 300
  registry_image = var.frontend_image

  scaling_option {
    concurrent_requests_threshold = 80
  }

  lifecycle {
    ignore_changes = [registry_image]
  }
}
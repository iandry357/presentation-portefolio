terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  backend "gcs" {
    bucket = "portfolio-emploi-tfstate"
    prefix = "gcp/infra"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
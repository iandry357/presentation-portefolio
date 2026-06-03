terraform {
  required_providers {
    scaleway = {
      source  = "scaleway/scaleway"
      version = "~> 2.47"
    }
  }

  backend "s3" {
    bucket                      = "portfolio-tfstate"
    key                         = "terraform.tfstate"
    region                      = "fr-par"
    endpoint                    = "https://s3.fr-par.scw.cloud"
    skip_credentials_validation = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    force_path_style            = true
  }
}

provider "scaleway" {
  region     = var.region
  zone       = var.zone
  project_id = var.project_id
  access_key = var.scw_access_key
  secret_key = var.scw_secret_key
}
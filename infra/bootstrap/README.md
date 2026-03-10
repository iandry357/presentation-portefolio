# Bootstrap — Création bucket tfstate

Ce Terraform est indépendant et tourne une seule fois.
Il crée le bucket Object Storage qui stockera le state du Terraform principal.

## Prérequis
- CLI Scaleway initialisée (`scw init`)
- Terraform installé

## Utilisation

1. Créer le fichier de variables :
   cp terraform.tfvars.example terraform.tfvars
   # Remplir project_id dans terraform.tfvars

2. Initialiser et appliquer :
   terraform init
   terraform apply

3. Noter le nom du bucket en output → à reporter dans infra/main.tf
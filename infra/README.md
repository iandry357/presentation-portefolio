# Infrastructure as Code — Scaleway / Terraform 

Gestion de l'infrastructure Scaleway du portfolio via Terraform.
Toute modification d'infrastructure passe par ce répertoire — jamais via la console Scaleway manuellement.

---

## Prérequis

| Outil | Version | Installation |
|---|---|---|
| Terraform | 1.14.6+ | `winget install HashiCorp.Terraform` |
| Scaleway CLI | 2.41.0+ | `winget install Scaleway.CLI` |

---

## Structure

```
infra/
├── bootstrap/                   → Terraform one-shot pour créer le bucket tfstate
│   ├── main.tf                  → Provider Scaleway minimal
│   ├── bucket.tf                → Bucket Object Storage portfolio-tfstate
│   ├── variables.tf             → Variables bootstrap
│   ├── terraform.tfvars.example → Template variables (à copier)
│   └── README.md                → Ce fichier
│
├── main.tf                      → Provider Scaleway + backend remote S3
├── variables.tf                 → Toutes les variables de l'infra
├── outputs.tf                   → URLs containers, endpoint DB
├── registry.tf                  → Container Registry portfolio-sv-registry
├── containers.tf                → Namespace + containers backend et frontend
├── database.tf                  → PostgreSQL managé portefolio-cv-db
├── secrets.tf                   → 11 secrets dans Scaleway Secret Manager
│
├── terraform.tfvars.example     → Template variables réelles (à copier)
├── terraform.tfvars             → Valeurs réelles — JAMAIS commité
├── backend.hcl.example          → Template credentials bucket (à copier)
├── backend.hcl                  → Credentials bucket — JAMAIS commité
└── .gitignore                   → Protège terraform.tfvars et backend.hcl
```

---

## Ressources gérées

| Ressource | Nom Scaleway | Type |
|---|---|---|
| Container Registry | `portfolio-sv-registry` | `scaleway_registry_namespace` |
| Container Namespace | `portfolio-cv` | `scaleway_container_namespace` |
| Backend Container | `portfolio-cv-backend` | `scaleway_container` |
| Frontend Container | `portfolio-cv-frontend` | `scaleway_container` |
| PostgreSQL | `portefolio-cv-db` | `scaleway_rdb_instance` |
| Secret Manager | 11 secrets | `scaleway_secret` + `scaleway_secret_version` |
| Bucket tfstate | `portfolio-tfstate` | `scaleway_object_bucket` (bootstrap) |

---

## Initialisation complète (nouvelle machine)

### Étape 0 — Prérequis

Installer Terraform et la CLI Scaleway :

```bash
winget install HashiCorp.Terraform
winget install Scaleway.CLI
```

Initialiser la CLI Scaleway avec tes credentials :

```bash
scw init
```

Tu auras besoin de :
- Access Key Scaleway (format `SCWXXXXXXXXXXXXXXXXXX`)
- Secret Key Scaleway (format UUID)
- Project ID (console Scaleway → Settings → Projects)

---

### Étape 1 — Bootstrap (une seule fois par environnement)

> Cette étape crée le bucket Object Storage qui stocke le state Terraform.
> À ne faire qu'une seule fois. Si le bucket `portfolio-tfstate` existe déjà, passer directement à l'étape 2.

```bash
cd infra/bootstrap
cp terraform.tfvars.example terraform.tfvars
# Remplir terraform.tfvars avec project_id, region, zone
terraform init
terraform apply -var-file="terraform.tfvars"
```

Vérifier dans la console Scaleway → Storage → Object Storage que le bucket `portfolio-tfstate` est créé.

---

### Étape 2 — Initialisation du Terraform principal

Créer les fichiers de configuration locaux :

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
cp backend.hcl.example backend.hcl
```

Remplir `terraform.tfvars` avec toutes les valeurs (project_id + 11 secrets).

Remplir `backend.hcl` avec les credentials Scaleway :

```hcl
access_key = "SCWXXXXXXXXXXXXXXXXXX"
secret_key = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

Initialiser Terraform avec le backend remote :

```bash
terraform init -backend-config="backend.hcl"
```

---

### Étape 3 — Import des ressources existantes

> Si l'infra existe déjà sur Scaleway, importer les ressources avant d'appliquer.
> Si tu pars de zéro, passer directement à l'étape 4.

```bash
# Container Registry
terraform import -var-file="terraform.tfvars" scaleway_registry_namespace.main fr-par/<REGISTRY_ID>

# Container Namespace
terraform import -var-file="terraform.tfvars" scaleway_container_namespace.main fr-par/<NAMESPACE_ID>

# Backend Container
terraform import -var-file="terraform.tfvars" scaleway_container.backend fr-par/<BACKEND_CONTAINER_ID>

# Frontend Container
terraform import -var-file="terraform.tfvars" scaleway_container.frontend fr-par/<FRONTEND_CONTAINER_ID>

# PostgreSQL
terraform import -var-file="terraform.tfvars" scaleway_rdb_instance.main fr-par/<RDB_INSTANCE_ID>
```

Récupérer les IDs via la CLI Scaleway :

```bash
scw registry namespace list
scw container namespace list
scw container container list namespace-id=<NAMESPACE_ID>
scw rdb instance list
```

---

### Étape 4 — Plan et Apply

Toujours vérifier avant d'appliquer :

```bash
terraform plan -var-file="terraform.tfvars" -out=tfplan
terraform apply tfplan
```

---

## Usage quotidien

### Modifier une variable d'environnement

1. Modifier la valeur dans `infra/terraform.tfvars`
2. Modifier si besoin `infra/containers.tf` (bloc `environment_variables`)
3. Lancer `terraform plan` puis `terraform apply`

### Ajouter un nouveau secret

1. Ajouter la variable dans `infra/variables.tf`
2. Ajouter la valeur dans `infra/terraform.tfvars`
3. Ajouter l'entrée dans le bloc `locals` de `infra/secrets.tf`
4. Ajouter l'entrée dans `secret_environment_variables` de `infra/containers.tf`
5. Mettre à jour `infra/terraform.tfvars.example` avec la clé vide
6. Lancer `terraform plan` puis `terraform apply`

### Recréer l'infra de zéro

```bash
terraform destroy -var-file="terraform.tfvars"
terraform apply -var-file="terraform.tfvars"
```

> ⚠️ Le `destroy` supprime tout sauf le bucket tfstate (géré par bootstrap).
> La DB PostgreSQL est protégée par `prevent_destroy = true` — la supprimer nécessite de retirer cette ligne dans `database.tf`.

---

## CI/CD GitHub Actions

Le workflow `.github/workflows/terraform.yml` se déclenche automatiquement :

| Événement | Action |
|---|---|
| Push sur `infra-scaleway-v1.1` touchant `infra/**` | Plan + Apply automatique |
| Pull Request vers `infra-scaleway-v1.1` touchant `infra/**` | Plan uniquement |

### Secrets GitHub requis

| Secret GitHub | Contenu |
|---|---|
| `TF_VARS_FILE` | Contenu complet de `terraform.tfvars` |
| `TF_BACKEND_CONFIG` | Contenu de `backend.hcl` |

---

## Sécurité

- `terraform.tfvars` et `backend.hcl` sont dans `.gitignore` — ne jamais les commiter
- Les valeurs sensibles sont marquées `sensitive = true` dans `variables.tf`
- Les secrets sont stockés dans Scaleway Secret Manager, pas en clair sur les containers
- Le state Terraform est chiffré dans le bucket `portfolio-tfstate` avec versioning activé
- La DB PostgreSQL est protégée contre la suppression accidentelle (`prevent_destroy = true`)
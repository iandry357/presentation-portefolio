# Savencia ML — Guide d'exécution

Deux workflows indépendants :
- **Pipeline ETL** — collecte et indexation des articles de veille Savencia
- **Computer Vision** — fine-tuning ViT pour la détection de maturité fromagère

---

## Prérequis

- Python 3.11+
- CUDA 12.4+ (RTX 5060 recommandé pour l'entraînement)
- Docker Desktop en cours d'exécution
- Accès SSH OVH (`ubuntu@51.68.130.23`)
- Fichier `gcp_sa_savencia.json` à la racine de `realisations/savencia/`

---

## Setup — Activation du venv

Depuis `realisations/savencia/` :

```bash
# Windows / Cmder
venv-savencia\Scripts\activate
```

Le venv contient PyTorch avec support CUDA (`torch+cu124`) et toutes les dépendances ML.

---

## Workflow 1 — Pipeline ETL (Collecte articles)

### Architecture

```
Google News RSS (2 flux)
        │
        ▼
feedparser + Trafilatura (full-text)
        │
        ├── BigQuery (savencia_veille)
        └── ChromaDB OVH (embeddings VoyageAI)
```

### Lancer le pipeline complet

# --- Développement local ---
```bash
# Depuis realisations/savencia/
docker-compose run --rm pipeline python pipeline/orchestrator.py
```
# --- Production (GCP) ---
# Automatique : Cloud Scheduler déclenche le Cloud Run Job
# aux horaires configurés dans gcp/savencia/infra/

# Lancement manuel en prod (console GCP) :
# GCP Console → Cloud Run → Jobs → savencia-pipeline → Execute

# Ou via gcloud :
gcloud run jobs execute savencia-pipeline --region=europe-west9

### Scripts utilitaires

```bash
# Vérifier les données BigQuery
docker-compose run --rm pipeline python scripts/check_data.py

# Vérifier les embeddings ChromaDB
docker-compose run --rm pipeline python scripts/check_embeddings.py

# Inspecter ChromaDB
docker-compose run --rm pipeline python scripts/inspect_chromadb.py

# Reset ChromaDB (⚠️ supprime tous les embeddings Savencia)
docker-compose run --rm pipeline python scripts/reset_chromadb.py
```

### ⚠️ Reset BigQuery

Le streaming buffer GCP bloque les DELETE pendant ~90 minutes. Pour reset immédiat :

```sql
-- Dans la console BigQuery
DROP TABLE `gen-lang-client-0989575872.savencia_veille.articles`
```

Puis relancer le pipeline.

---

## Workflow 2 — Computer Vision (Fine-tuning ViT)

### Architecture

```
Dataset CR-IDB (CHEESE-HIDB)
        │
        ▼ prepare_dataset.py
CHEESE-HIDB-224/ (images redimensionnées 224x224)
        │
        ▼ train.py
ViT fine-tuné (google/vit-base-patch16-224)
        │
        ├── models/best_model.pt
        ├── models/model_latest.pt
        └── models/model_registry.json
        │
        ▼ scp → OVH
ml-service FastAPI (port 8002)
```

### Structure du dataset attendue

```
ml/sample_images/
├── CHEESE-HIDB-main/        ← images originales (6016x4016px)
│   ├── Extra-Hard/
│   │   ├── Target/
│   │   └── NotTarget/
│   ├── Hard/
│   │   ├── Target/
│   │   └── NotTarget/
│   └── Semi-Hard/
│       ├── Target/
│       └── NotTarget/
└── CHEESE-HIDB-224/         ← images redimensionnées (générées par prepare_dataset.py)
    ├── Extra-Hard/
    ├── Hard/
    └── Semi-Hard/
```

### Étape 1 — Préparer le dataset

```bash
# Depuis realisations/savencia/ml/training/
# (venv-savencia activé)
python prepare_dataset.py
```

Redimensionne les images originales de `CHEESE-HIDB-main/` vers `CHEESE-HIDB-224/` (224x224px, format attendu par ViT).

### Étape 2 — Entraînement

```bash
python train.py
```

Produit :
- `models/best_model.pt` — meilleur checkpoint (val accuracy)
- `models/model_latest.pt` — dernier checkpoint
- `models/model_registry.json` — métadonnées (accuracy, epochs, date)

> Durée estimée : ~30-60 min sur RTX 5060 selon le nombre d'epochs.

### Étape 3 — Évaluation

```bash
python evaluate.py
```

Affiche les métriques par type (Semi-Hard / Hard / Extra-Hard) et compare avec la baseline CRDet (Random Forest + handcrafted features).

### Étape 4 — Test inférence locale

```bash
python test_inference.py
```

Teste le modèle `best_model.pt` sur les images de `sample_images/` et génère les heatmaps Grad-CAM dans `results/heatmaps/`.

### Étape 5 — Déploiement sur OVH

#### Upload du modèle

```bash
# Depuis realisations/savencia/ml/
scp models/best_model.pt ubuntu@51.68.130.23:~/ml-project/realisations/savencia/ml/models/best_model.pt
```

#### Redémarrage du ml-service

```bash
ssh ubuntu@51.68.130.23
cd ~/ml-project/realisations/savencia/ml
docker-compose down
docker-compose up -d
```

#### Vérification

```bash
# Tester l'endpoint inférence
curl http://51.68.130.23:8002/health
```

---

## Fichiers clés

| Fichier | Rôle |
|---|---|
| `pipeline/orchestrator.py` | Point d'entrée pipeline ETL |
| `pipeline/collectors/google_news.py` | Collecte RSS + Trafilatura |
| `training/prepare_dataset.py` | Redimensionnement images → 224px |
| `training/dataset.py` | PyTorch Dataset custom |
| `training/train.py` | Fine-tuning ViT |
| `training/evaluate.py` | Métriques vs baseline CRDet |
| `training/test_inference.py` | Test inférence + Grad-CAM local |
| `ml/vit_inference.py` | Inférence FastAPI sur OVH |
| `models/model_registry.json` | Versioning modèle |

---

## Points d'attention

- `models/` est dans `.gitignore` — les `.pt` ne sont jamais commités
- `gcp_sa_savencia.json` est dans `.gitignore` — ne jamais commiter
- Le ml-service OVH tourne sur le réseau `savencia-ml-network` (port 8002) — isolé de Sanofi (port 8001)
- ChromaDB OVH partagé avec Sanofi — utiliser la collection `savencia_veille` uniquement
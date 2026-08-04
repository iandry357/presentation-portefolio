# MVP Banque de France — Guide de lancement & remise à jour des données

---

## 1. Prérequis

- `venv-banque-training` (Python local, pour l'entraînement/exploration) — `pandas`, `scikit-learn`, `sentence-transformers`, `google-cloud-bigquery`
- `gcp_sa_banque.json` présent à **2 emplacements** :
  - `realisations/banque-de-france/gcp_sa_banque.json` (local, pour le pipeline/training)
  - `~/ml-project/realisations/banque-de-france/gcp_sa_banque.json` (OVH, monté en volume par `banque-ml`)
- `.env` de `realisations/banque-de-france/ml/` avec au minimum `MISTRAL_API_KEY` et/ou `GEMINI_API_KEY` (labeling LLM du Topic Modeling), présent en local **et** sur OVH
- `backend/.env` (local) avec `GCP_SERVICE_ACCOUNT_JSON_BANQUE` — contenu JSON compacté sur une ligne, pas le chemin du fichier :
  ```bash
  python -c "import json; print(json.dumps(json.load(open('realisations/banque-de-france/gcp_sa_banque.json'))))"
  ```

---

## 2. Lancer les services

### 2.1 En local (test avant déploiement)

**Backend :**
```bash
cd backend
docker-compose up --build
```

**Frontend :**
```bash
cd frontend
npm run dev
```

### 2.2 Sur OVH (`51.68.130.23`)

⚠️ **`docker-compose up`/`restart` est actuellement cassé sur ce VPS** (bug `KeyError: 'ContainerConfig'`, incompatibilité `docker-compose` v1.29.2 avec une version récente du moteur Docker — cf. document Troubleshooting). Contournement à utiliser systématiquement pour `banque-ml` :

```bash
cd ~/ml-project/realisations/banque-de-france/ml

# Build (fonctionne normalement avec compose)
docker-compose -p banque-de-france-ml build --no-cache

# Démarrage — PAS docker-compose up, utiliser docker run directement
docker rm -f banque-ml-service 2>/dev/null
docker run -d \
  --name banque-ml-service \
  -p 8007:8007 \
  -v $(pwd)/results:/app/results \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/../gcp_sa_banque.json:/app/gcp_sa_banque.json:ro \
  --env-file .env \
  --restart unless-stopped \
  banque-de-france-ml_ml-service:latest
```

Vérifier :
```bash
curl http://localhost:8007/health
```

**Orchestrateur** (si `registry.yaml` a été modifié) :
```bash
cd ~/ml-project/ovh
docker-compose restart orchestrator
```
(celui-là fonctionne normalement — `registry.yaml` est monté en volume `:ro`, pas copié dans l'image, donc un simple restart recharge le fichier sans passer par le chemin `docker-compose up` fautif)

---

## 3. Remise à jour des données

### 3.1 Veille + décisions ACPR (pipeline ETL)

Pas encore automatisé via Cloud Run Job (cf. roadmap) — lancement manuel :
```bash
cd realisations/banque-de-france/pipeline
docker-compose run --rm pipeline python orchestrator.py
```
*(vérifier la commande exacte dans `pipeline/Dockerfile`/`orchestrator.py` si elle a évolué depuis — non re-testée dans cette session)*

Vérification post-run :
```bash
cd realisations/banque-de-france
python scripts/check_data.py
```

### 3.2 Score composite EBA (annuel, à la publication du nouvel exercice EBA)

1. Télécharger manuellement les nouveaux CSV EBA (`tr_oth.csv`, `tr_cre.csv`) depuis la section "Full database" de la page annuelle EBA, dans `training/eba/data/<année>/`
2. Recalculer :
   ```bash
   cd training/eba
   python load_eba.py
   python compute_score.py
   ```
3. Transférer le résultat vers OVH :
   ```bash
   scp data/processed/eba_scores.json ubuntu@51.68.130.23:/home/ubuntu/ml-project/realisations/banque-de-france/ml/results/eba_scores.json
   ```
   Aucun redémarrage de `banque-ml` nécessaire — le fichier est relu à chaque appel de `/predict/eba`.

### 3.3 Topic Modeling (à relancer après toute mise à jour de la veille)

```bash
docker exec banque-ml-service python topic_modeling.py
```
Vérifier dans les logs le nombre de documents exploitables et les labels générés — ajuster `N_TOPICS`/stopwords dans `topic_modeling.py` si le volume de veille a significativement changé.

### 3.4 Modèle de classification (réentraînement complet)

⚠️ Chantier lourd (fine-tuning du corps CamemBERT) — à ne faire que si le corpus de décisions ACPR a significativement grossi, pas pour un ajustement mineur.

```bash
cd training/classification
python dataset.py          # régénère full_pool.csv depuis les décisions BigQuery
python train_final.py      # réentraîne sur l'intégralité du pool
```
⚠️ Avant de relancer : nettoyer `training/models/classification/` (folds ET `final/`) pour ne pas mélanger anciens et nouveaux artefacts.

Puis réenregistrer le modèle (nouvelle version Vertex AI) :
```bash
cd training/registry
python register_model.py --model classification
```

Vérifier que la nouvelle version est bien montée dans le bucket avec une vraie hiérarchie de dossiers (pas d'antislash Windows) :
```bash
gsutil ls "gs://banque-de-france-models/banque-de-france/classification/embedding_body/"
```

Enfin, forcer le service OVH à retélécharger le modèle mis à jour (le cache local ne se rafraîchit pas tout seul) :
```bash
ssh ubuntu@51.68.130.23
rm -rf ~/ml-project/realisations/banque-de-france/ml/models/classification
docker rm -f banque-ml-service
docker run -d ... # cf. section 2.2 — le prochain démarrage retéléchargera depuis GCS
```

### 3.5 Exemples de démo (classification)

Le fichier `demo.csv` est commité directement dans le repo (`realisations/banque-de-france/ml/data/demo.csv`), copié dans l'image Docker au build (`COPY data ./data` dans le `Dockerfile`). Toute modification nécessite un rebuild de `banque-ml`, pas juste un remplacement de fichier sur disque.

---

## 4. Déploiement en production

### 4.1 Infrastructure GCP (Terraform, manuel — pas de CI dédiée pour ce MVP)

```bash
cd realisations/banque-de-france/infra   # ou l'emplacement réel du Terraform GCP du MVP
terraform plan
terraform apply
```

### 4.2 Infrastructure Scaleway (variables backend, Terraform manuel)

```bash
cd infra
terraform plan
terraform apply
```
Nécessite `gcp_service_account_json_banque` renseigné dans le `.tfvars` local.

### 4.3 Déploiement applicatif (backend + frontend)

Automatisé — un simple merge sur la branche `infra-scaleway-v1.1` déclenche GitHub Actions (build images Docker + push Container Registry + redeploy Serverless Containers). Aucune action manuelle nécessaire au-delà du merge, **sauf** si le secret GitHub `TF_VARS_FILE` n'a pas été mis à jour avec la nouvelle variable Terraform (`gcp_service_account_json_banque`) — sinon le pipeline échoue à l'étape `terraform apply` de la CI.

### 4.4 Après déploiement confirmé

Repasser le statut de la carte MVP de `'wip'` à `'live'` dans `frontend/app/realisations/page.tsx`.

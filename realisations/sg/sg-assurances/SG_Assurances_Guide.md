# SG Assurances — Guide d'exécution

Trois workflows indépendants :
- **Pipeline ETL** — collecte et indexation des articles de veille SG Assurances
- **Training ML** — entraînement YOLO, NER CamemBERT, QLoRA Qwen2.5-1.5B
- **Serving llama.cpp** — inférence Qwen fine-tuné sur OVH CPU

---

## Prérequis

- Python 3.11+
- CUDA 12.8+ (RTX 5060 recommandé pour l'entraînement QLoRA)
- Docker Desktop en cours d'exécution
- Accès SSH OVH (`ubuntu@51.68.130.23`)
- Fichier `gcp_sa_sg.json` à la racine de `realisations/sg/sg-assurances/`
- venv `venv-sg-training` activé pour les scripts de training

---

## Setup — Activation du venv

Depuis `realisations/sg/sg-assurances/` :

```bash
# Windows / Cmder
venv-sg-training\Scripts\activate
```

Le venv contient PyTorch GPU nightly (`torch==2.12.0.dev20260408+cu128`) et toutes les dépendances ML (transformers 4.46.0, peft, trl, ultralytics).

---

## Workflow 1 — Pipeline ETL (Collecte articles de veille)

### Architecture

```
France Travail API + Gmail alerts (9+ parsers RSS)
        │
        ▼
pipeline/orchestrator.py (Docker)
        │
        ├── BigQuery (sg_assurance_veille.articles_bruts)
        └── ChromaDB OVH :8000 (collection sg_assurances_news)
             └── Embeddings : paraphrase-multilingual-mpnet-base-v2 (768 dim)
                 via Embedding Service OVH :8004
```

### Lancer le pipeline complet

```bash
# Depuis realisations/sg/sg-assurances/
docker-compose run --rm pipeline python pipeline/orchestrator.py
```

### Scripts utilitaires

```bash
# Vérifier les données BigQuery
docker-compose run --rm pipeline python scripts/check_data.py

# Vérifier les embeddings ChromaDB
docker-compose run --rm pipeline python scripts/check_embeddings.py

# Inspecter ChromaDB
docker-compose run --rm pipeline python scripts/inspect_chromadb.py

# Reset ChromaDB (⚠️ supprime tous les embeddings SG)
docker-compose run --rm pipeline python scripts/reset_chromadb.py
```

### ⚠️ Reset BigQuery

Le streaming buffer GCP bloque les DELETE pendant ~90 minutes. Pour reset immédiat :

```sql
-- Dans la console BigQuery
CREATE OR REPLACE TABLE `gen-lang-client-0989575872.sg_assurance_veille.articles_bruts`
AS SELECT * FROM `gen-lang-client-0989575872.sg_assurance_veille.articles_bruts` WHERE FALSE
```

### Topic Modeling (ML Service OVH)

Après chaque mise à jour des données :

```bash
ssh ubuntu@51.68.130.23
cd ~/ml-project/realisations/sg/sg-assurances/ml
docker-compose run --rm sg-ml-service python topic_modeling.py
```

Produit : `results/topic_modeling.json` — 5 topics LDA avec labels LiteLLM (Mistral/Gemini fallback).

---

## Workflow 2 — Training ML

### Structure des modèles entraînés

```
training/models/
├── yolo/              ← poids YOLO entraîné
├── ner/               ← modèle NER CamemBERT fine-tuné
├── qlora/
│   └── qlora_sg_assurances/   ← adapters LoRA QLoRA
├── qwen-base/         ← modèle Qwen2.5-1.5B base
└── qwen_sg_merged/    ← modèle mergé base + LoRA (généré par export)
```

Tous les modèles sont aussi enregistrés dans **Vertex AI Model Registry** (`europe-west9`) comme référence MLOps.

---

### Étape 1 — YOLO (Détection zones document)

#### Dataset

```
training/data/
├── annotations/images/    ← images synthétiques de documents SG (PNG)
├── annotations/labels/    ← annotations YOLO format (.txt)
└── dataset.yaml           ← config classes et chemins
```

Classes détectées : `contract_block`, `identity_block`, `amount_block`, `signature_block`

#### Entraînement

```bash
# Depuis realisations/sg/sg-assurances/training/
# (venv-sg-training activé)
python train_yolo.py
```

Produit :
- `models/yolo/yolo_sg_assurances.pt` — meilleur checkpoint (mAP50)
- Métriques : mAP50=0.51, threshold=0.40

#### Push vers GCS

```bash
gsutil cp training/models/yolo/yolo_sg_assurances.pt gs://sg-assurances-models/sg-assurances/yolo/yolo_sg_assurances.pt
```

---

### Étape 2 — NER CamemBERT (Extraction entités)

#### Dataset

Données synthétiques générées via `pipeline/qa_generator.py` à partir du corpus ChromaDB.

Entités détectées : `NUMERO_POLICE`, `NOM_ASSURE`, `MONTANT`, `DATE`, `ADRESSE`

#### Entraînement

```bash
# Depuis realisations/sg/sg-assurances/training/
python train_ner.py
```

Produit :
- `models/ner/ner_sg_assurances/` — modèle CamemBERT fine-tuné complet
- Métriques : F1=0.84, threshold=0.70

#### Push vers GCS

```bash
gsutil -m rsync -r training/models/ner/ner_sg_assurances gs://sg-assurances-models/sg-assurances/ner/ner_sg_assurances
```

---

### Étape 3 — QLoRA Qwen2.5-1.5B (Modèle fine-tuné assurance)

#### Dataset

622 chunks extraits de 13 PDFs SG Assurances via `pipeline/pdf_collector.py` → indexés dans ChromaDB → paires Q/A générées via `pipeline/qa_generator.py` (Mistral local Ollama).

#### Entraînement

```bash
# Depuis realisations/sg/sg-assurances/training/
# (venv-sg-training activé — GPU RTX 5060 requis)
python train_qlora.py
```

Config optimale (Run 5) :
- `r=32`, `lora_alpha=64`, `NEFTune noise_alpha=5`
- Base model : `Qwen/Qwen2.5-1.5B-Instruct`
- Epochs : 3, batch_size : 4, gradient_accumulation : 4

Produit :
- `models/qlora/qlora_sg_assurances/` — adapters LoRA

#### Push vers GCS

```bash
gsutil -m rsync -r training/models/qlora/qlora_sg_assurances gs://sg-assurances-models/sg-assurances/qlora/qlora_sg_assurances
```

---

### Étape 4 — Export GGUF (Merge + Quantification)

#### Merge LoRA → modèle complet

```bash
# Depuis realisations/sg/sg-assurances/
# (venv-sg-training activé)
python scripts/export_merged_model.py
```

Produit : `training/models/qwen_sg_merged/` — modèle HuggingFace complet (~3Go)

#### Conversion F16 GGUF

```bash
# Depuis realisations/sg/sg-assurances/llama.cpp/
python convert_hf_to_gguf.py ../training/models/qwen_sg_merged --outfile ../training/models/qwen_sg_merged/qwen_sg_merged_f16.gguf --outtype f16
```

#### Quantification Q4_K_M

```bash
# Depuis realisations/sg/sg-assurances/llama.cpp/
..\llamaZip\llama-bin\llama-quantize.exe ..\training\models\qwen_sg_merged\qwen_sg_merged_f16.gguf ..\training\models\qwen_sg_merged\qwen_sg_merged_q4km.gguf Q4_K_M
```

Produit : `qwen_sg_merged_q4km.gguf` — ~934Mo

#### Déploiement sur OVH

```bash
scp realisations\sg\sg-assurances\training\models\qwen_sg_merged\qwen_sg_merged_q4km.gguf ubuntu@51.68.130.23:~/llm-models/qwen_sg_merged_q4km.gguf
```

---

## Workflow 3 — Serving llama-server OVH

### Architecture

```
llama-server (systemd, port 8005)
    └── ~/llm-models/qwen_sg_merged_q4km.gguf
         └── API compatible OpenAI /v1/chat/completions

ML Service OVH :8003
    └── qwen_finetuned_client.py → http://172.17.0.1:8005
```

### Commandes utiles

```bash
# Statut du service
sudo systemctl status llama-server

# Redémarrer le service
sudo systemctl restart llama-server

# Logs en temps réel
tail -f ~/llama-server.log

# Tester l'API
curl -X POST http://localhost:8005/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen","messages":[{"role":"user","content":"test"}],"max_tokens":50}'
```

### Mise à jour du modèle GGUF

1. Générer le nouveau GGUF en local (Étape 4)
2. Copier via scp vers `~/llm-models/`
3. Mettre à jour le chemin dans `/etc/systemd/system/llama-server.service` si besoin
4. `sudo systemctl daemon-reload && sudo systemctl restart llama-server`

---

## Déploiement ML Service OVH

```bash
ssh ubuntu@51.68.130.23
cd ~/ml-project/realisations/sg/sg-assurances/ml
git pull origin feature/realisations-sg
docker-compose down
docker-compose up -d --build
curl http://localhost:8003/health
```

**Résultat attendu :**
```json
{"status": "ok", "service": "sg-assurances-ml", "models": {"yolo": "loaded", "ner": "loaded", "qwen": "vertex-endpoint"}}
```

---

## Variables d'environnement requises

### `.env` — `realisations/sg/sg-assurances/pipeline/`

| Variable | Description |
|---|---|
| `GCP_PROJECT_ID` | `gen-lang-client-0989575872` |
| `SA_KEY_PATH` | Chemin relatif vers `gcp_sa_sg.json` |
| `BQ_DATASET` | `sg_assurance_veille` |
| `BQ_TABLE` | `articles_bruts` |
| `CHROMA_HOST` | `51.68.130.23` |
| `CHROMA_PORT` | `8000` |
| `CHROMA_USER` | — |
| `CHROMA_PASSWORD` | — |
| `CHROMA_COLLECTION_SG` | `sg_assurances_news` |
| `EMBEDDING_SERVICE_HOST` | `51.68.130.23` |
| `EMBEDDING_SERVICE_PORT` | `8004` |
| `MISTRAL_API_KEY` | — |
| `GEMINI_API_KEY` | — |

### `.env` — `realisations/sg/sg-assurances/ml/`

| Variable | Description |
|---|---|
| `SA_KEY_PATH` | `/app/gcp_sa_sg.json` |
| `GCS_YOLO_URI` | `gs://sg-assurances-models/sg-assurances/yolo/yolo_sg_assurances.pt` |
| `GCS_NER_URI` | `gs://sg-assurances-models/sg-assurances/ner/ner_sg_assurances` |
| `MISTRAL_API_KEY` | — |
| `GEMINI_API_KEY` | — |

---

## Points d'attention

- `training/models/` est dans `.gitignore` — les `.pt`, `.safetensors`, `.gguf` ne sont jamais commités
- `gcp_sa_sg.json` est dans `.gitignore` — ne jamais commiter
- Le ML Service OVH tourne sur le réseau `ml_default` (port 8003) — isolé des autres services
- **llama-server** tourne en dehors de Docker via systemd — accès depuis Docker via `172.17.0.1:8005`
- Le port 8005 est ouvert via UFW (`sudo ufw allow 8005`)
- Le streaming buffer BigQuery bloque les DELETE ~90 minutes après insert — utiliser `CREATE OR REPLACE TABLE` pour reset immédiat
- `pipeline/transformers/` a été renommé en `pipeline/transformation/` pour éviter le shadowing avec HuggingFace `transformers`
- `venv-sg-training` doit être dans `training/` — ne jamais lancer `pip install -r requirements.txt` de llama.cpp sans `--no-deps` pour ne pas écraser torch GPU

---

## Architecture des services

```
Local (Windows/Cmder)
├── venv-sg-training (PyTorch GPU)
│   ├── Training YOLO / NER / QLoRA
│   └── Export GGUF (llama.cpp)
└── pipeline ETL (Docker)
    ├── → BigQuery GCP (sg_assurance_veille)
    └── → ChromaDB OVH :8000 via Embedding Service :8004

OVH VPS-1 (51.68.130.23)
├── ChromaDB :8000
├── Embedding Service :8004 (paraphrase-multilingual-mpnet-base-v2)
├── ML Service :8003
│   ├── POST /predict/yolo
│   ├── POST /predict/ner
│   ├── GET  /predict/topic-modeling
│   └── POST /predict/qwen/finetuned → llama-server :8005
└── llama-server :8005 (systemd)
    └── qwen_sg_merged_q4km.gguf (~934Mo, Q4_K_M)

GCP
├── BigQuery : sg_assurance_veille.articles_bruts
├── GCS : gs://sg-assurances-models/ (modèles YOLO + NER)
└── Vertex AI Model Registry (europe-west9) — référence MLOps uniquement

Scaleway (backend FastAPI)
└── proxy → OVH ML Service
    ├── GET  /sg/stats
    ├── GET  /sg/news
    ├── POST /sg/rag
    ├── POST /sg/ml/yolo
    ├── POST /sg/ml/ner
    ├── GET  /sg/ml/topic-modeling
    └── POST /sg/ml/qwen
```
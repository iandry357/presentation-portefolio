# Pipeline Sanofi Investigation — Guide d'exécution

## Prérequis

- Docker Desktop lancé
- `.env` présent dans `realisations/sanofi/`
- `gcp_sa_sanofi.json` présent dans `realisations/sanofi/`
- Réseau Docker `portefolio-network` existant : `docker network create portefolio-network`
- Accès SSH OVH : `ubuntu@51.68.130.23`

---

## Étape 1 — Collecte + chargement BQ + ChromaDB

Depuis `realisations/sanofi/` :

```bash
docker-compose run --rm pipeline python pipeline/orchestrator.py
```

**Ce que ça fait :**
- Collecte ClinicalTrials (200 essais), PubMed (100 articles), Google News (50), Press Releases (5)
- Fetch contenu réel via Trafilatura pour Google News + Press Releases
- Normalisation + validation qualité
- Insertion BigQuery (déduplication automatique)
- Embeddings VoyageAI + insertion ChromaDB (upsert)

---

## Étape 2 — Enrichissement Google News (optionnel)

Enrichit les articles Google News existants dont le contenu est encore du HTML brut RSS.
À lancer 90 minutes après l'étape 1 (contrainte streaming buffer BigQuery).

```bash
docker-compose run --rm pipeline python pipeline/enrich_orchestrator.py
```

---

## Étape 3 — ML sur OVH

### Connexion OVH
```bash
ssh ubuntu@51.68.130.23
cd ~/ml-project/realisations/sanofi/ml
git pull origin feature/realisations-sanofi
```

### Lancer les modèles ML
```bash
docker-compose run --rm ml-service python clustering.py
docker-compose run --rm ml-service python forecasting.py
docker-compose run --rm ml-service python topic_modeling.py
```

**Ce que ça fait :**
- `clustering.py` — KMeans mixte TF-IDF + embeddings VoyageAI → 11 clusters → `results/clustering.json`
- `forecasting.py` — volume/an + durée par cluster → `results/forecasting.json`
- `topic_modeling.py` — LDA sur news + press releases → 5 topics → `results/topic_modeling.json`

---

## Étape 4 — Redémarrer le ml-service

Recharge les JSONs en mémoire cache.

```bash
docker-compose down
docker-compose up -d ml-service
curl http://localhost:8001/health
```

**Résultat attendu :**
```json
{"status": "ok", "cached": ["clustering", "forecasting", "topic_modeling"]}
```

---

## Vérifications

### Tester les endpoints ML depuis local
```bash
curl http://51.68.130.23:8001/ml/clustering
curl http://51.68.130.23:8001/ml/forecasting
curl http://51.68.130.23:8001/ml/topic-modeling
```

### Inspecter les résultats topic modeling
```bash
cd ~/ml-project/realisations/sanofi/ml
docker-compose run --rm ml-service python scripts/inspect_topic_modeling.py
```

### Vérifier les données BigQuery
```bash
cd realisations/sanofi
docker-compose run --rm pipeline python scripts/check_data.py
```

---

## Variables d'environnement requises

### `.env` — `realisations/sanofi/`
| Variable | Description |
|---|---|
| `GCP_PROJECT_ID` | `gen-lang-client-0989575872` |
| `GCP_SA_KEY_PATH` | Chemin relatif vers `gcp_sa_sanofi.json` |
| `BQ_DATASET_CLINICAL_TRIALS` | `sanofi_clinical_trials` |
| `BQ_DATASET_PUBMED` | `sanofi_pubmed` |
| `BQ_DATASET_NEWS` | `sanofi_news` |
| `BQ_DATASET_PRESS_RELEASES` | `sanofi_press_releases` |
| `CHROMA_HOST` | `51.68.130.23` |
| `CHROMA_PORT` | `8000` |
| `CHROMA_USER` | — |
| `CHROMA_PASSWORD` | — |
| `CHROMA_COLLECTION_CLINICAL_TRIALS` | `sanofi_clinical_trials` |
| `CHROMA_COLLECTION_PUBMED` | `sanofi_pubmed` |
| `CHROMA_COLLECTION_NEWS` | `sanofi_news` |
| `CHROMA_COLLECTION_PRESS_RELEASES` | `sanofi_press_releases` |
| `VOYAGE_API_KEY` | — |
| `VOYAGE_EMBEDDING_MODEL` | `voyage-3` |
| `VOYAGE_EMBEDDING_DIMENSIONS` | `1024` |
| `MISTRAL_API_KEY` | — |
| `GEMINI_API_KEY` | — |

### `.env` — `realisations/sanofi/ml/`
| Variable | Description |
|---|---|
| `GCP_SA_SANOFI_PATH` | `/app/gcp_sa_sanofi.json` |
| `CHROMA_HOST` | `51.68.130.23` |
| `CHROMA_PORT` | `8000` |
| `CHROMA_USER` | — |
| `CHROMA_PASSWORD` | — |
| `MISTRAL_API_KEY` | — |
| `GEMINI_API_KEY` | — |
| `VOYAGE_API_KEY` | — |
| `VOYAGE_EMBEDDING_MODEL` | `voyage-3` |
| `VOYAGE_EMBEDDING_DIMENSIONS` | `1024` |

---

## Architecture des services

```
Local (Windows/Cmder)
└── pipeline ETL (Docker)
    ├── → BigQuery GCP (4 datasets)
    └── → ChromaDB OVH :8000

OVH VPS-1 (51.68.130.23)
├── ChromaDB :8000
└── ml-service :8001
    ├── GET /ml/clustering
    ├── GET /ml/forecasting
    └── GET /ml/topic-modeling

Scaleway (backend FastAPI)
└── proxy → OVH ml-service
    ├── GET /sanofi/ml/clustering
    ├── GET /sanofi/ml/forecasting
    └── GET /sanofi/ml/topic-modeling
```
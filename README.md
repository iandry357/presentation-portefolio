# Portfolio CV — Iandry RAKOTONIAINA

Plateforme full-stack d'intelligence de recherche d'emploi, construite en solo, à double vocation :

1. **Portfolio technique live** — démontrer des compétences réelles Data/AI Engineering, ML et MLOps à travers des MVPs sectoriels déployés en production.
2. **Outil de veille emploi opérationnel** — observatoire du marché de l'emploi data, utilisé au quotidien (collecte multi-sources, scoring sémantique, enrichissement IA, suivi de candidatures).

🔗 **Démo live** : [portfoliocvcy2iktuv-portfolio-cv-frontend.functions.fnc.fr-par.scw.cloud](https://portfoliocvcy2iktuv-portfolio-cv-frontend.functions.fnc.fr-par.scw.cloud/)
📁 **Repo** : [github.com/iandry357/presentation-portefolio](https://github.com/iandry357/presentation-portefolio/tree/infra-scaleway-v1.1)

---

## Sommaire

- [Ce que fait la plateforme](#ce-que-fait-la-plateforme)
- [Architecture globale](#architecture-globale)
- [MVPs sectoriels](#mvps-sectoriels)
- [Workflows clés](#workflows-clés)
- [Infrastructure](#infrastructure)
- [Stack technique](#stack-technique)
- [Pages de la plateforme](#pages-de-la-plateforme)
- [Pipeline Gmail alerts](#pipeline-gmail-alerts)
- [Prérequis](#prérequis)
- [Installation et lancement](#installation-et-lancement)
- [Variables d'environnement](#variables-denvironnement)
- [Déploiement](#déploiement)
- [Structure du projet](#structure-du-projet)
- [Roadmap](#roadmap)

---

## Ce que fait la plateforme

| Module | Description |
|---|---|
| **CV interactif** | Chatbot RAG (BM25 + VoyageAI embeddings + reranking, LiteLLM multi-provider) qui répond aux questions sur le parcours |
| **Matching d'offres** | Collecte automatique France Travail + Gmail alerts (10 sources), scoring hybride, enrichissement agents LLM |
| **Tracker de candidatures** | Suivi des offres avec statuts, ajout manuel ; enrichissement offre via CrewAI + fiche entreprise via LangChain LCEL (`company_crew`) ; suivi des pipelines via LangSmith |
| **Explorer** | Parcours paginé de toutes les offres collectées avec filtres avancés |
| **Observatoire Marché** | Analytics BigQuery temps réel sur le marché de l'emploi data/ML (Q01–Q11), désormais servi par une **couche de transformation dbt** (Q01–Q10 lisent des tables agrégées, Q11 reste en lecture directe) |
| **Feedback** | Système de retour visiteur intégré sur toutes les pages |
| **Réalisations** | 5 MVPs sectoriels — Sanofi (Graph RAG + LLM fine-tuné), Savencia (NLP + Computer Vision), SG Assurances (YOLO + NER + QLoRA), Banque de France (Classification + RAG + Scoring EBA), Gestion Patrimoine (RAG juridique + function calling ReAct) |

---

## Architecture globale

```
Frontend (Next.js — Scaleway)
          │
          │ HTTP/REST
          ▼
Backend (FastAPI — Scaleway Serverless Container)
          │
          ├── RAG Chatbot CV ───────────────► PostgreSQL + pgvector (Scaleway)
          │
          ├── Pipeline Jobs
          │     ├── Collecte France Travail API
          │     ├── Collecte Gmail alerts (10 sources)
          │     ├── Scoring hybride (BM25 + VoyageAI + rerank-2)
          │     └── Enrichissement CrewAI (Parser → Analyste → Rédacteur)
          │
          ├── Routers Réalisations (sanofi / savencia / sg / banque_de_france / gestion_patrimoine)
          │     ├── orchestrator_client.py ──► Orchestrateur OVH :8080
          │     │                                 │
          │     │                                 ▼
          │     │                        Wake-on-demand des services ML
          │     │                        (démarrage/arrêt containers Docker,
          │     │                         timer d'inactivité 5 min)
          │     │
          │     └── profil_agent.py (gestion_patrimoine) ──► Mistral / Gemini (LiteLLM, appel direct, pas de service dédié)
          │
          ├── API Jobs / CV / Explorer / Market / Feedback
          │
          └── GCP BigQuery ◄──────────────── Cloud Run Job (sync-ft-bigquery)
                    │                               ▲
                    │ déclenche (fire-and-forget)  GCP Workflows
                    ▼                               ▲
              Cloud Run Job (dbt-emploi-marche)   Cloud Scheduler (3 triggers)
                    │
                    ▼
        stg_offres / int_offres_agg_* (BigQuery)

OVH VPS (51.68.130.23) — Compute ML / VectorDB
    ├── ChromaDB (port 8000, always-on)
    ├── Sanofi   : ml-service (8001), Neo4j (7474/7687), llama-server Mistral 7B (8006)
    ├── Savencia : ml-service (8002)
    ├── SG Assurances   : ml-service (8003), llama-server Qwen fine-tuné (8005)
    ├── Embedding Service (8004) — partagé SG Assurances + Banque de France + Gestion Patrimoine
    ├── Banque de France : ml-service (8007) — classification, topic modeling, scoring EBA
    └── Gestion Patrimoine : ml-service (8008, function calling ReAct), llama-server Qwen2.5-3B base (8009)
```

---

## MVPs sectoriels

Chaque MVP suit le même pattern structurel : **pipeline ETL → ML Service OVH → Backend Scaleway → Frontend Next.js**, avec ses modèles enregistrés dans Vertex AI Model Registry (`europe-west9`) quand applicable.

### Sanofi — ✅ En production (Release 2)
*Cible : poste "Accelerator Data Scientist Paris H/F" (CDI, Digital R&D)*

**Release 1 :**
- Pipeline ETL : ClinicalTrials (391 essais), PubMed (100 publications), Google News + Press Releases → BigQuery + ChromaDB
- ML : KMeans clustering (11 clusters thérapeutiques, TF-IDF + embeddings hybrides), Bayesian GLM forecasting (Poisson + MAP BFGS + approximation de Laplace), Topic Modeling
- RAG multi-sources avec fallback multi-provider
- Frontend : 6 vues — Essais Cliniques, Publications R&D, Actualités, Press Releases, Ask AI, ML Insights

**Release 2 — Therapeutic Insight + Graph RAG :**
- Ingestion OpenTargets GraphQL (gènes / maladies / médicaments / essais) → graphe Neo4j local
- Profils de clusters (Mature / Émergent / Exploratoire / Actif) basés sur `bio_score_avg` × `approved_drug_rate`
- Fine-tuning Mistral 7B (QLoRA) sur corpus drug discovery — win-rate **46,7 %** vs modèle de base
- Endpoint Graph RAG dédié (Neo4j + LLM fine-tuné), intégré dans la vue clusters (~125–140s de réponse)
- Serving : llama.cpp, OVH port 8006 (`-c 2048`)
- Modèle enregistré dans Vertex AI Model Registry (adaptateurs LoRA sur GCS, bucket `sanofi-models`)

### Savencia — ✅ En production
*Cible : Soredab, centre R&D agroalimentaire*

- Pipeline ETL Google News (2 flux RSS + Trafilatura) → BigQuery `savencia_veille` + ChromaDB
- ML : Topic Modeling LDA (5 topics cohérents en français), Computer Vision ViT (val_acc = 1.00 avec encoder dégelé + Grad-CAM heatmaps)
- Frontend : `/realisations/savencia` — Actualités, Ask AI RAG, Topics LDA, Détection maturité fromagère
- Deployed : OVH port 8002, réseau `savencia-ml-network`

### SG Assurances — ✅ En production
*Cible : secteur Banque/Assurance*

- Pipeline ETL → BigQuery `sg_assurance_veille` + ChromaDB (74 articles, embeddings 768 dim)
- 3 modèles ML entraînés et enregistrés dans Vertex AI Model Registry :
  - YOLO document detection — mAP50 = 0.51 (4 classes : contract, identity, amount, signature)
  - CamemBERT NER — F1 = 0.84 (5 entités : NUMERO_POLICE, NOM_ASSURE, MONTANT, DATE, ADRESSE)
  - QLoRA Qwen2.5-1.5B — win-rate = 29 % (r=32, lora_alpha=64, NEFTune noise_alpha=5)
- Serving : llama.cpp sur OVH port 8005 (Q4_K_M ~934 Mo, ~20 tok/sec CPU)
- ML Service OVH port 8003, Embedding Service port 8004 (partagé avec Banque de France et Gestion Patrimoine)

### Banque de France — ✅ En production
*Cible : offre Data Scientist Suptech (ACPR), en complément du MVP SG Assurances*

- Pipeline ETL veille RSS (2 flux) + décisions ACPR (découverte automatique du Recueil des sanctions, extraction PDF) → BigQuery `banque_de_france_veille` + ChromaDB (156-158 docs veille, 1924 chunks / 105 décisions ACPR)
- Classification multi-label des griefs de sanction : corps `sentence-camembert-base` fine-tuné + têtes k-NN one-vs-rest par catégorie (4 catégories), seuils dérivés du déséquilibre positif/négatif — modèle enregistré Vertex AI Model Registry (registre seul, inférence sur OVH)
- Scoring composite EBA : indicateur comparatif de robustesse financière (CET1 fully loaded / levier fully phased-in / NPL) des 6 grandes banques françaises vs moyenne UE simple, calcul déterministe (pas de ML), couverture 2022-2024
- RAG + Topic Modeling LDA restreints à la veille (décisions ACPR exclues, registres de langue trop différents)
- Frontend : `/realisations/banque-de-france` — Actualités, Ask AI, ML Insights (Topic Modeling / Scoring EBA / Classification avec démo interactive sur 82 décisions réelles)
- Backlog assumé : Webstat (fréquence des séries insuffisante), NER (chantier lourd pour un gain surtout méthodologique)

### Gestion Patrimoine — 🚧 Développé et testé, non déployé en production (branche non mergée)
*Copilote d'ingénierie patrimoniale — démonstration d'un pattern agentique RAG juridique avec anti-hallucination*

- Génération de profils clients synthétiques RGPD-safe via `profil_agent` (Mistral, fallback Gemini natif via LiteLLM, validation Pydantic stricte, 1 retry sur échec)
- Pipeline ETL Légifrance (API PISTE) → 213 articles du Code Général des Impôts, 761 chunks (chunking par marqueurs juridiques), BigQuery `referentiel_patrimoine` + ChromaDB
- `assistant_agent` : function calling **simulé par prompt (pattern ReAct)** — pas de function calling natif OpenAI-style, choix délibéré pour la robustesse sur un petit modèle local quantifié et la cohérence avec le pattern d'appel `llama-server` existant (SG/Sanofi)
- Anti-hallucination stricte : refus explicite si aucun article pertinent trouvé, citation obligatoire (numéro d'article + URL Légifrance) sur toute réponse
- Serving : llama.cpp, OVH port 8009, Qwen2.5-3B-Instruct **base** (non fine-tuné), `-c 4096`
- ML Service OVH port 8008 (boucle ReAct + `search_referentiel`)
- Frontend dédié : flux séquentiel profil → chat, format de conversation propre (carte profil persistante + fil de discussion, articles cités en pastilles cliquables)
- **Statut** : testé de bout en bout avec succès (génération profil → RAG → réponse citée, latence mesurée ~94s sur ce VPS), déployé manuellement sur OVH pour validation, **non mergé dans `infra-scaleway-v1.1`** — voir Roadmap

### Mirakl — 🔜 Prochain MVP
*E-commerce NLP/GenAI — analyse sentiment, détection d'anomalie prix, agent IA vendeur (BERT, PyTorch, LangChain + Mistral via LiteLLM)*

---

## Workflows clés

### Observatoire emploi (collecte → transformation → restitution)
```
Cloud Scheduler (7h / 12h / 1er-15 du mois)
        │
        ▼
Cloud Run Job "sync-ft-bigquery"
   ├── Collecte France Travail API
   └── Collecte Gmail OAuth (10 sources)
        │
        ▼
BigQuery emploi_marche.offres_brutes
        │
        │ déclenchement fire-and-forget si succès
        ▼
Cloud Run Job "dbt-emploi-marche"
   ├── dbt run  → staging (dédup) + intermediate (agrégats jour/entreprise/localisation)
   └── dbt test → échec bloquant si tests qualité KO
        │
        ▼
Frontend /market (Q01–Q10 sur tables agrégées, Q11 direct sur offres_brutes)
```

### Wake-on-demand OVH (orchestrateur)
```
Utilisateur ouvre une page Réalisations
        │
        ▼
Backend appelle wake(service_key) → Orchestrateur OVH :8080
        │
        ▼
Orchestrateur démarre le container ML via SDK Docker
        │
        ▼
Backend poll /health du service jusqu'à 200 OK
        │
        ▼
Appel ML exécuté normalement, heartbeat envoyé
        │
        ▼
Timer 5 min armé, reset à chaque heartbeat
        │
        ▼
Inactivité 5 min → container stoppé automatiquement
```
Services concernés : ChromaDB (always-on), Sanofi ML, Savencia ML, SG ML, Embedding Service (partagé SG + Banque de France + Gestion Patrimoine), Banque de France ML, Gestion Patrimoine ML.

> ⚠️ Les `llama-server` (SG, Sanofi, Gestion Patrimoine) sont **hors du périmètre de l'orchestrateur** — services systemd tournant en continu, pas des conteneurs Docker wake-on-demand. Avec 3 modèles désormais potentiellement actifs en permanence, la pression RAM/CPU du VPS est un point de vigilance actif (voir Roadmap).

### CI/CD (déploiement application)
```
Push sur infra-scaleway-v1.1
        │
        ▼
GitHub Actions
   ├── Build images Docker (backend + frontend)
   ├── Push Scaleway Container Registry
   └── Déploiement Serverless Containers (redeploy automatique)
```
Infrastructure Scaleway et GCP gérées exclusivement via Terraform — aucune modification manuelle via console.

---

## Infrastructure

### Scaleway
| Ressource | Usage |
|---|---|
| Serverless Container | Backend FastAPI (`min_scale=0` + lazy loading) |
| Serverless Container | Frontend Next.js |
| PostgreSQL managé + pgvector | Données candidat, offres trackées, embeddings, sessions/messages MVPs sectoriels |
| Container Registry | Images Docker backend + frontend |
| Secret Manager | Secrets applicatifs (noms en kebab-case) |
| Terraform state | Bucket S3 `portfolio-emploi-tfstate` |

### GCP (projet `gen-lang-client-0989575872`)
| Ressource | Usage |
|---|---|
| BigQuery `emploi_marche.offres_brutes` | Source de vérité des offres marché (partitionné `date_publication`, clustérisé `source, code_rome`) |
| BigQuery `stg_offres`, `int_offres_agg_*` | Couche de transformation dbt (staging + intermediate) |
| BigQuery `referentiel_patrimoine.articles_cgi` | Traçabilité des articles du CGI (Gestion Patrimoine) |
| Cloud Run Job `sync-ft-bigquery` | Pipeline de collecte France Travail + Gmail → BigQuery |
| Cloud Run Job `dbt-emploi-marche` | Transformation dbt déclenchée après chaque sync réussie |
| Cloud Scheduler × 3 | Sync 7h/12h quotidien + exploration ROME 1er/15 du mois |
| GCP Workflows | Orchestration Scheduler → Cloud Run Job |
| Vertex AI Model Registry (`europe-west9`) | Modèles fine-tunés (Mistral 7B Sanofi, YOLO/NER/Qwen SG Assurances, classification griefs Banque de France) |
| Secret Manager | Secrets pipeline GCP (`ft-client-id`, `ft-client-secret`, `gmail-token`, `gmail-credentials`) |
| Cloud Storage `portfolio-emploi-config` | Configuration ROME codes + liste entreprises exclues |
| Cloud Storage `sanofi-models` | Adaptateurs LoRA Sanofi |
| Cloud Storage `banque-de-france-models` | Corps d'embeddings + têtes k-NN classification griefs ACPR |
| BigQuery `banque_de_france_veille` | Veille + décisions ACPR (colonne `source` distingue les deux) |
| Artifact Registry `europe-west9` | Images Docker Cloud Run Jobs |

### OVH VPS (`51.68.130.23`)
| Service | Port | Rôle |
|---|---|---|
| Orchestrateur (FastAPI) | 8080 | Wake-on-demand, heartbeat, statut, health |
| ChromaDB | 8000 | Base vectorielle globale — always-on |
| Sanofi ML Service | 8001 | Clustering, forecasting, topic modeling, Graph RAG |
| Neo4j | 7474 / 7687 | Graphe Therapeutic Insight (Sanofi Release 2) |
| Savencia ML Service | 8002 | Topic modeling, inférence ViT |
| SG ML Service | 8003 | YOLO, NER, topic modeling |
| Embedding Service | 8004 | Embeddings pour RAG — partagé SG Assurances, Banque de France, Gestion Patrimoine |
| llama-server Qwen fine-tuné (SG) | 8005 | Serving Qwen2.5 fine-tuné QLoRA (`-c 1024`) |
| llama-server Mistral (Sanofi) | 8006 | Serving Mistral 7B fine-tuné (`-c 2048`) |
| Banque de France ML Service | 8007 | Classification griefs, topic modeling, scoring EBA |
| Gestion Patrimoine ML Service | 8008 | Boucle ReAct, function calling simulé, `search_referentiel` |
| llama-server Qwen2.5-3B base (Gestion Patrimoine) | 8009 | Serving Qwen2.5-3B-Instruct **non fine-tuné** (`-c 4096`) |

Toute l'infra est versionnée en **Terraform IaC**, déployée via **GitHub Actions** sur la branche `infra-scaleway-v1.1`.

---

## Stack technique

| Couche | Technologies |
|---|---|
| Frontend | Next.js App Router, TypeScript, Tailwind CSS, shadcn/ui, Recharts, TipTap, ReactMarkdown |
| Backend | FastAPI, Python, SQLAlchemy (async), asyncpg, Pydantic |
| Pipeline IA | CrewAI, LangChain LCEL, LiteLLM |
| LLMs | GPT-4o-mini (OpenAI), Mistral (magistral-small + Mistral 7B fine-tuné), Gemini (GCP), Qwen2.5 fine-tuné (SG), Qwen2.5-3B base (Gestion Patrimoine) |
| Embeddings / Rerank | VoyageAI `voyage-3`, `rerank-2` ; `paraphrase-multilingual-mpnet-base-v2` (RAG sectoriels) |
| ML sectoriel | KMeans, Bayesian GLM (MAP + Laplace), LDA, ViT, YOLO, CamemBERT NER, QLoRA, CamemBERT + k-NN (classification multi-label) |
| Bases de données | PostgreSQL + pgvector (Scaleway), BigQuery (GCP), Neo4j (OVH), ChromaDB (OVH) |
| Transformation data | dbt-core + dbt-bigquery |
| Recherche web | DuckDuckGo (`backend="html"`), Brave Search API |
| Matching ROME | ROMEO v2 API |
| Monitoring | LangSmith (projet `portfolio-rag` — traces CrewAI + company_crew) |
| Infra as Code | Terraform (Scaleway `infra/`, GCP `gcp/infra/`, `gcp/dbt_transformation/infra/`, OVH orchestrateur) |
| CI/CD | GitHub Actions + Docker |

---

## Pages de la plateforme

| Route | Description |
|---|---|
| `/` | Landing page |
| `/cv` | CV statique rendu depuis PostgreSQL |
| `/cv/edit` | Interface CRUD expériences |
| `/chat` | Chatbot RAG interactif |
| `/jobs` | Tracker candidatures avec scoring et enrichissement CrewAI |
| `/jobs/[id]` | Fiche détail offre enrichie + recalcul (max 3) |
| `/companies/[id]` | Fiche entreprise enrichie pour préparation entretien |
| `/explore` | Exploration des offres BigQuery avec filtres |
| `/market` | Observatoire marché emploi — catalogue Q01–Q11 (dbt) |
| `/realisations` | Vue d'ensemble des MVPs sectoriels |
| `/realisations/sanofi` | MVP Sanofi — Essais Cliniques, PubMed, Actualités, Press Releases, Ask AI, ML Insights, Graph RAG |
| `/realisations/savencia` | MVP Savencia — Actualités, Ask AI, Topics LDA, Détection maturité fromagère |
| `/realisations/sg/sg-assurances` | MVP SG Assurances — Actualités, RAG, YOLO/NER (Document), Qwen |
| `/realisations/banque-de-france` | MVP Banque de France — Actualités, Ask AI, ML Insights (Topic Modeling, Scoring EBA, Classification) |
| `/realisations/gestion-patrimoine` | MVP Gestion Patrimoine — génération de profil, assistant RAG juridique avec citation (non en prod, branche non mergée) |

---

## Pipeline Gmail alerts

10 sources parsées automatiquement via alertes email :

| Source | Adresse expéditeur |
|---|---|
| France Travail | `nepasrepondre@offre.francetravail.fr` |
| LinkedIn | `jobalerts-noreply@linkedin.com` |
| APEC | `offres@diffusion.apec.fr` |
| Hellowork | `notification@emails.hellowork.com` |
| Talent.com | `no-reply@alerts.talent.com` |
| Jobijoba | `contact@jobijoba.com` |
| Free-Work | `alerts@welcometothejungle.com` |
| WTTJ | — |
| Indeed | `donotreply-jobalert@indeed.com` |
| JobLeads | `mailer@jobleads.com` |
| Meteojob | `ne-pas-repondre@meteojob.com` |

> ⚠️ Token OAuth Gmail à régénérer manuellement tous les 7 jours (app en mode Test).
> Voir `backend/scripts/README_gmail_token.md` pour la procédure.

---

## Prérequis

- Docker et Docker Compose (`docker-compose` v1 syntax requis côté OVH — bug connu `KeyError: 'ContainerConfig'` sur recréation, voir Roadmap)
- Node.js v18+
- Python 3.11+
- Comptes : Scaleway, GCP, VoyageAI, OpenAI, Mistral, Gemini, LangSmith
- Voir section Variables d'environnement

---

## Installation et lancement

### Application (backend + frontend) — Avec Docker *(recommandé)*

```bash
git clone https://github.com/iandry357/presentation-portefolio.git
cd presentation-portefolio
git checkout infra-scaleway-v1.1
```

Créer les fichiers `.env` (voir section suivante), puis :

```bash
# Backend
cd backend
docker compose up --build

# Frontend (autre terminal)
cd frontend
docker build -t portfolio-frontend .
docker run -p 3000:3000 --env-file .env portfolio-frontend
```

### Application — Sans Docker

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

### Couche dbt (Observatoire Emploi) — en local

```bash
cd gcp/dbt_transformation
python -m venv venv-dbt
venv-dbt\Scripts\activate
pip install -r requirements.txt
gcloud auth application-default login

dbt debug                  # vérifier la connexion BigQuery (target dev)
dbt run                    # construire tous les modèles
dbt test                   # lancer les tests qualité
dbt source freshness       # vérifier la fraîcheur de offres_brutes
```

### Orchestrateur OVH (wake-on-demand)

```bash
cd ovh
docker-compose up -d
# API disponible sur le port 8080 : /wake, /heartbeat, /status, /health
```

### Pipeline ETL Gestion Patrimoine (ponctuel, one-shot)

```bash
cd realisations/gestion-patrimoine/pipeline
docker-compose run --rm pipeline
```

---

## Variables d'environnement

### Backend — `backend/.env`

```env
# Base de données
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname

# Sécurité
SECRET_KEY=your_secret_key

# France Travail API
FT_CLIENT_ID=
FT_CLIENT_SECRET=

# LLM
OPENAI_API_KEY=
MISTRAL_API_KEY=
GEMINI_API_KEY=

# Embeddings & Reranking
VOYAGE_API_KEY=

# ROME prediction
ROMEO_API_KEY=

# GCP
GCP_SERVICE_ACCOUNT_JSON=

# Orchestrateur OVH
OVH_ORCHESTRATOR_PORT=8080

# Monitoring
LANGSMITH_API_KEY=
LANGCHAIN_TRACING_V2=true
LANGSMITH_PROJECT=portfolio-rag
```

### Frontend — `frontend/.env.local`

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_FT_BASE_URL=https://candidat.francetravail.fr/offres/recherche/detail
```

### Gestion Patrimoine — `realisations/gestion-patrimoine/.env` (OVH, hors dépôt)

```env
CHROMA_HOST=
CHROMA_PORT=8000
CHROMA_USER=
CHROMA_PASSWORD=
EMBEDDING_SERVICE_URL=http://<gateway_gestion-patrimoine-ml-network>:8004
OVH_ORCHESTRATOR_URL=http://<gateway_gestion-patrimoine-ml-network>:8080
LLAMA_SERVER_URL=http://<gateway_gestion-patrimoine-ml-network>:8009/v1/chat/completions
```

### dbt — `gcp/dbt_transformation/profiles.yml`

Valeurs de connexion (projet, dataset, SA à impersonner) mises en dur — dbt ne lit pas automatiquement de `.env`. Deux targets : `dev` (ADC + impersonation SA `pipeline-dbt` en local) et `prod` (SA natif attaché au Cloud Run Job).

---

## Déploiement

Entièrement automatisé via **GitHub Actions** sur push de la branche `infra-scaleway-v1.1` :

1. Build images Docker backend + frontend
2. Push sur Scaleway Container Registry
3. Déploiement Serverless Containers Scaleway

Les Cloud Run Jobs (`sync-ft-bigquery`, `dbt-emploi-marche`) se redéploient manuellement via `gcloud run jobs update` après changement d'image (voir procédures dans `gcp/sync_job/` et `gcp/dbt_transformation/`).

L'infrastructure Scaleway est gérée via **Terraform** (`infra/`). L'infrastructure GCP est gérée via **Terraform** (`gcp/infra/`, `gcp/dbt_transformation/infra/`). Aucune modification manuelle via console.

**Gestion Patrimoine — cas particulier** : développé sur la branche `feature/gestion-patrimoine-mvp`, déployé et testé sur OVH manuellement, mais **pas encore mergé** dans `infra-scaleway-v1.1` — le CI/CD ne l'a donc pas encore déployé en production Scaleway. Voir `Guide_Lancement_Gestion_Patrimoine.md` pour la procédure de merge.

---

## Structure du projet

```
presentation-portefolio/
├── backend/
│   ├── app/
│   │   ├── core/                  # Config, base de données, sécurité
│   │   ├── models/                # Modèles SQLAlchemy
│   │   ├── routers/                # Endpoints FastAPI (jobs, cv, explore, market, feedback, chat, company...)
│   │   ├── schemas/                # Schémas Pydantic
│   │   └── services/
│   │       ├── job_crew/           # Agents CrewAI (Parser, Analyste, Rédacteur)
│   │       ├── company_crew/       # Agents fiche entreprise (LangChain LCEL)
│   │       ├── gmail_alerts/       # Parsing alertes email
│   │       ├── orchestrator_client.py  # Wake + heartbeat vers l'orchestrateur OVH
│   │       ├── market_queries.py
│   │       ├── excluded_companies.py
│   │       └── bigquery_client.py
│   ├── routers/
│   │   ├── sanofi/                 # router, ml.py, rag.py, schemas.py
│   │   ├── savencia/                # router, ml.py, rag.py, schemas.py
│   │   ├── sg/sg_assurances/        # router, ml.py, rag.py, schemas.py
│   │   ├── banque_de_france/        # router, ml.py, rag.py, schemas.py
│   │   └── gestion_patrimoine/      # router.py, schemas.py, profil_agent.py (copie — exécution directe backend)
│   ├── migrations/sql/              # Scripts SQL (001 → 017)
│   ├── scheduler/                   # job_pipeline.py
│   ├── scripts/                     # Scripts utilitaires manuels
│   └── Dockerfile
├── gcp/
│   ├── sync_job/                    # Cloud Run Job (France Travail + Gmail → BigQuery)
│   │   ├── sources/
│   │   │   ├── france_travail.py
│   │   │   └── gmail_alerts/        # 10 parseurs sources
│   │   ├── main.py                  # inclut _trigger_dbt_job (fire-and-forget)
│   │   └── Dockerfile
│   ├── dbt_transformation/          # Cloud Run Job — couche dbt Observatoire Emploi
│   │   ├── models/
│   │   │   ├── staging/             # stg_offres (dédup id_unique)
│   │   │   ├── intermediate/        # int_offres_agg_jour / entreprise / localisation
│   │   │   └── marts/               # vide pour l'instant
│   │   ├── profiles.yml
│   │   ├── entrypoint.sh
│   │   ├── Dockerfile
│   │   └── infra/                   # Terraform SA pipeline-dbt + IAM
│   └── infra/                       # Terraform GCP (sync job, scheduler, secrets)
├── ovh/
│   ├── orchestrator/                # Orchestrateur wake-on-demand
│   │   ├── registry.yaml            # déclaration des services (inclut gestion-patrimoine-ml, port 8008)
│   │   ├── docker_client.py
│   │   ├── resource_manager.py
│   │   ├── timer_manager.py
│   │   └── main.py                  # API FastAPI /wake /heartbeat /status /health
│   └── docker-compose.yml
├── realisations/
│   ├── sanofi/
│   │   ├── ml/                      # graph_rag.py, neo4j_ingestion.py, pipeline_orchestrator.py
│   │   └── training/                 # finetune.py, export_gguf.py, evaluate.py, register_model.py
│   ├── savencia/
│   │   ├── pipeline/                 # ETL Google News + Trafilatura
│   │   └── scripts/                  # check_data.py, inspect_chromadb.py, reset_chromadb.py
│   ├── sg/sg-assurances/
│   │   ├── ml/, embedding-service/, serving/, training/
│   │   └── scripts/
│   ├── banque-de-france/
│   │   ├── pipeline/                 # ETL veille RSS + décisions ACPR
│   │   ├── ml/                       # classification_inference.py, eba_service.py, topic_modeling.py
│   │   ├── training/                 # classification/, eba/, ner/ (backlog), webstat/ (backlog)
│   │   └── scripts/                  # check_data.py, inspect_chromadb.py
│   └── gestion-patrimoine/
│       ├── pipeline/                 # ETL Légifrance (API PISTE) — collectors/loaders/transformation/validators
│       ├── agents/                   # profil_agent.py, assistant_agent.py, tools.py (function calling ReAct)
│       ├── ml/                       # main.py (FastAPI /chat), config.py, Dockerfile, docker-compose.yml
│       └── scripts/                  # check_data.py
├── infra/                            # Terraform Scaleway
└── frontend/
    ├── app/
    │   ├── cv/, chat/, jobs/, companies/, explore/, market/
    │   └── realisations/
    │       ├── sanofi/
    │       ├── savencia/
    │       ├── sg/sg-assurances/
    │       ├── banque-de-france/
    │       └── gestion-patrimoine/
    ├── components/
    │   ├── sanofi/ml/, savencia/ml/, sg/sg-assurances/ml/, banque-de-france/ml/
    │   ├── gestion-patrimoine/       # ProfilGenerator.tsx, ChatAssistant.tsx
    │   └── ui/                       # shadcn/ui
    ├── lib/                          # api.ts, sanofiApi.ts, savenciaApi.ts, sgApi.ts, banqueApi.ts, gestionPatrimoineApi.ts
    └── Dockerfile
```

---

## Roadmap

### Court terme
- **Merger `feature/gestion-patrimoine-mvp` dans `infra-scaleway-v1.1`** une fois la stratégie de cohabitation RAM/CPU des `llama-server` tranchée (voir ci-dessous)
- Trancher la cohabitation des 3 `llama-server` toujours-actifs (SG, Sanofi, Gestion Patrimoine) sur un VPS à RAM/CPU limités : upgrade VPS OVH, ou conteneuriser les `llama-server` pour les rendre pilotables par l'orchestrateur wake-on-demand
- Mettre à jour `docker-compose` sur OVH (bug `KeyError: 'ContainerConfig'`, incompatibilité avec le moteur Docker actuel — impacte potentiellement tous les MVPs, contourné ponctuellement par `docker rm -f` + `DOCKER_BUILDKIT=0`)
- Toujours isoler le nom de projet Docker Compose (`-p <nom>`) sur OVH — plusieurs dossiers `ml/` homonymes entre MVPs créent une confusion de nommage de conteneurs
- Finaliser le backlog Release 2 Sanofi (règle iptables persistante, streaming Graph RAG, LangSmith sur Graph RAG)
- MVP Mirakl — E-commerce NLP/GenAI
- Banque de France : Webstat (détection d'anomalies, série à fréquence adaptée à trouver) et NER (établissement, base légale) sur les décisions ACPR

### Moyen terme
- Automatisation Cloud Run Jobs pour les MVPs (refresh périodique des pipelines ML)
- Pipeline de scraping qualifié complet des offres partenaires (BM25 → filtre LLM local → scraping)
- `NEXT_PUBLIC_ENV` pour conditionner `isDev` en prod
- Domaine custom Scaleway
- Investiguer la cause du timeout `embedding-service` observé au premier wake à froid (Gestion Patrimoine) — `WAKE_TIMEOUT_SEC` potentiellement trop court

### Long terme
- Multi-utilisateur onboarding (upload CV PDF + extraction LLM)
- LangGraph pour orchestration du scraping
- Pattern multi-secteurs réplicable (autres comptes cibles)

---

## Ce qui différencie ce projet

- **Construit seul**, de bout en bout : data engineering, ML training, MLOps, DevOps, frontend
- **En production réelle** : chaque composant est containerisé, déployé, monitoré — pas des notebooks
- **Piloté par un objectif métier concret** : décrocher un CDI Data Scientist à Paris
- **Architecture scalable** : pattern IaC Terraform + GitHub Actions reproductible à chaque nouveau secteur
- **Décisions pragmatiques assumées** : seuils MVP acceptés (mAP50=0.51, F1=0.84), coût OVH CPU préféré à Vertex AI T4 permanent, on-demand plutôt que toujours-allumé, function calling simulé par prompt plutôt que natif quand la robustesse prime sur l'élégance

---

## Licence

Projet personnel — tous droits réservés.

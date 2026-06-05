# Portfolio CV — Iandry RAKOTONIAINA

Plateforme full-stack d'intelligence de recherche d'emploi, servant simultanément de **portfolio interactif** et d'**outil personnel de candidature**, construite autour d'une stack data/AI moderne déployée sur Scaleway et GCP.

🔗 **Démo live** : [portfoliocvcy2iktuv-portfolio-cv-frontend.functions.fnc.fr-par.scw.cloud](https://portfoliocvcy2iktuv-portfolio-cv-frontend.functions.fnc.fr-par.scw.cloud/)
📁 **Repo** : [github.com/iandry357/presentation-portefolio](https://github.com/iandry357/presentation-portefolio/tree/infra-scaleway-v1.1)

---

## Ce que fait la plateforme

| Module | Description |
|---|---|
| **CV interactif** | Chatbot RAG (BM25 + VoyageAI embeddings + reranking) qui répond aux questions sur le parcours |
| **Matching d'offres** | Collecte automatique France Travail + Gmail alerts, scoring hybride, enrichissement agents LLM |
| **Tracker de candidatures** | Suivi des offres avec statuts, ajout manuel ; enrichissement offre via CrewAI + fiche entreprise via LangChain LCEL (`company_crew`) ; suivi des pipelines via LangSmith |
| **Explorer** | Parcours paginé de toutes les offres collectées avec filtres avancés |
| **Observatoire Marché** | Analytics BigQuery temps réel sur le marché de l'emploi data/ML (Q01–Q11) |
| **Feedback** | Système de retour visiteur intégré sur toutes les pages |
| **Réalisations** | MVPs sectoriels — pipeline ETL données publiques → ChromaDB (OVH) → RAG LLM ; MVP en production |

---

## Architecture globale

```
Frontend (Next.js — Scaleway)
          │
          │ HTTP/REST
          ▼
Backend (FastAPI — Scaleway Serverless Container)
          │
          ├── RAG Chatbot ──────────────────► PostgreSQL + pgvector (Scaleway)
          │
          ├── Pipeline Jobs
          │     ├── Collecte France Travail API
          │     ├── Collecte Gmail alerts (10 sources)
          │     ├── Scoring hybride (BM25 + VoyageAI + rerank-2)
          │     └── Enrichissement CrewAI (Parser → Analyste → Rédacteur)
          │
          ├── API Jobs / CV / Explorer / Market / Feedback
          │
          └── GCP BigQuery ◄──────────────── Cloud Run Job (sync-ft-bigquery)
                                                    ▲
                                              GCP Workflows
                                                    ▲
                                           Cloud Scheduler (3 triggers)
```

---

## Infrastructure

### Scaleway
| Ressource | Usage |
|---|---|
| Serverless Container | Backend FastAPI (`min_scale=0` + lazy loading) |
| Serverless Container | Frontend Next.js |
| PostgreSQL managé + pgvector | Données candidat, offres trackées, embeddings |
| Container Registry | Images Docker backend + frontend |
| Secret Manager | Secrets applicatifs |

### GCP (projet `gen-lang-client-0989575872`)
| Ressource | Usage |
|---|---|
| BigQuery `emploi_marche.offres_brutes` | Source de vérité des offres marché (partitionné `date_publication`, clustérisé `source, code_rome`) |
| Cloud Run Job `sync-ft-bigquery` | Pipeline de collecte France Travail + Gmail → BigQuery |
| Cloud Scheduler × 3 | Sync 7h/12h quotidien + exploration ROME 1er/15 du mois |
| GCP Workflows | Orchestration Scheduler → Cloud Run Job |
| Secret Manager | Secrets pipeline GCP (`ft-client-id`, `ft-client-secret`, `gmail-token`, `gmail-credentials`) |
| Cloud Storage `portfolio-emploi-config` | Configuration ROME codes + liste entreprises exclues |
| Artifact Registry `europe-west9` | Image Docker Cloud Run Job |

### OVH VPS-1
- **ChromaDB** — base vectorielle active, utilisée par les MVPs Réalisations (requêtes depuis le backend Scaleway)

---

## Stack technique

| Couche | Technologies |
|---|---|
| Frontend | Next.js App Router, TypeScript, Tailwind CSS, shadcn/ui, Recharts, TipTap, ReactMarkdown |
| Backend | FastAPI, Python, SQLAlchemy (async), asyncpg, Pydantic |
| Pipeline IA | CrewAI, LangChain LCEL, LiteLLM |
| LLMs | GPT-4o-mini (OpenAI), magistral-small (Mistral), Gemini (GCP) |
| Embeddings / Rerank | VoyageAI `voyage-3`, `rerank-2` |
| Bases de données | PostgreSQL + pgvector (Scaleway), BigQuery (GCP) |
| Recherche web | DuckDuckGo (`backend="html"`), Brave Search API |
| Matching ROME | ROMEO v2 API |
| Monitoring | LangSmith (projet `portfolio-rag` — traces CrewAI + company_crew), Langfuse (partiel) |
| Infra as Code | Terraform (Scaleway `infra/` + GCP `gcp/infra/`) |
| CI/CD | GitHub Actions + Docker |

---

## Pages de la plateforme

| Route | Description |
|---|---|
| `/` | Landing page |
| `/cv` | CV statique rendu depuis PostgreSQL |
| `/cv/edit` | Interface CRUD expériences (Chantier 1A) |
| `/chat` | Chatbot RAG interactif |
| `/jobs` | Tracker candidatures avec scoring et enrichissement CrewAI |
| `/jobs/[id]` | Fiche détail offre enrichie + recalcul (max 3) |
| `/companies/[id]` | Fiche entreprise enrichie pour préparation entretien |
| `/explore` | Exploration des offres BigQuery avec filtres |
| `/market` | Observatoire marché emploi — catalogue Q01–Q11 sur BigQuery |
| `/realisations` | MVPs sectoriels — pipeline ETL + clustering + RAG sur données publiques |

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
| Jobijoba | — |
| Free-Work | — |
| WTTJ | — |
| Indeed | — |
| JobLeads | — |

> ⚠️ Token OAuth Gmail à régénérer manuellement tous les 7 jours (app en mode Test).  
> Voir `backend/scripts/README_gmail_token.md` pour la procédure.

---

## Prérequis

- Docker et Docker Compose
- Node.js v18+
- Python 3.11+
- Comptes : Scaleway, GCP, VoyageAI, OpenAI, Mistral, LangSmith
- Voir section Variables d'environnement

---

## Installation et lancement

### Avec Docker *(recommandé)*

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

### Sans Docker

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

# Embeddings & Reranking
VOYAGE_API_KEY=

# ROME prediction
ROMEO_API_KEY=

# GCP
GCP_SERVICE_ACCOUNT_JSON=

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

---

## Déploiement

Entièrement automatisé via **GitHub Actions** sur push branche principale :

1. Build images Docker backend + frontend
2. Push sur Scaleway Container Registry
3. Déploiement Serverless Containers Scaleway

L'infrastructure Scaleway est gérée via **Terraform** (`infra/`). L'infrastructure GCP est gérée via **Terraform** (`gcp/infra/`). Aucune modification manuelle via console.

---

## Structure du projet

```
presentation-portefolio/
├── backend/
│   ├── app/
│   │   ├── core/              # Config, base de données, sécurité
│   │   ├── models/            # Modèles SQLAlchemy
│   │   ├── routers/           # Endpoints FastAPI
│   │   ├── schemas/           # Schémas Pydantic
│   │   └── services/
│   │       ├── job_crew/      # Agents CrewAI (Parser, Analyste, Rédacteur)
│   │       ├── market_queries.py
│   │       ├── excluded_companies.py
│   │       └── bigquery_client.py
│   ├── migrations/sql/        # Scripts SQL (001 → 014)
│   ├── scripts/               # Scripts utilitaires manuels
│   │   ├── upload_cv_pdf.py   # Upload CV → PostgreSQL
│   │   └── generate_gmail_token.py  # Régénération token OAuth Gmail
│   └── Dockerfile
├── gcp/
│   ├── sync_job/              # Cloud Run Job (France Travail + Gmail → BigQuery)
│   │   ├── sources/
│   │   │   ├── france_travail.py
│   │   │   └── gmail_alerts/  # 10 parseurs sources
│   │   ├── main.py
│   │   └── Dockerfile
│   └── infra/                 # Terraform GCP
├── infra/                     # Terraform Scaleway
└── frontend/
    ├── app/                   # Pages Next.js
    │   ├── cv/, chat/, jobs/, companies/
    │   ├── explore/, market/
    │   └── realisations/
    ├── components/            # Composants React
    └── Dockerfile
```

---

## Licence

Projet personnel — tous droits réservés.
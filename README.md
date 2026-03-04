# Portfolio CV — Iandry RAKOTONIAINA

Application web full-stack servant à la fois de **portfolio interactif** et de **terrain d'expérimentation** autour du déploiement cloud, de l'IA générative et de l'orchestration d'agents LLM.

🔗 **Démo live** : [portfoliocvcy2iktuv-portfolio-cv-frontend.functions.fnc.fr-par.scw.cloud](https://portfoliocvcy2iktuv-portfolio-cv-frontend.functions.fnc.fr-par.scw.cloud/)

---

## Ce que fait l'application

- **CV interactif** — chatbot RAG qui répond aux questions sur le parcours, les compétences et les expériences à partir d'un CV vectorisé
- **Pipeline de matching d'offres** — collecte automatique d'offres France Travail, scoring hybride (BM25 + embeddings + reranking), enrichissement par agents LLM
- **Gestion des offres** — visualisation, filtrage, statuts (enregistré, postulé, manuel), ajout manuel d'offre

---

## Architecture

```
Frontend (Next.js)
      │
      │ HTTP/REST
      ▼
Backend (FastAPI)
      │
      ├── RAG Chatbot ──────────────────► PostgreSQL + pgvector
      │
      ├── Pipeline Jobs (APScheduler)
      │     ├── Collecte (France Travail API)
      │     ├── Scoring (BM25 + VoyageAI)
      │     └── Enrichissement (CrewAI agents)
      │
      └── API Jobs / CV
```

Le backend tourne dans un **Serverless Container Scaleway**. La base de données est un **PostgreSQL managé Scaleway** avec l'extension `pgvector`. Le frontend est également déployé sur Scaleway. Le CI/CD est géré via **GitHub Actions**.

---

## Stack technique

| Couche | Technologies |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | FastAPI, Python, SQLAlchemy (async), asyncpg |
| Base de données | PostgreSQL, pgvector |
| Pipeline IA | CrewAI, LiteLLM, APScheduler |
| Modèles LLM | OpenAI GPT-4o-mini, Mistral magistral-small |
| Embeddings / Rerank | VoyageAI (voyage-3, rerank-2) |
| Matching ROME | ROMEO v2 API |
| Infra | Scaleway (Containers, PostgreSQL, Registry) |
| CI/CD | GitHub Actions, Docker |

---

## Prérequis

- [Docker](https://www.docker.com/) et Docker Compose
- [Node.js](https://nodejs.org/) v18+ *(si lancement sans Docker)*
- [Python](https://www.python.org/) 3.11+ *(si lancement sans Docker)*
- Clés API : voir section [Variables d'environnement](#variables-denvironnement)

---

## Installation et lancement

### Avec Docker *(recommandé)*

```bash
git clone https://github.com/iandry357/presentation-portefolio.git
cd presentation-portefolio
```

Créer les fichiers `.env` (voir section suivante), puis :

```bash
# Lancer backend + base de données
cd backend
docker compose up --build

# Lancer le frontend (dans un autre terminal)
cd frontend
docker build -t portfolio-frontend .
docker run -p 3000:3000 --env-file .env portfolio-frontend
```

### Sans Docker

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows : .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend**
```bash
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
```

### Frontend — `frontend/.env.local`

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_FT_BASE_URL=https://candidat.francetravail.fr/offres/recherche/detail
```

---

## Déploiement

Le déploiement en production est entièrement automatisé via **GitHub Actions** à chaque push sur la branche principale.

1. **Build** — les images Docker backend et frontend sont construites
2. **Push** — les images sont poussées sur le **Scaleway Container Registry**
3. **Deploy** — les Serverless Containers Scaleway sont mis à jour avec les nouvelles images

Les variables d'environnement de production sont injectées directement dans les containers via les secrets GitHub Actions et la configuration Scaleway.

---

## Structure du projet

```
presentation-portefolio/
├── backend/
│   ├── app/
│   │   ├── core/          # Config, base de données, sécurité
│   │   ├── models/        # Modèles SQLAlchemy
│   │   ├── routers/       # Endpoints FastAPI
│   │   ├── schemas/       # Schémas Pydantic
│   │   └── services/
│   │       └── job_crew/  # Agents CrewAI (Parser, Analyste, Rédacteur)
│   ├── scheduler/         # Pipeline APScheduler
│   ├── migrations/        # Scripts SQL
│   └── Dockerfile
└── frontend/
    ├── app/               # Pages Next.js (cv, chat, jobs)
    ├── components/        # Composants React
    ├── lib/               # Utilitaires et appels API
    └── Dockerfile
```

---

## Licence

Projet personnel — tous droits réservés.

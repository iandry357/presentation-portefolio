# presentation-portefolio — Instructions Claude Code

Plateforme full-stack solo, à double vocation : portfolio technique live (MVPs sectoriels ML/AI déployés)
et outil de veille emploi utilisé au quotidien. Monorepo `iandry357/presentation-portefolio`.
Vue d'ensemble détaillée : `README.md` (à lire au besoin, section par section).

## Rôle et méthode de travail (prioritaire)

- Tu es mon assistant codeur avec une **posture d'architecte** : projet pensé pour la scalabilité,
  répertoires bien découpés, chaque script à sa place.
- Sois **précis et terre à terre**. Si tu ne sais pas, dis-le ; ne devine pas un nom de fichier,
  de variable, de table ou de port : vérifie dans le code ou demande-moi.
- **Jamais de code sans validation.** Une validation = un « ok » explicite de ma part sur le
  **contenu exact** du diff, affiché au préalable dans la réponse. Un accord sur un plan, une
  approche ou un principe (« go », « d'accord ») n'autorise **jamais** à écrire. En cas de doute,
  tu demandes. Cela couvre Edit, Write et NotebookEdit, y compris pour un changement d'une ligne.
  La validation est **par fichier** : le diff affiché regroupe **tous** les changements prévus
  dans ce fichier (une seule vue globale, un seul « ok »), puis on passe au fichier suivant.
  Un changement supplémentaire sur un fichier déjà validé demande une nouvelle validation.
  Techniquement : un seul appel d'édition par fichier (une confirmation de l'IDE par fichier).
  Déroulé obligatoire :
  1. je décris le besoin ;
  2. on affine ensemble ;
  3. tu proposes la mise en place ;
  4. je valide explicitement ;
  5. seulement ensuite tu codes.
- Pendant les échanges de raisonnement : **illustrations de haut niveau uniquement** (schémas ASCII,
  tableaux, arborescences). **Jamais de code ni de pseudo-code** à ce stade.
- **Création de fichiers** : avant d'écrire dans un fichier qui n'existe pas encore, donne-moi un
  script Cmder (Windows, `.bat`) qui crée les dossiers et fichiers vides. Je l'exécute moi-même,
  puis tu remplis les fichiers.
- **Modification de code** : modifications ciblées (diffs), jamais de réécriture complète d'un fichier
  sans demande explicite. Ne touche pas à un fichier hors du périmètre validé.
  **Mode d'application** : pour toute modification de code existant, quels que soient le nombre de fichiers et la
  taille, tu me présentes d'abord les éléments à copier-coller (par fichier, avec l'emplacement exact, et le numéro
  des lignes concernées), puis tu me demandes : « tu l'appliques toi-même, ou on passe en validation ? ». Si je
  l'applique, tu n'utilises ni Edit ni Write. Si je choisis la validation, comportement de base : diff global par
  fichier, un seul « ok », puis tu écris. Nouveaux fichiers : script Cmder d'abord, puis le contenu proposé de la
  même façon.
- Réponses en français, directes et denses, sans préambule.

## Ce que tu ne fais pas (et pourquoi)

- **Tu n'exécutes rien.** Tu n'as pas de shell. Quand une commande est nécessaire (test, build,
  docker, terraform, git), donne-la-moi prête à copier pour Cmder, avec le résultat attendu.
  Je l'exécute et je te renvoie la sortie.
- **Tu ne lis jamais de secret** (`.env`, clés GCP, `tfvars`, `tfstate`, tokens OAuth). Les règles
  `.claude/settings.json` le bloquent. Pour les noms de variables : lis le `.env.example`
  correspondant ou demande-moi. Ne me demande jamais une valeur.
- Tu n'écris ni ne modifies aucun fichier avant d'avoir affiché le diff dans ta réponse et reçu
  mon « ok » sur ce diff. Si une erreur de ce type survient, tu le dis, tu montres le diff
  appliqué et tu proposes l'annulation, sans te justifier.
- Tu ne proposes jamais de commiter un secret, de faire un `docker system prune` / `docker image prune`
  global, ni de modifier l'infra à la main via une console (tout passe par Terraform).

## Carte du repo

| Dossier | Rôle |
|---|---|
| `backend/` | API FastAPI (Scaleway). `app/` = cœur (core, models, routers, schemas, services) ; `routers/<mvp>/` = endpoints des MVPs ; `migrations/sql/`, `scheduler/`, `scripts/` (dont OAuth Gmail) |
| `frontend/` | Next.js App Router + TypeScript + Tailwind + shadcn/ui. `app/` = routes, `components/<module>/`, `lib/`, `types/` |
| `realisations/<mvp>/` | Un dossier autonome par MVP sectoriel (voir pattern ci-dessous) |
| `gcp/` | `infra/` (Terraform GCP commun), `<mvp>/infra/` (Terraform par MVP), `sync_job/` (Cloud Run Job collecte), `dbt_transformation/` (dbt + son Terraform) |
| `infra/` | Terraform Scaleway (`bootstrap/` pour le state) |
| `ovh/` | `orchestrator/` (wake-on-demand, port 8080) + `docker-compose.yml` |
| `chromadb/` | Déploiement ChromaDB (OVH, port 8000) |
| `.github/workflows/` | CI/CD : deploy backend, deploy frontend, Terraform |
| `_docs-local/` | Docs locales non versionnées : `STATUS.md` (reprise, seul fichier chargé automatiquement), `projets/<projet>/` (`avancement.md`, `decisions.md`, `backlog.md`, `historique.md`, lus à la demande), `specs/` (cahiers des charges) |

## Architecture

```
Frontend Next.js (Scaleway Serverless) ──HTTP──► Backend FastAPI (Scaleway Serverless, min_scale=1, max 2)
                                                   ├── PostgreSQL + pgvector (Scaleway)
                                                   ├── contrôle d'accès /access (jeton httpOnly, gardes stricte / souple)
                                                   ├── BigQuery (GCP) : emploi_marche + datasets par MVP
                                                   └── routers MVP ──► orchestrateur OVH :8080 ──► services ML (Docker, wake-on-demand)
GCP : Cloud Scheduler → Workflows → Cloud Run Job sync-ft-bigquery → Cloud Run Job dbt-emploi-marche
      Vertex AI Model Registry (europe-west9), Artifact Registry, Secret Manager, GCS
OVH VPS : ChromaDB 8000 · Sanofi 8001 (+Neo4j 7474/7687, llama 8006) · Savencia 8002 · SG 8003 (+llama 8005)
          · Embedding 8004 (partagé) · Banque de France 8007 · Gestion Patrimoine 8008 (+llama 8009)
```

- Les `llama-server` tournent hors orchestrateur (systemd, always-on) : RAM du VPS = point de vigilance.
- Top Offres s'écarte du pattern MVP : worker local (Windows, Docker, Ollama sur GPU, hors OVH), `agents/` et `dbt/` à la place de `ml/` et `training/` ; seul service OVH utilisé : Embedding 8004 via l'orchestrateur ; le backend lit BigQuery `top_offres` avec un compte de service dédié (`GCP_SERVICE_ACCOUNT_JSON_TOP_OFFRES`).
- Frontend → backend : proxy Next.js `/backend/*` pour jobs / explore / companies / accès (cookies first-party) ;
  les fichiers API des MVPs restent en appel direct (`NEXT_PUBLIC_API_URL`). `BACKEND_URL` = build-arg frontend.
- Détails (tables BigQuery, buckets, secrets, pages frontend) : sections « Infrastructure » et
  « Pages de la plateforme » du `README.md`.

## Pattern d'un MVP (à reproduire pour tout nouveau MVP)

```
realisations/<mvp>/
├── pipeline/   collectors/ · transformers/ · validators/ · loaders/ · orchestrator.py · config.py
│               (+ Dockerfile, docker-compose.yml, requirements.txt)
├── ml/         service FastAPI (main.py) + modules ML, Dockerfile, docker-compose.yml → OVH
├── training/   entraînement local (GPU RTX 5060) ; modèles → Vertex AI Model Registry
└── scripts/    scripts de contrôle / debug ponctuels
gcp/<mvp>/infra/                    Terraform dédié (comptes de service pipeline-<mvp>, terraform-<mvp>)
backend/routers/<mvp>/              endpoints + appel orchestrateur (wake + heartbeat)
frontend/app/realisations/<mvp>/    page + frontend/components/<mvp>/
```

Avant de proposer un nouveau MVP, inspire-toi du MVP existant le plus proche (lis son code) plutôt
que d'inventer une structure.

## Modules de la plateforme

| Module | Route | Ce que ça fait |
|---|---|---|
| CV + chatbot | `/cv`, `/chat` | CV rendu depuis PostgreSQL ; chatbot RAG hybride (BM25 + VoyageAI voyage-3 + rerank-2, LiteLLM) |
| Tracker candidatures | `/jobs`, `/companies/[id]` | Scoring hybride des offres ; enrichissement CrewAI `job_crew` (Parser → Analyste → Rédacteur) ; fiche entreprise LangChain LCEL `company_crew` ; traces LangSmith |
| Explorer | `/explore` | Parcours paginé et filtré des offres BigQuery |
| Observatoire marché | `/market` | Q01–Q10 sur tables dbt agrégées, Q11 direct sur `offres_brutes` |
| Collecte emploi | `gcp/sync_job/` | France Travail API + Gmail alerts (10 sources) → `emploi_marche.offres_brutes` → dbt (`gcp/dbt_transformation/`) |
| Feedback | toutes pages | Retour visiteur intégré |
| Accès public / privé | `/access/*`, zones 🔒 | Code unique → jeton serveur httpOnly (15 min glissantes, anti brute-force) ; public : offres sans statut / notes / fiches / `raw_data` ; privé : Explorer, Companies, routes d'écriture jobs ; `lib/api.ts` (helper `request`) via proxy `/backend` |
| Top Offres | `/realisations/top-offres` | Offres classées chaque jour par LLM local ; public : vue d'ensemble (statistiques) ; privé 🔒 : Top du jour (« intéressé » → brouillon `job_offers`), Entreprises, Brouillons ; `backend/routers/top_offres/` |

## MVPs sectoriels

| MVP | Finalité | Briques ML / IA | OVH | Statut |
|---|---|---|---|---|
| Sanofi | Veille R&D pharma (ClinicalTrials, PubMed, News) | KMeans 11 clusters, GLM bayésien Poisson, LDA, RAG ; R2 : OpenTargets → Neo4j Graph RAG + Mistral 7B QLoRA (win-rate 46,7 %) | 8001, Neo4j 7474/7687, llama 8006 | Prod (Release 2) |
| Savencia | Veille agroalimentaire (Google News) | LDA 5 topics, ViT maturité fromagère + Grad-CAM, RAG | 8002 | Prod |
| SG Assurances | Veille + traitement documents assurance | YOLO zones (mAP50 0,51), CamemBERT NER (F1 0,84), QLoRA Qwen2.5-1.5B (win-rate 29 %), RAG | 8003, embedding 8004, llama 8005 | Prod |
| Banque de France | Veille RSS + décisions ACPR (Suptech) | Classification multi-label griefs (CamemBERT + k-NN), scoring EBA déterministe, RAG + LDA sur la veille | 8007 | Prod |
| Gestion Patrimoine | Copilote patrimonial, RAG juridique CGI | `profil_agent` (Mistral/Gemini via LiteLLM) + `assistant_agent` ReAct, Qwen2.5-3B base, citation obligatoire | 8008, llama 8009 | Prod |
| Top Offres | Veille emploi personnelle : classement quotidien des offres collectées selon le profil, top du jour, brouillons vers `/jobs` | Cibles dérivées du profil (LLM local), scoring `gemma4:e4b` (Ollama, lots de 1, rappel 91,4 % à ≥ 60), embeddings OVH, dbt (porte de contrôle, marts) | embedding 8004 via l'orchestrateur ; worker local | Prod |
| Mirakl | E-commerce NLP/GenAI | Sentiment, anomalies prix, agent vendeur (prévu) | — | Prochain MVP |

Métriques, datasets BigQuery et buckets : section « MVPs sectoriels » du `README.md`.

## Conventions

- Git : branches de feature depuis `infra-scaleway-v1.1` ; commits d'infra séparés des commits applicatifs.
- Docker : scripts ponctuels via `docker-compose run --rm` (jamais `exec`) ; `PYTHONUNBUFFERED=1` obligatoire.
- OVH : docker-compose v1.29.2 ; sparse-checkout sur le serveur ; fichiers lourds (modèles, JSON
  pré-calculés) transférés par `scp`, jamais commités.
- Toujours valider en local (Docker) avant déploiement OVH / Scaleway.
- Paramètres configurables en tête de script.
- Pragmatisme MVP : accepter un seuil de métrique raisonnable plutôt que sur-ingénierer.
- Environnement de travail : Windows + Cmder ; chemins Windows dans les commandes que tu me donnes.

## Reprise de session

Le suivi de reprise (feature en cours, tableau des projets, où je me suis arrêté, prochaine étape) est dans
`_docs-local/STATUS.md`, chargé automatiquement via `CLAUDE.local.md`. Commence toute nouvelle tâche en
t'appuyant dessus. `STATUS.md` reste court (environ 50 lignes) : le détail est dans
`_docs-local/projets/<projet>/`, à lire à la demande (jamais importé) :
- `avancement.md` : résumé, objectif, étapes, résultats clés ;
- `decisions.md` : décisions cumulatives ;
- `backlog.md` : points ouverts, avec statut (ouvert / à vérifier / reporté / accepté) ;
- `historique.md` : une ligne par session.

Toute mise à jour de suivi passe par le skill `/livraison` (lancé par moi seul), jamais à la main :
- fin de session (`/livraison`) : `STATUS.md` + les 4 fichiers du projet concerné + cahier des charges de la feature (`_docs-local/specs/`) ;
- fin de MVP (`/livraison mvp`) : en plus `CLAUDE.md` et `README.md`.

Quand je dis vouloir m'arrêter, rappelle-moi `/livraison` au lieu de mettre à jour ces fichiers toi-même.
À la question « où en est-on ? », lis `STATUS.md` puis `avancement.md` du projet concerné, et réponds dans
l'ordre : résumé de la feature, objectif, ce qui est fait, puis seulement la suite. Pour une question sur le
backlog, lis `backlog.md` du projet.
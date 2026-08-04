# MVP Banque de France — Récap technique & Architecture

*Cible : offre Data Scientist Suptech (ACPR), en complément du MVP SG Assurances.*
*Branche Git : `feature/banque-de-france-mvp`*

---

## 1. Vue d'ensemble

Le MVP réutilise le pattern déjà en production sur les autres réalisations (pipeline ETL → ML Service OVH → Backend Scaleway → Frontend Next.js), appliqué à un cas d'usage de supervision bancaire française.

| Module | Statut | Ce qu'il fait |
|---|---|---|
| **Classification multi-label** | ✅ En production | Prédit le(s) grief(s) de manquement d'une décision de sanction ACPR (4 catégories) |
| **RAG** | ✅ En production | Répond aux questions sur la veille réglementaire (Banque de France / ACPR) |
| **Topic Modeling** | ✅ En production | LDA sur la veille — regroupement thématique automatique |
| **Scoring composite EBA** | ✅ En production | Indicateur comparatif de robustesse financière (CET1 / levier / NPL) des 6 grandes banques françaises vs moyenne UE |
| **Webstat (anomalies)** | ⏸️ Backlog | Détection d'anomalies temporelles — fréquence des séries disponibles jugée insuffisante (annuelle, 9 points) |
| **NER (établissement, base légale)** | ⏸️ Backlog | Extraction d'entités sur les décisions ACPR — chantier lourd (double entraînement CamemBERT/Flair sur WikiNER-FR) pour un gain surtout méthodologique |

---

## 2. Choix sur la récupération des données

### 2.1 Veille réglementaire (automatisée)
- 2 flux RSS Google News (`"Banque de France" actualités`, `ACPR "Commission des sanctions"`)
- Extraction de contenu via Trafilatura, avec le même piège déjà documenté ailleurs sur le projet (`entry.link` = URL de redirection Google, bon pour l'affichage ; `source.href` = URL réelle, seule utilisable pour l'extraction de contenu)

### 2.2 Décisions ACPR (semi-automatisé)
- Découverte automatique du Recueil des sanctions ACPR (page unique, non paginée)
- Résolution des liens PDF (directs ou via page intermédiaire), extraction texte (PyMuPDF → pdfplumber en fallback)
- Cache local persistant pour éviter le retraitement à chaque run
- **105 décisions** récupérées, **1924 chunks** ChromaDB

### 2.3 EBA Transparency Exercise (manuel, choix assumé)
Contrairement à la veille RSS, ces données **ne sont pas automatisables de façon rentable** : pas d'API officielle, seulement des CSV téléchargeables sur le site EBA, dont l'URL change chaque année (ID numérique imprévisible) et dont la publication n'a lieu qu'**une fois par an**. Construire et maintenir un scraper pour économiser un clic annuel n'a pas de sens — acquisition manuelle assumée, à l'inverse du cas ACPR où l'automatisation se justifiait (mises à jour plus fréquentes).

### 2.4 Webstat (API ouverte, non exploitée pour l'instant)
Une API REST ouverte existe bien (OpenDataSoft, sans authentification), donc automatisable techniquement — mais la série candidate identifiée (ratio de solvabilité CET1 du secteur bancaire français) n'est publiée qu'en **fréquence annuelle** (9 points sur 2016-2024), insuffisante pour une détection d'anomalies temporelles fiable. Mis en backlog plutôt que de livrer un module peu robuste.

---

## 3. Choix méthodologiques

### 3.1 Classification multi-label des griefs
- **Construction de la taxonomie** (le plus gros du travail) : le champ `motif` brut mélange type d'établissement et grief réel. Plusieurs approches automatiques ont échoué (règles heuristiques, clustering d'embeddings, LLM segment par segment) avant de converger sur une taxonomie figée en 4 macro-catégories, documentée dans `taxonomy_mapping.json` (artefact figé, à ne jamais régénérer sans repasser par le notebook d'exploration).
- **Architecture du modèle** : corps `sentence-camembert-base` fine-tuné (paires générées par similarité Jaccard multi-label) + une tête k-NN indépendante par catégorie (`k = min(5, n_positifs)`, poids par distance).
- **Seuil de décision par catégorie** : dérivé du déséquilibre positif/négatif observé à l'entraînement (`n_pos / (n_pos + n_neg)`), pas un seuil fixe à 0.5 — cohérent avec des catégories très déséquilibrées sur un corpus de ~100 décisions.
- **Limite assumée et documentée** : F1 fragile sur les catégories les moins représentées (ex. gouvernance et maîtrise des risques, F1 ≈ 0.5) — pas masqué, affiché tel quel dans les métriques du modèle enregistré.
- **Réentraînement final** (`train_final.py`) : mêmes hyperparamètres que le K-Fold d'évaluation, mais sur l'intégralité du pool (pas de split), pour maximiser la donnée disponible sur l'artefact réellement déployé.

### 3.2 Scoring composite EBA
- **3 ratios retenus** : CET1 fully loaded (solvabilité), ratio de levier fully phased-in (garde-fou anti-manipulation du calcul pondéré du risque), NPL ratio (qualité du portefeuille de crédit) — calculés à partir des montants bruts (numérateur/dénominateur), pas des items pré-calculés du fichier (qui disparaissent ou changent de libellé d'une année à l'autre).
- **Pondération égale, assumée** : pas de base actuarielle pour privilégier un ratio plutôt qu'un autre — poids neutre plutôt qu'une pondération non justifiable.
- **Score = moyenne des écarts vs moyenne UE simple** (non pondérée par la taille de bilan), exprimé en points de pourcentage, toujours accompagné du détail des 3 écarts (jamais affiché seul).
- **Couverture volontairement arrêtée à décembre 2024** : à partir de mars 2025, l'EBA ne publie plus les items "fully loaded" (transition CRR3 en cours) — plutôt que de mélanger deux régimes de calcul différents dans une même série, la période la plus complète et homogène est retenue.
- **Pas de ML** : un calcul déterministe et transparent, pas un modèle entraîné — choix assumé pour rester interprétable en toute circonstance.

### 3.3 Topic Modeling & RAG — périmètre volontairement restreint
Les deux modules sont **restreints à la veille** (`source = google_news`), à l'exclusion des décisions ACPR — pour ne pas mélanger deux registres de langue très différents (actualité courte vs texte juridique long), qui dilueraient le signal du LDA et biaiseraient la pertinence sémantique du RAG.

### 3.4 Mutualisation de l'embedding-service
Le service d'embeddings (`sentence-transformers`, port 8004) était initialement scope SG Assurances uniquement. Réutilisé tel quel pour Banque de France plutôt que dupliqué — service déjà générique (aucune référence à SG dans son code), seul le nom de sa clé dans le registre d'orchestration a été renommé (`sg-embedding` → `embedding-service`, `mvp: sg` → `mvp: shared`) pour refléter l'usage partagé.

---

## 4. Architecture technique

### 4.1 Flux global

```
Pipeline ETL (RSS + ACPR)
        │
        ▼
BigQuery (banque_de_france_veille.articles_bruts)  +  ChromaDB (collection banque_de_france)
        │                                                      │
        │ lecture directe (stats/news)                         │ recherche sémantique
        ▼                                                      ▼
Backend Scaleway (routers/banque_de_france/)  ◄──────  RAG (embedding-service partagé, port 8004)
        │
        ├── GET  /banque-de-france/stats
        ├── GET  /banque-de-france/news
        ├── POST /banque-de-france/rag
        │
        └── orchestrator_client.wake("banque-ml") ──► Orchestrateur OVH :8080
                                                              │
                                                              ▼
                                                    banque-ml-service (port 8007)
                                                       ├── GET  /predict/topic-modeling  (JSON pré-calculé)
                                                       ├── GET  /predict/eba             (JSON pré-calculé, transporté par scp)
                                                       ├── POST /predict/classification  (inférence live, torch CPU)
                                                       └── GET  /predict/classification/examples (demo.csv, 82 décisions)
```

### 4.2 Endpoints backend

| Méthode | Route | Source des données |
|---|---|---|
| GET | `/banque-de-france/stats` | BigQuery direct (dédupliqué sur titre normalisé) |
| GET | `/banque-de-france/news` | BigQuery direct (dédupliqué sur titre normalisé) |
| POST | `/banque-de-france/rag` | ChromaDB + embedding-service + LLM fallback (LiteLLM) |
| GET | `/banque-de-france/ml/topic-modeling` | Proxy → `banque-ml` `/predict/topic-modeling` |
| GET | `/banque-de-france/ml/eba-scores` | Proxy → `banque-ml` `/predict/eba` |
| POST | `/banque-de-france/ml/classification` | Proxy → `banque-ml` `/predict/classification` |
| GET | `/banque-de-france/ml/classification/examples` | Proxy → `banque-ml` `/predict/classification/examples` |

### 4.3 Service ML (`banque-ml`, port 8007)

Contrairement aux autres MVPs, ce service **ne charge un modèle lourd que pour la classification** (corps CamemBERT + têtes k-NN, téléchargés depuis GCS au démarrage). Topic Modeling et EBA sont de simples lectures de fichiers pré-calculés (`results/*.json`), sans coût d'inférence à la requête.

| Composant | Poids dans l'image | Dépendances |
|---|---|---|
| `main.py` (FastAPI, lifespan) | — | fastapi, uvicorn |
| `classification_inference.py` | torch CPU + sentence-transformers + transformers (versions alignées sur celles de l'entraînement local, `5.6.0`/`5.14.1`) | gcloud CLI (téléchargement GCS au démarrage) |
| `eba_service.py` | — | lecture JSON seule |
| `topic_modeling.py` (script one-shot, pas un endpoint permanent) | scikit-learn, litellm | BigQuery |

### 4.4 Modèles enregistrés — Vertex AI Model Registry

| Modèle | Resource | Registre uniquement |
|---|---|---|
| Classification griefs ACPR | `projects/870096195586/locations/europe-west9/models/2802285703294091264` | ✅ Aucun endpoint Vertex déployé — service d'inférence sur OVH uniquement |

Bucket GCS : `gs://banque-de-france-models/banque-de-france/classification/` (corps d'embeddings + 4 têtes k-NN + `categories.json`).

### 4.5 Infrastructure — récapitulatif des services

| Couche | Ressource |
|---|---|
| GCP | Dataset BigQuery `banque_de_france_veille`, bucket `banque-de-france-models`, SA `pipeline-banque-de-france`, Vertex AI Model Registry |
| OVH | ChromaDB (collection `banque_de_france`, partagée avec le reste du VPS), `banque-ml-service` (port 8007), `embedding-service` (port 8004, partagé avec SG) |
| Scaleway | Routes backend `routers/banque_de_france/`, page frontend `/realisations/banque-de-france` |

# MVP Top Offres — Récap technique & Architecture

*Outil de veille emploi personnel : classe chaque jour les offres collectées selon leur pertinence pour un profil (cibles de postes, LLM local) et les expose sur la plateforme.*
*Branche Git : `feature/top-offres` · en production depuis le 2026-10-18*

---

## 1. Vue d'ensemble

Le MVP s'appuie sur la collecte emploi déjà en place (France Travail + alertes Gmail → BigQuery → dbt) et ajoute un worker local qui note les offres avec un LLM sur GPU, puis un backend et une page pour les exploiter.

| Module | Statut | Ce qu'il fait |
|---|---|---|
| **Cibles de postes** | ✅ En production | 8 cibles dérivées du profil (`experiences`) par un LLM local, validées à la main, versionnées |
| **Sélection et filtres (dbt)** | ✅ En production | Fenêtre réglable, dédoublonnage, filtres durs marqués (stage, alternance, hors Île-de-France) |
| **Enrichissement des entreprises** | ✅ En production | API Recherche d'entreprises (NAF, catégorie), type d'annonceur, secteur (NAF ou recherche web + LLM local), cache de 90 jours |
| **Scoring LLM local** | ✅ En production | Score 0-100, catégorie (cœur / adjacent / hors cible), raison et alertes par offre ; similarité par embeddings avec les cibles |
| **Porte de contrôle + marts (dbt)** | ✅ En production | Tests avant fusion ; `offres_scores`, `mart_top_du_jour`, `mart_stats` |
| **Top du jour (privé)** | ✅ En production | Deux listes (à lire, zone grise), décisions « intéressé / pas intéressé », brouillons vers le suivi de candidatures |
| **Entreprises (privé)** | ✅ En production | Tableau triable : secteur, type, répartition cœur / adjacent / hors cible, offres dépliables avec lien |
| **Vue d'ensemble (publique)** | ✅ En production | Tuiles et graphiques sur les offres scorées |
| **Planificateur Windows** | ⏸️ Backlog | Le run quotidien est lancé à la main (`scripts\run_quotidien.bat`) |
| **Clôture de l'évaluation (E10)** | ⏸️ Backlog | Objectif de rappel (D6), garde-fou GPU, révision du prompt de scoring |

---

## 2. Choix sur la récupération des données

### 2.1 Offres (collecte existante)
- Collecte deux fois par jour (7h et 12h, Europe/Paris) : API France Travail et alertes Gmail de plusieurs plateformes, vers `emploi_marche.offres_brutes`, exposée par la vue dbt `stg_offres`. Top Offres ne collecte rien : il lit `stg_offres` en lecture seule.
- **Métadonnées seulement** (titre, entreprise, lieu, contrat, salaire, lien) : le contenu des annonces n'est pas collecté (scraping abandonné pour raisons de CGU). Conséquence assumée : le scoring juge sur le titre et le contexte de l'entreprise ; la description d'une offre retenue est collée à la main lors de la création du brouillon.
- Les liens des alertes e-mail sont des **liens de suivi** : leur durée de validité n'est pas garantie.

### 2.2 Profil
Lecture de la table PostgreSQL `experiences` par un utilisateur dédié en **lecture seule** (`top-offres-reader`). Le worker n'écrit jamais en PostgreSQL ; seul le backend écrit, et seulement ses deux tables propres (voir 4.3).

### 2.3 Entreprises
- **API publique Recherche d'entreprises** : recherche par nom seul, cache de 90 jours, plafond de 200 appels par exécution. Entrepreneurs individuels et établissements inactifs écartés ; un candidat ambigu est conservé avec l'origine `a_valider` plutôt que jeté.
- **Entreprises exclues** : liste `excluded_companies.json` (bucket de configuration) copiée dans BigQuery à chaque run. Leurs offres sont scorées comme les autres et **marquées** (`entreprise_exclue`), jamais masquées par le mart : l'affichage choisit de les montrer.
- **Secteur** : section NAF si le NAF est exploitable ; sinon (holdings, NAF absent, entreprise non trouvée), recherche web gratuite (méta-moteur `ddgs`) puis LLM local, jusqu'à 3 essais, `NON DETERMINE` si non concluant ; plafond de 50 entreprises par run. Pas de recherche pour les intermédiaires.

---

## 3. Choix méthodologiques

### 3.1 Cibles de postes
Dérivées du profil par un LLM local (`gemma3:12b`, sortie contrainte par schéma JSON) : 5 à 12 cibles avec intitulé, niveau (cœur / adjacent), justification, variantes de titres et description. Une version est proposée, relue et corrigée à la main, puis validée (une seule version active ; la précédente est archivée). La version des cibles entre dans la `version_scoring` : changer de cibles re-score tout.

### 3.2 Filtres durs et dédoublonnage
- Stages et alternances exclus, hors Île-de-France exclu **seulement si le département est identifié** (inconnu : l'offre est conservée). Une offre n'est jamais supprimée : elle est marquée avec un motif.
- Même titre normalisé + même entreprise normalisée = un groupe de doublons ; un seul représentant est scoré, les autres héritent de son score.
- **Information manquante jamais pénalisante** : entreprise inconnue, intermédiaire ou lieu illisible = neutre.

### 3.3 Scoring par LLM local
- **Modèle** `gemma4:e4b` sur Ollama (GPU local de 8 Go de VRAM) ; raisonnement désactivé, contexte de 8 192 jetons, sortie JSON contrainte par schéma.
- **Entrée par offre** : titre, entreprise, lieu, contrat, salaire, type d'annonceur, NAF, cible la plus proche et similarité, plus les cibles validées et un résumé court du profil.
- **Une offre par appel** (lots de 1) : c'est la taille de lot qui élimine l'instabilité mesurée (écart moyen de 11,5 à 16 points entre copies identiques de la même offre en lots de 5 à 20, **0 en lots de 1**).
- **Pré-score par embeddings** (`paraphrase-multilingual-mpnet-base-v2`, 768 dimensions, service OVH partagé) : similarité titre ↔ cibles, utilisée comme contexte du LLM et pour départager à score égal, jamais comme filtre.
- **Seuils** : `a_lire` à partir de 75, `zone_grise` de 60 à 74, `masque` en dessous (ou sur filtre dur).
- **Garde-fou** : après 3 offres consécutives en erreur d'appel (Ollama injoignable, timeout), le run s'arrête ; un JSON invalide ne compte pas, l'offre est retentée seule une fois.

### 3.4 Évaluation
- **Test de rappel** : les 104 offres de `job_offers` au statut `postule` ou `enregistre` (72 et 32) passées dans la même chaîne sans écrire en base. Le rappel est bruité (environ 3 points).
- **Benchmark de 5 modèles** sur un même jeu (positifs + échantillon de 200 offres + 50 copies exactes pour la stabilité) : `gemma4:e4b` retenu, à charge de lecture égale équivalent à `qwen3.5:4b`, 1,75 fois plus rapide, plus stable ; `mistral:latest`, `phi4-mini` et `mistral-nemo` écartés.
- **Balayage de la taille de lot** (même jeu, `gemma4:e4b`) : rappel à ≥ 60 de 86,7 / 89,5 / 87,6 / 91,4 % pour des lots de 20 / 10 / 5 / 1.

### 3.5 Porte de contrôle avant fusion
Le scoring écrit dans une table de staging ; dbt teste ce staging avant de le fusionner (tests de colonnes sur la source + 5 tests singuliers : nombre de lignes, taux d'erreur LLM ≤ 5 %, score et catégorie valides, alertes autorisées, version et run courants). Un échec donne le verdict `echec_tests` : **rien n'est fusionné**, la fenêtre ne bouge pas, le prochain `--auto` repart du dernier succès. `offres_scores` est incrémental (fusion sur `id_unique` + `version_scoring`).

### 3.6 Top du jour, décisions et brouillons
- Les décisions sont **explicites** (« intéressé », « pas intéressé ») et stockées par offre exacte ; le top (20 offres par liste) est calculé à l'affichage : candidates du mart sur la période, moins les décisions, moins les offres déjà `postule` / `enregistre` dans `job_offers`, une offre par entreprise.
- « Intéressé » crée une ligne `job_offers` au statut **`brouillon`** (visible uniquement déverrouillé) après un contrôle de doublon qui avertit sans jamais bloquer. La description et la présentation de l'entreprise sont saisies à la main (« Modifier »), puis « Valider » passe le statut à `enregistre`. « Postuler » reste grisé tant qu'un brouillon n'est pas validé.

### 3.7 Type d'entreprise
Information affichée, sans effet sur le scoring : `esn`, `conseil`, `esn_conseil`, `cabinet_recrutement`, `client_final` ; `non_identifie` par défaut. Automatique : intermédiaire connu ou NAF 78.10Z → cabinet de recrutement, NAF 62.02A → ESN ; le NAF 70.22Z n'est pas utilisé seul (il mélange ESN, conseil et cabinets). **La correction manuelle prime** (table PostgreSQL), applicable depuis une carte du top ou une ligne du tableau Entreprises.

### 3.8 Normalisation des noms en trois copies
Les titres et noms d'entreprise sont normalisés (minuscules, sans accents ni ponctuation, mentions de genre supprimées) pour dédoublonner et rapprocher. La règle existe en trois copies à garder synchronisées : la macro dbt `normaliser`, la fonction du worker (`transformation/entreprises.py`) et celle du backend (`app/core/normalisation.py`).

---

## 4. Architecture technique

### 4.1 Flux global

```
PC local (Windows, GPU)                                           OVH / Scaleway              GCP (BigQuery)
────────────────────────────────                                  ──────────────────          ──────────────────────────
scripts\run_quotidien.bat  →  pipeline/orchestrator.py (Docker)
   1. entreprises exclues (GCS) ─────────────────────────────────────────────────────────────► top_offres.entreprises_exclues
   2. dbt amont : fenêtre, normalisation, doublons, filtres durs ◄── emploi_marche.stg_offres
                                                         ──────────────────────────────────► top_offres.int_offres_a_scorer
   3. entreprises (API publique, cache) ─────────────────────────────────────────────────────► top_offres.entreprises_ref
      embeddings  ─────────────────► orchestrateur :8080 ─► embedding-service :8004
      scoring LLM ─► Ollama (localhost:11434) ──► staging ──────────────────────────────────► top_offres.offres_scores_staging
   4. porte de contrôle (tests dbt) ─ échec : arrêt sans fusion
   5. fusion et marts dbt ───────────────────────────────────────────────────────────────────► offres_scores · mart_top_du_jour · mart_stats
   6. journal du run ────────────────────────────────────────────────────────────────────────► top_offres.runs

Backend Scaleway (routers/top_offres/) ◄── lecture des marts (compte de service dédié)
   + PostgreSQL : job_offers (brouillons), top_offres_decisions, top_offres_types_entreprise
Frontend Next.js : /realisations/top-offres  (+ intégration à /jobs)
```

### 4.2 Tables BigQuery (dataset `top_offres`)

| Table | Alimentée par | Rôle |
|---|---|---|
| `cibles` | worker | cibles de postes versionnées (`proposee` / `validee` / `archivee`) |
| `entreprises_exclues` | worker | copie de la liste d'exclusion |
| `entreprises_ref` | worker | cache des entreprises : NAF, catégorie, type d'annonceur, secteur, confiance |
| `offres_scores_staging` | worker | scores du run, avant la porte de contrôle |
| `runs` | worker | journal : fenêtre, versions, volumes, verdict, durée |
| `int_offres_a_scorer` | dbt | offres de la fenêtre, doublons, filtres durs, `a_scorer` |
| `offres_scores` | dbt | historique des scores (incrémental) |
| `mart_top_du_jour` | dbt | offres scorées + entreprise + liste (`a_lire` / `zone_grise` / `masque`) |
| `mart_stats` | dbt | comptages par jour et par dimension (format long) |

### 4.3 Tables PostgreSQL (backend)

| Table | Contenu |
|---|---|
| `job_offers` | statut `brouillon` ajouté (migration 019) ; le brouillon vit ici pour rester accessible depuis `/jobs` |
| `top_offres_decisions` | clé `id_unique` ; `pas_interesse` ou `interesse` ; lien vers `job_offers` ; les états brouillon et enregistrée se lisent via `job_offers.status` (migration 020) |
| `top_offres_types_entreprise` | corrections de type d'entreprise, par nom normalisé (migration 021) |

### 4.4 Endpoints backend

| Méthode | Route | Accès | Rôle |
|---|---|---|---|
| GET | `/top-offres/stats` | public | `mart_stats` + intitulés des cibles |
| GET | `/top-offres/top` | privé | les deux listes (onglets) et leurs compteurs |
| GET | `/top-offres/entreprises` | privé | agrégat par entreprise, filtres, tri par colonne |
| GET | `/top-offres/entreprises/offres` | privé | offres d'une entreprise (à la demande) |
| POST | `/top-offres/decisions` | privé | « intéressé » (brouillon, doublon en deux temps) ou « pas intéressé » |
| DELETE | `/top-offres/decisions` | privé | annule un « pas intéressé » |
| GET / PUT / DELETE | `/top-offres/types-entreprise…` | privé | corrections de type d'entreprise |

L'`id_unique` d'une alerte e-mail est un lien de suivi (`?`, `&`, `/`) : il circule en corps JSON ou en paramètre de requête encodé, jamais dans le chemin.

### 4.5 Frontend

Page `/realisations/top-offres`, quatre vues : **Vue d'ensemble** (publique : tuiles, colonnes empilées par jour, catégories, cibles, type d'annonceur, secteurs, bascule en tableau), **Top du jour**, **Entreprises**, **Brouillons** (privées). Côté `/jobs` : badge et filtre `brouillon`, bouton « Valider », « Postuler » grisé, détail mis à jour après « Modifier ».

### 4.6 Worker local

Image Docker unique (pipeline, agents, dbt, scripts) : le code est copié dans l'image, `docker-compose build pipeline` après toute modification. Modes de l'orchestrateur : `cibles-proposer`, `cibles-valider`, `run` (fenêtre `--auto`, `--depuis`, `--entre`, `--derniers-jours`, `--forcer`), `marts`. Scripts : `run_quotidien.bat`, `test_rappel.py`, `benchmark.py`, `balayage_lots.bat`, `inspect_run.py`. Détail d'exploitation : `GUIDE_LANCEMENT_ET_MISE_A_JOUR.md`.

---

## 5. Infrastructure

| Couche | Ressource |
|---|---|
| Local | PC Windows, Docker Desktop, Ollama (`gemma4:e4b`, `mistral:latest`, `gemma3:12b`), GPU de 8 Go |
| GCP | dataset `top_offres`, comptes de service `pipeline-top-offres` (lecture `emploi_marche`, écriture `top_offres`, lecture du bucket de configuration, jobs BigQuery) et `terraform-top-offres`, bucket `portfolio-emploi-config` |
| OVH | `embedding-service` (port 8004, partagé) derrière l'orchestrateur wake-on-demand (port 8080) |
| Scaleway | utilisateur PostgreSQL `top-offres-reader` (lecture seule), variable Terraform `gcp_service_account_json_top_offres` → `GCP_SERVICE_ACCOUNT_JSON_TOP_OFFRES` dans le backend, routes `routers/top_offres/`, page frontend |

---

## 6. Résultats clés

| Mesure | Résultat |
|---|---|
| Fenêtre de test de 30 jours | 12 856 offres, 5 578 à scorer, 580 stages et 148 alternances marqués, 264 entreprises exclues |
| Cibles validées | 8 |
| Run réel en lots de 1 (170 offres) | 170 `ok`, 0 erreur, 531 s (environ 1,75 s par offre), 20 tests dbt passés |
| Rappel sur les positifs (lots de 1, seuil 60) | 91,4 % (`postule` 98,6 %, `enregistre` 75,0 %) ; à seuil 75 : 83,8 % |
| Charge de lecture (lots de 1) | 48,5 % de l'échantillon à ≥ 60, 34,5 % à ≥ 75 |
| Listes au dernier run | `a_lire` 55 (scores 75 à 90), `zone_grise` 39 (60 à 70) |

---

## 7. Limites assumées

- **Le LLM reste imparfait** : le rappel est bruité (environ 3 points) ; la catégorie `adjacent` est parfois incohérente avec la raison (« cible cœur ») ; le secteur de l'entreprise peut influencer un score sans règle explicite du prompt.
- **Secteur web variable** d'un run à l'autre (moteurs de recherche qui limitent le débit) ; certaines étiquettes d'e-mail sont prises pour des entreprises (le parseur Gmail est hors périmètre).
- **Statistiques** (`mart_stats`) : les jours antérieurs au premier run n'existent pas ; les offres filtrées et les doublons des anciens jours manquent (le mart couvre tout l'historique scoré, la fenêtre courante en plus).
- **Doublons inter-fenêtres** : une offre republiée dans une autre fenêtre reçoit encore un score propre ; le mart n'en affiche qu'une.
- **Liens des alertes e-mail** : liens de suivi, durée de vie non garantie.
- **Normalisation en trois copies** à garder synchronisées (voir 3.8).

---

## 8. Backlog

- **E10 (clôture)** : objectif de rappel (D6, cible indicative 90 %), garde-fou si le modèle tourne sur CPU (`/api/ps`), révision du prompt de scoring puis nouveau benchmark en lots de 1.
- **Planificateur de tâches Windows** pour le run quotidien.
- **Recouvrement des 30 jours** en tranches (`--entre`, `--forcer`, environ 2 h 40) avec le modèle et la taille de lot définitifs.
- Groupes d'offres par mot-clé, bonus de mots-clés (`variantes_titres`), signal de récurrence (offre alertée plusieurs fois).
- Taille et effectif des entreprises dans le mart (déjà dans `entreprises_ref`).

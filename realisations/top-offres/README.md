# Top Offres

Veille emploi personnelle : chaque jour, les offres collectées sont classées selon leur pertinence pour un profil, par un LLM tournant en local sur GPU. En production depuis le 2026-10-18, utilisé au quotidien.

Page : `/realisations/top-offres` (vue d'ensemble publique ; Top du jour, Entreprises et Brouillons derrière le code d'accès 🔒).

## Ce que ça fait

| Étape | Résumé |
|---|---|
| Cibles de postes | 8 cibles dérivées de la table `experiences` par un LLM local (`gemma3:12b`), relues et validées à la main, versionnées |
| Sélection (dbt) | Fenêtre réglable, dédoublonnage, filtres durs marqués (stage, alternance, hors Île-de-France) |
| Entreprises | API Recherche d'entreprises (NAF, catégorie), secteur par NAF ou recherche web + LLM, cache de 90 jours |
| Scoring | `gemma4:e4b` sur Ollama, **une offre par appel** : score 0-100, catégorie, raison, alertes |
| Porte de contrôle (dbt) | Tests sur le staging avant fusion : un échec ne fusionne rien |
| Restitution | Marts `mart_top_du_jour` et `mart_stats` → backend `/top-offres` → frontend |

Les offres viennent de la collecte existante (France Travail + alertes Gmail → `emploi_marche`) : Top Offres lit `stg_offres` en lecture seule et ne collecte rien.

## Architecture

```
PC local (Windows, Docker, Ollama sur GPU)
   scripts\run_quotidien.bat → pipeline/orchestrator.py
      1 entreprises exclues (GCS) ─────────────────────────► BigQuery top_offres
      2 dbt amont (fenêtre, doublons, filtres) ◄── emploi_marche.stg_offres
      3 entreprises · embeddings (OVH 8004 via orchestrateur) · scoring LLM (Ollama) → staging
      4 porte de contrôle dbt ── échec : arrêt sans fusion
      5 fusion + marts dbt ────────────────────────────────► offres_scores · mart_top_du_jour · mart_stats
      6 journal ───────────────────────────────────────────► runs

Backend FastAPI (Scaleway) ◄── lecture des marts (compte de service dédié)
   + PostgreSQL : job_offers (brouillons), décisions, types d'entreprise corrigés
Frontend Next.js : /realisations/top-offres (+ statut « brouillon » dans /jobs)
```

## Choix techniques

- **Lots de 1** : écart nul entre copies identiques d'une même offre, contre 11,5 à 16 points en lots de 5 à 20.
- **Information manquante jamais pénalisante** : entreprise inconnue, intermédiaire ou lieu illisible = neutre.
- **Embeddings** (`paraphrase-multilingual-mpnet-base-v2`, service OVH partagé) : contexte du LLM et départage, jamais un filtre.
- **Seuils** : `a_lire` ≥ 75, `zone_grise` 60 à 74 (réglables dans le `.env`).
- **Évaluation** : rappel de 91,4 % à un seuil de 60 sur les offres déjà postulées ou enregistrées ; benchmark de 5 modèles ; run réel de 170 offres en 531 s.
- **Accès** : le worker ne fait que lire PostgreSQL (utilisateur lecture seule) ; seul le backend écrit.

## Lancer

Depuis `realisations/top-offres/pipeline` (là où se trouve `docker-compose.yml`).

**Prérequis**
- Docker Desktop et Ollama lancés ; modèles installés : `gemma4:e4b` (scoring), `mistral:latest` (secteur), `gemma3:12b` (cibles, seulement pour `cibles-proposer`).
- Le modèle de scoring doit tourner sur GPU : `ollama ps` doit afficher `100% GPU`.
- `.env` à la racine du MVP et clé `gcp_sa_top_offres.json` (jamais commités). Variables obligatoires : `GOOGLE_APPLICATION_CREDENTIALS`, `PG_HOST`, `PG_PORT`, `PG_DB`, `PG_USER`, `PG_PASSWORD`, `MODELE_SCORING=gemma4:e4b`. Réglages actuels : `TAILLE_LOT_LLM=1`, `SEUIL_HAUT=75`, `SEUIL_BAS=60`, `NB_LOTS_ERREUR_MAX=3`. Liste complète et défauts : `pipeline/config.py`.
- Au moins une version de cibles au statut `validee`.
- Le code est copié dans l'image : `docker-compose build pipeline` après toute modification de `pipeline/`, `agents/`, `dbt/` ou `scripts/`.

**Run quotidien** (après la collecte de 12h, donc à partir de 14h)

```
scripts\run_quotidien.bat --pause
```

ou directement :

```
docker-compose run --rm pipeline pipeline/orchestrator.py run --auto
```

Options de fenêtre : `--depuis AAAA-MM-JJ`, `--entre D1 D2`, `--derniers-jours N`, `--forcer` (re-score aussi les offres déjà scorées).

**Autres commandes**

```
docker-compose run --rm pipeline pipeline/orchestrator.py marts
docker-compose run --rm pipeline pipeline/orchestrator.py cibles-proposer
docker-compose run --rm pipeline pipeline/orchestrator.py cibles-valider --fichier results/cibles_<version>.json
docker-compose run --rm pipeline scripts/test_rappel.py
docker-compose run --rm pipeline scripts/benchmark.py --taille-lot 1
```

Verdicts d'un run : `succes`, `echec_tests` (rien n'est fusionné), `erreur`. Un run en échec ne déplace pas la fenêtre : le prochain `--auto` repart du dernier succès.

## Structure

```
top-offres/
├── pipeline/   collectors/ · transformation/ · validators/ · loaders/ · orchestrator.py · config.py (+ Dockerfile, docker-compose.yml)
├── agents/     cibles_agent.py · scoring_agent.py · secteur_agent.py · llm_client.py · prompts/
├── dbt/        int_offres_a_scorer · offres_scores · mart_top_du_jour · mart_stats · tests (porte de contrôle)
├── scripts/    run_quotidien.bat · test_rappel.py · benchmark.py · balayage_lots.bat · inspect_run.py
└── results/    rapports, logs de runs (non versionnés)
```

Côté plateforme : `backend/routers/top_offres/`, `backend/app/services/top_offres_bigquery.py`, `frontend/components/top-offres/`, migrations SQL 019 à 021.

## Limites et backlog

- Le LLM reste imparfait : rappel bruité (environ 3 points), catégorie `adjacent` parfois incohérente avec la raison.
- Métadonnées seulement (pas de description d'offre, scraping abandonné pour raisons de CGU) ; les liens des alertes e-mail sont des liens de suivi à durée de vie non garantie.
- Backlog : clôture de l'évaluation (objectif de rappel, garde-fou GPU `/api/ps`, revue du prompt), Planificateur de tâches Windows, groupes par mot-clé.

## Pour aller plus loin

- `GUIDE_LANCEMENT_ET_MISE_A_JOUR.md` : exploitation, dépannage, mise à jour de la plateforme.
- `RECAP_TECHNIQUE_ET_ARCHITECTURE.md` : choix méthodologiques, tables, endpoints, résultats.

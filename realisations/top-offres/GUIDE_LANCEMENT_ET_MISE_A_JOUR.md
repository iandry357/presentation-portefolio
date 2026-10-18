# Top Offres — lancement et mise à jour

Worker local (Windows + Docker + Ollama) qui classe chaque jour les offres collectées. Toutes les commandes se lancent
depuis `realisations/top-offres/pipeline` (là où se trouve `docker-compose.yml`).

## 1. Prérequis

- Docker Desktop et Ollama lancés ; modèles installés : `gemma4:e4b` (scoring), `mistral:latest` (secteur des entreprises) et `gemma3:12b` (cibles de postes, seulement pour `cibles-proposer`).
- `.env` à la racine du MVP (jamais commité) et clé `gcp_sa_top_offres.json` (jamais commitée).
- Variables du `.env` à régler : `MODELE_SCORING=gemma4:e4b` (pas de valeur par défaut), `TAILLE_LOT_LLM=1`, `SEUIL_HAUT=75`, `SEUIL_BAS=60`, `NB_LOTS_ERREUR_MAX=3`. La liste complète des variables et de leurs défauts est dans `pipeline/config.py`.
- Au moins une version de cibles au statut `validee` (voir section 3).
- Après toute modification de `pipeline/`, `agents/`, `dbt/` ou `scripts/` : `docker-compose build pipeline` (le code est copié dans l'image).
- Le modèle de scoring doit tourner sur le GPU : `ollama ps` doit afficher `100% GPU` (après une mise à jour d'Ollama, redémarrer complètement le serveur).

## 2. Lancer un run

```
cd /d "C:\Users\iandr\Documents\EXP\exp 2.0\projet cv\presentation-portefolio\realisations\top-offres\pipeline"
docker-compose run --rm pipeline pipeline/orchestrator.py run --auto
```

| Option | Fenêtre sur `date_collecte` (UTC) |
|---|---|
| `--auto` (défaut) | De la fin du dernier run `succes` à maintenant ; sinon les `DERNIERS_JOURS_DEFAUT` derniers jours (30) |
| `--depuis 2026-10-10` | De cette date à maintenant |
| `--entre 2026-10-01 2026-10-08` | Entre les deux dates |
| `--derniers-jours 7` | Les 7 derniers jours |
| `--forcer` | Re-score aussi les offres déjà scorées avec la version courante (sans doublon : le merge met à jour) |

Étapes du run : 1 entreprises exclues · 2 dbt amont · 3 scoring (entreprises, embeddings, LLM, staging) · 4 porte de
contrôle (tests dbt) · 5 fusion et marts · 6 journal dans `top_offres.runs`.

**Lancement quotidien (recommandé)** : `scripts\run_quotidien.bat --pause`, depuis n'importe quel dossier (le script se place lui-même dans `pipeline`). Il vérifie que Docker et Ollama répondent, lance `run --auto` (ou les options passées au script, par exemple `scripts\run_quotidien.bat --derniers-jours 3`), affiche la sortie et l'enregistre dans `results\logs\run_<AAAAMMJJ-hhmmss>.log`. `--pause` garde la fenêtre ouverte à la fin. Codes de retour : 0 succès, 2 Docker indisponible, 3 Ollama indisponible, sinon le code du run. La collecte tourne à 7h et 12h (Europe/Paris) : lancer après celle de 12h (à partir de 14h) ou le soir.

Reconstruire seulement les marts (après un changement de seuils, par exemple) :

```
docker-compose run --rm pipeline pipeline/orchestrator.py marts
```

Les seuils se règlent dans le `.env` (`SEUIL_HAUT=75`, `SEUIL_BAS=60` actuellement). Pour un essai ponctuel : `docker-compose run --rm -e SEUIL_HAUT=80 pipeline pipeline/orchestrator.py marts`.

## 3. Cibles de postes

```
docker-compose run --rm pipeline pipeline/orchestrator.py cibles-proposer
docker-compose run --rm pipeline pipeline/orchestrator.py cibles-valider --fichier results/cibles_<version>.json
```

`cibles-proposer` écrit une version `proposee` et un export dans `results/` ; relire et corriger le fichier, puis
`cibles-valider` (une seule version validée active ; la précédente passe `archivee`). Une nouvelle version de cibles change la `version_scoring` : tout est re-scoré.

## 4. Verdicts et reprise

| Verdict (`runs.verdict`) | Signification | Code de sortie |
|---|---|---|
| `succes` | Porte passée, fusion et marts à jour | 0 |
| `echec_tests` | La porte de contrôle a échoué : **rien n'a été fusionné** | 1 |
| `erreur` | dbt, API ou exception | 1 |

Un run en échec ne déplace pas la fenêtre : le prochain `--auto` repart de la fin du dernier `succes`, sans doublon.
Arrêt avant journal (sans ligne dans `runs`) : `MODELE_SCORING` absent, aucune cible validée, fenêtre invalide.

Derniers runs :

```sql
SELECT run_id, verdict, fenetre_debut, fenetre_fin, nb_lues, nb_filtrees, nb_a_scorer, nb_scorees_ok, nb_erreurs, duree_s, message
FROM `top_offres.runs` ORDER BY debut DESC LIMIT 10
```

## 5. Planificateur de tâches Windows (reporté)

Le run quotidien est lancé à la main avec `scripts\run_quotidien.bat --pause` (section 2). L'automatisation est au backlog ; le moment venu :

1. Planificateur de tâches > Créer une tâche : déclencheur quotidien après la collecte de 12h (14h ou le soir), action « Démarrer un programme » = `scripts\run_quotidien.bat` (sans `--pause`).
2. Docker Desktop et Ollama lancés, PC éveillé et utilisateur connecté au déclenchement (réglages à tester).
3. Contrôler le lendemain : le dernier fichier de `results\logs` et la requête de la section 4.

Durée indicative : environ 9 minutes pour 170 offres en lots de 1 (531 s mesurées), plus long au premier passage (cache des entreprises vide, recherches web de secteur limitées à `MAX_RECHERCHES_WEB_PAR_RUN` par exécution).

## 6. Dépannage

| Symptôme | Piste |
|---|---|
| `MODELE_SCORING non défini` | Ajouter la variable au `.env` |
| `Ollama HTTP 404 ... model not found` | Le modèle n'est pas installé : `ollama list`, puis `ollama pull <modèle>` |
| `echec_tests` | La sortie du run contient les lignes `dbt \| FAIL …` du test en cause ; rejouer les tests à la main avec `dbt test --select source:top_offres porte_...` |
| Secteurs web vides ou `NON DETERMINE` en masse | Moteurs de recherche limitant le débit : relancer plus tard, ou augmenter `PAUSE_RECHERCHE_WEB_SECONDS` |
| Modification dbt sans effet | Reconstruire l'image (`docker-compose build pipeline`) |
| Entreprise parasite (étiquette d'e-mail prise pour une entreprise) | L'ajouter à `excluded_companies.json` (bucket `portfolio-emploi-config`) |
| Scoring très lent (environ 100 s par offre) | Le modèle tourne sur CPU : `ollama ps` doit afficher `100% GPU` ; redémarrer complètement Ollama (surtout après une mise à jour) |
| Run arrêté après quelques offres | `NB_LOTS_ERREUR_MAX` offres consécutives en erreur d'appel (Ollama injoignable, délai dépassé) : relancer, `--auto` repart de la fin du dernier succès |
| Un lien « Voir l'offre » d'une alerte e-mail ne s'ouvre plus | Ces liens sont des liens de suivi, de durée de vie non garantie ; la date de collecte affichée aide à repérer les anciens |

## 7. Utiliser la plateforme (`/realisations/top-offres`)

| Vue | Accès | À quoi elle sert |
|---|---|---|
| Vue d'ensemble | publique | Tuiles du dernier jour collecté et graphiques sur la période (7, 14 ou 30 jours), bascule « Voir en tableau » |
| Top du jour | privée | Deux onglets (à lire, zone grise), période et option « Inclure les entreprises exclues » ; une offre par entreprise |
| Entreprises | privée | Tableau trié en cliquant sur une colonne ; filtres période, type, secteur, nom ; clic sur une ligne : offres de l'entreprise avec lien |
| Brouillons | privée | Offres marquées « Intéressé » à compléter |

Parcours d'une offre : **Top du jour** > « Intéressé » (un doublon dans `/jobs` est signalé, sans jamais bloquer) > **Brouillons** > « Compléter et valider » (ouvre `/jobs/{id}`) > « Modifier » : coller la description et la présentation de l'entreprise > « Valider ». « Postuler » reste grisé tant que le brouillon n'est pas validé. « Pas intéressé » écarte l'offre (lien « Annuler » pendant quelques secondes). Le type d'entreprise se corrige depuis une carte ou une ligne du tableau Entreprises ; la correction prime sur le type automatique.

## 8. Évaluer et comparer

```
docker-compose run --rm pipeline scripts/test_rappel.py
docker-compose run --rm pipeline scripts/benchmark.py --taille-lot 1
```

`test_rappel.py` score les offres déjà `postule` ou `enregistre` de `job_offers` et mesure le rappel par seuil. `benchmark.py` compare des modèles ou des tailles de lot sur un même jeu. Les rapports JSON sont écrits dans `results/`. `scripts\balayage_lots.bat` compare les tailles de lot 20, 10, 5 et 1 en un lancement. Ne pas lancer de `run` entre deux étapes d'un benchmark `--sans-amont` (le run reconstruit `int_offres_a_scorer`).

## 9. Mettre à jour la plateforme (backend, frontend, base)

- **Migrations SQL** : appliquées à la main (`backend/migrations/sql/`), sur la base Scaleway avant de fusionner le code qui en dépend. Celles de Top Offres : 019 (statut `brouillon`), 020 (décisions), 021 (types d'entreprise corrigés).
- **Compte de service du backend** : variable Terraform `gcp_service_account_json_top_offres` (JSON compact de la clé de `pipeline-top-offres`), dans `terraform.tfvars` local et dans le secret GitHub `TF_VARS_FILE` ; `terraform apply` en local avant la fusion.
- **Fusion et déploiement** : fusionner sur `infra-scaleway-v1.1`, attendre « Deploy Backend » vert avant de tester la production.
- **Cibles** : une nouvelle version validée change la `version_scoring` (tout est re-scoré). Un changement de modèle ou de prompt aussi ; la taille de lot n'en fait pas partie (utiliser `--forcer`).

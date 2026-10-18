# Top Offres — lancement et mise à jour

Worker local (Windows + Docker + Ollama) qui classe chaque jour les offres collectées. Toutes les commandes se lancent
depuis `realisations/top-offres/pipeline` (là où se trouve `docker-compose.yml`).

## 1. Prérequis

- Docker Desktop et Ollama lancés ; modèles `mistral:latest` (secteur des entreprises) et celui du scoring installés.
- `.env` à la racine du MVP (jamais commité) et clé `gcp_sa_top_offres.json` (jamais commitée).
- Variable `MODELE_SCORING` définie dans le `.env` (pas de valeur par défaut : le modèle sera fixé après le benchmark, E10).
- Au moins une version de cibles au statut `validee` (voir section 3).
- Après toute modification de `pipeline/`, `agents/`, `dbt/` ou `scripts/` : `docker-compose build pipeline` (le code est copié dans l'image).

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

Reconstruire seulement les marts (après un changement de seuils, par exemple) :

```
docker-compose run --rm pipeline pipeline/orchestrator.py marts
```

Les seuils (`SEUIL_HAUT`, `SEUIL_BAS`) se changent par variable d'environnement : `docker-compose run --rm -e SEUIL_HAUT=75 pipeline pipeline/orchestrator.py marts`.

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

## 5. Planificateur de tâches Windows (run quotidien)

1. Créer un fichier `lancer_run_quotidien.bat` hors du dépôt (par exemple dans votre dossier utilisateur) :

```bat
@echo off
cd /d "C:\Users\iandr\Documents\EXP\exp 2.0\projet cv\presentation-portefolio\realisations\top-offres\pipeline"
docker-compose run --rm -T pipeline pipeline/orchestrator.py run --auto >> ..\results\run_quotidien.log 2>&1
```

`-T` est indispensable : sans terminal, `docker-compose run` échoue par défaut.

2. Planificateur de tâches > Créer une tâche : déclencheur quotidien (heure de votre choix), action « Démarrer un programme » = ce `.bat`.
3. Docker Desktop et Ollama doivent être lancés au moment du déclenchement. Choisir « Exécuter uniquement si l'utilisateur est connecté » (à tester selon votre configuration).
4. Contrôler le lendemain : `results/run_quotidien.log` et la requête de la section 4.

Durée indicative : quelques minutes par jour une fois le cache des entreprises rempli (le premier run sur plusieurs jours est long : recherches web de secteur limitées à `MAX_RECHERCHES_WEB_PAR_RUN` par exécution).

## 6. Dépannage

| Symptôme | Piste |
|---|---|
| `MODELE_SCORING non défini` | Ajouter la variable au `.env` |
| `Ollama HTTP 404 ... model not found` | Le modèle n'est pas installé : `ollama list`, puis `ollama pull <modèle>` |
| `echec_tests` | La sortie du run contient les lignes `dbt \| FAIL …` du test en cause ; rejouer les tests à la main avec `dbt test --select source:top_offres porte_...` |
| Secteurs web vides ou `NON DETERMINE` en masse | Moteurs de recherche limitant le débit : relancer plus tard, ou augmenter `PAUSE_RECHERCHE_WEB_SECONDS` |
| Modification dbt sans effet | Reconstruire l'image (`docker-compose build pipeline`) |
| Entreprise parasite (étiquette d'e-mail prise pour une entreprise) | L'ajouter à `excluded_companies.json` (bucket `portfolio-emploi-config`) |

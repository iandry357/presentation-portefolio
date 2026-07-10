# gcp/dbt_transformation — Observatoire Emploi, couche transformation

Transforme `emploi_marche.offres_brutes` en tables agrégées consommées par
`/market` (Q01–Q10), via dbt-core + dbt-bigquery. Réduit le volume scanné
par le backend à chaque appel, au lieu de rescanner `offres_brutes` en direct.

---

## Architecture en un coup d'œil

```
sync-ft-bigquery (FT + Gmail)
        │
        │ déclenche automatiquement, fire-and-forget,
        │ une fois la sync terminée avec succès
        ▼
dbt-emploi-marche (Cloud Run Job)
        │
        ├── dbt run   → matérialise staging (view) + intermediate (table)
        └── dbt test  → tests qualité, échec = Job marqué "Failed"
        ▼
emploi_marche.stg_offres            (view, dédupliquée sur id_unique)
emploi_marche.int_offres_agg_jour   (table, grain jour×source×dimensions)
emploi_marche.int_offres_agg_entreprise
emploi_marche.int_offres_agg_localisation
        ▼
backend/market_queries.py — Q01-Q10 lisent ces tables (SUM au lieu de COUNT)
                             Q11 reste sur offres_brutes, inchangée
```

**Modèles staging** : miroir renommé/typé de `offres_brutes`, aucun filtre
métier — seule transformation : déduplication sur `id_unique` (la ligne
avec `date_collecte` la plus récente est conservée).

**Modèles intermediate** : agrégations + filtres qualité (`entreprise_nom`
et `localisation_libelle` non vides). Séparés par dimension à cardinalité
élevée (entreprise, localisation) pour éviter une table quasi aussi grosse
que `stg_offres`.

**Q11 est volontairement hors dbt** — logique dynamique (score, exclusion
entreprises en temps réel) non pré-calculable sans perdre l'instantanéité
de l'exclusion.

---

## Prérequis pour travailler en local

```
cd gcp/dbt_transformation
python -m venv venv-dbt
venv-dbt\Scripts\activate
pip install -r requirements.txt
gcloud auth application-default login
```

L'authentification utilise l'impersonation ADC du SA `pipeline-dbt`
(target `dev` de `profiles.yml`) — pas de clé JSON à gérer. Le SA et ses
rôles IAM sont définis dans `infra/` (Terraform).

---

## Commandes courantes

```
# Vérifier la connexion BigQuery (target dev par défaut)
dbt debug

# Construire tous les modèles
dbt run

# Construire un modèle précis
dbt run --select stg_offres
dbt run --select int_offres_agg_jour int_offres_agg_entreprise int_offres_agg_localisation

# Lancer les tests qualité (unique, not_null, accepted_values)
dbt test

# Vérifier la fraîcheur de la source offres_brutes
dbt source freshness

# Nettoyer les artefacts locaux (target/, dbt_packages/)
dbt clean
```

---

## Exécution automatique en production

Aucune action manuelle nécessaire en usage normal — la chaîne se déclenche
seule à chaque exécution de `sync-ft-bigquery` (Cloud Scheduler, 7h/12h/
1er-15 du mois). Le déclenchement est fait depuis `gcp/sync_job/main.py`
(fonction `_trigger_dbt_job`), en fire-and-forget, uniquement après succès
de la sync FT + Gmail.

**Pour vérifier qu'une exécution récente s'est bien déroulée :**

```
gcloud run jobs executions list --job=dbt-emploi-marche --region=europe-west9

gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=dbt-emploi-marche" \
  --limit=100 --format="table(timestamp,severity,textPayload)" --order=asc
```

Chercher la ligne finale `=== [dbt] Transformation terminée avec succès ===`
— si elle est absente, `dbt run` ou `dbt test` a échoué (le Job apparaît
alors en "Failed" dans son historique d'exécution).

---

## Redéployer après une modification

**Si un modèle `.sql`/`.yml` change** (staging, intermediate, config dbt) :

```
cd gcp/dbt_transformation
docker build -t dbt-emploi-marche .
docker tag dbt-emploi-marche europe-west9-docker.pkg.dev/gen-lang-client-0989575872/sync-job-registry/dbt-emploi-marche:latest
docker push europe-west9-docker.pkg.dev/gen-lang-client-0989575872/sync-job-registry/dbt-emploi-marche:latest
gcloud run jobs update dbt-emploi-marche --image=europe-west9-docker.pkg.dev/gen-lang-client-0989575872/sync-job-registry/dbt-emploi-marche:latest --region=europe-west9
```

**Test manuel immédiat**, sans attendre le prochain cycle Cloud Scheduler :

```
gcloud run jobs execute dbt-emploi-marche --region=europe-west9
```

**Si `gcp/sync_job/main.py` change** (ex. logique de déclenchement dbt) :
rebuild/push/update de l'image `sync-job` — voir procédure identique dans
`gcp/sync_job/`, cible `sync-ft-bigquery` au lieu de `dbt-emploi-marche`.

**Si l'infra change** (rôles IAM, SA) :

```
cd gcp/dbt_transformation/infra
terraform plan
terraform apply
```

---

## Dépannage — problèmes déjà rencontrés

| Symptôme | Cause | Fix |
|---|---|---|
| `Error 400: User ... does not exist` sur `terraform apply` | `impersonator_member` du `.tfvars` pas renseigné avec une vraie adresse | Mettre l'email du compte `gcloud` réel, préfixe `user:` conservé |
| `dbt debug` → `Env var required but not provided: 'DBT_IMPERSONATE_SA'` | dbt ne lit jamais un `.env` automatiquement | Valeurs mises en dur dans `profiles.yml` (pas de secret réel ici) — plus de dépendance à `.env` pour la connexion |
| `dbt test` échoue sur `accepted_values` de `source` | Liste de valeurs incomplète dans le schéma de référence initial | 12 valeurs réelles listées dans `_staging__models.yml` et `_sources.yml` (6 emails supplémentaires : jobijoba, meteojob, indeed, wttj, freework, jobleads) |
| `DeprecationSummary: PropertyMovedToConfigDeprecation` | `loaded_at_field`/`freshness` doivent être sous une clé `config:` en dbt 1.11+ | Voir structure actuelle de `_sources.yml` |
| Cloud Run Job `dbt-emploi-marche` : "Application failed to start", aucun log applicatif | Fins de ligne CRLF dans `entrypoint.sh` (édition Windows) | `sed -i 's/\r$//' entrypoint.sh` ajouté dans le `Dockerfile` avant `chmod +x` |
| `sync-ft-bigquery` ne déclenche pas dbt | SA `pipeline_emploi` sans droit d'invoquer un Cloud Run Job | Déjà couvert — `roles/run.invoker` + `roles/run.developer` présents au niveau projet dans `serviceaccount.tf` |

---

## Limites connues / backlog

- **Q11** hors dbt — reste sur `offres_brutes` en lecture directe, décision assumée (voir plus haut)
- **`models/marts/`** vide — Q01-Q10 restent en `intermediate`, le `GROUP BY` fin (période/source) reste fait côté backend
- **Pas de partitionnement BigQuery** sur les tables `int_offres_agg_*` — à envisager si le volume de `offres_brutes` grossit significativement
- **`--log-format json`** dans `entrypoint.sh` : suppose que Cloud Logging structure automatiquement les lignes JSON de stdout en `jsonPayload` — comportement standard GCP, pas re-testé explicitement au-delà de la vérification "ça tourne"

---

## Arborescence

```
gcp/dbt_transformation/
├── dbt_project.yml
├── profiles.yml              # targets dev (ADC+impersonation) / prod (SA natif Cloud Run)
├── packages.yml
├── requirements.txt
├── Dockerfile
├── entrypoint.sh              # dbt run puis dbt test, échec explicite loggé
├── .dockerignore
├── models/
│   ├── staging/
│   │   ├── _sources.yml
│   │   ├── _staging__models.yml
│   │   └── stg_offres.sql
│   ├── intermediate/
│   │   ├── _intermediate__models.yml
│   │   ├── int_offres_agg_jour.sql
│   │   ├── int_offres_agg_entreprise.sql
│   │   └── int_offres_agg_localisation.sql
│   └── marts/                 # vide pour l'instant
├── tests/                     # vide pour l'instant
└── infra/
    ├── main.tf                 # SA pipeline-dbt + IAM
    ├── variables.tf
    ├── outputs.tf
    └── terraform.tfvars.example
```
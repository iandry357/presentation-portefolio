# Immobilier (Paris 75)

Veille immobilière à partir de données ouvertes, pour un cas d'usage précis : repérer qu'un bien s'est amélioré (DPE refait) et situer son prix. Support d'échange avec un agent immobilier indépendant. Pas de ML, pas de service OVH.

Page : `/realisations/immobilier`, deux onglets.
- **V1 (DPE + DVF)**, en production depuis le 2026-10-20 : 3 vues, carte des arrondissements, repères pédagogiques.
- **Bâtiments (BDNB)**, en production depuis le 2026-10-22 : 3 vues (Prix et DPE, Profil du parc, Sources et qualité).

## Sources

| Source | Contenu | Chargement |
|---|---|---|
| DPE ADEME (`dpe03existant`) | Diagnostics de Paris, via API | Pipeline Docker. Production : échantillon de 97 937 DPE ; complet = 854 971 (à charger) |
| DVF (Etalab, `geo-dvf`) | Ventes 2021-2025 | Pipeline Docker. 150 407 ventes de logement, 145 128 validées |
| BDNB (CSTB, millésime 2026-02.b) | Bâtiments, DPE, adresses, ventes rattachées | Pipeline local (Parquet + Polars), 6 tables `bdnb_*` (1,12 Go) |

Les deux jeux (V1 et BDNB) restent séparés : aucune fusion des tables, une source de référence par information, avec sa date.

## Architecture

```
Sources ouvertes ──► pipeline local ──► BigQuery (dataset `immobilier`) ──► Backend FastAPI ──► Frontend Next.js
 ADEME / Etalab       collecte, transfo,    tables brutes + agrégats          /immobilier/*        /realisations/immobilier
 BDNB (CSV → Parquet) validation, chargement agg_dpe_*, agg_dvf_*,            /immobilier/bdnb/*
                                            bdnb_*, agg_bdnb_*
```

- **V1** : collecteurs → transformations → validateurs → chargement CSV BigQuery → agrégats `agg_dpe_parc`, `agg_dvf_prix`, `agg_dvf_paris`.
- **BDNB** : CSV converties en Parquet, sélection DPE (arrêté 2021, logement, méthode 3cl, surface > 0 : 824 036 DPE sur 1 101 962), chargement avec contrôle des comptages, puis agrégats `agg_bdnb_*` et métadonnées `bdnb_sources`, `bdnb_entonnoir`.
- **Backend** : lecture des agrégats BigQuery avec un compte de service dédié (`GCP_SERVICE_ACCOUNT_JSON_IMMOBILIER`), en cache.
- **Accès** : public pour les agrégats ; les cellules de prix de moins de 5 ventes sont masquées si l'accès est verrouillé ; la liste des DPE refaits (`/changements`) est réservée au code d'accès.

## Endpoints

| Route | Accès | Rôle |
|---|---|---|
| `/immobilier/stats`, `/dpe`, `/prix` | public | En-tête, parc DPE, prix DVF |
| `/immobilier/changements` | privé | DPE refaits (recalcul 2026 probable ou simplement refait) |
| `/immobilier/bdnb/stats`, `/prix-dpe`, `/parc`, `/sources` | public | Onglet Bâtiments (BDNB) |

## Choix techniques

- Drapeaux dérivés : chauffage électrique et DPE post-réforme (2026-01-01) ; la combinaison signale un recalcul 2026 probable.
- DVF : prix au m² borné à 2 000-30 000 € (5 273 ventes hors bornes écartées).
- BDNB : une vente représentative par bâtiment ; géocodage des DPE très fiable à 88,9 % ; classes fragiles (peu de ventes) grisées dans l'interface.
- Textes « À retenir » calculés à partir des données (`frontend/lib/immobilierBdnbTextes.ts`), pas écrits à la main.
- Constat honnête : les prix varient peu avec la classe DPE (F+G contre D : −2,7 %, brut).

## Lancer

### Prérequis
- Docker Desktop (V1) ; Python avec le venv `scripts/venv-explore` (BDNB).
- Compte de service GCP : fichier `realisations/immobilier/gcp_sa_immobilier.json` (jamais commité).
- `realisations/immobilier/pipeline/.env` (jamais commité) avec `GCP_PROJECT_ID`, `GCP_SA_KEY_PATH` (chemin relatif à `realisations/immobilier`) et `BQ_DATASET`.
- Terraform du dataset et des comptes de service : `gcp/immobilier/infra/`.

### V1 : DVF et DPE (Docker)
Depuis `realisations/immobilier/pipeline`. Le code est copié dans l'image : `docker-compose build pipeline` après modification.

```
docker-compose run --rm pipeline python pipeline/orchestrator.py --source dvf
docker-compose run --rm pipeline python pipeline/orchestrator.py --source dpe --echantillon
docker-compose run --rm pipeline python pipeline/orchestrator.py --source dpe
docker-compose run --rm pipeline python pipeline/orchestrator.py --source agg
```

- `--echantillon` : 10 pages de 10 000 DPE (environ 3 min) ; sans l'option, parcours complet des 86 pages (environ 23 min, estimation).
- `--reprendre` : reprend une collecte complète interrompue.
- `--source all` : DPE et DVF ; `--source agg` : reconstruit seulement les agrégats.
- Le cache (`/app/data`) est un volume Docker persistant.

### BDNB (local, hors Docker)
Les données BDNB ne sont pas versionnées ni embarquées dans l'image. Prérequis : l'export CSV du département 75 dézippé dans `pipeline/data/bdnb/bdnb_dep75_csv/`.

```
cd /d "C:\Users\iandr\Documents\EXP\exp 2.0\projet cv\presentation-portefolio\realisations\immobilier"
scripts\venv-explore\Scripts\activate
pip install -r pipeline\bdnb\requirements-bdnb.txt
python scripts\convert_bdnb_parquet.py
python -m pipeline.bdnb.orchestrator --etape chargement --dry-run
python -m pipeline.bdnb.orchestrator --etape tout
```

- `--etape chargement | metadonnees | agregats | tout` ; `--tables t1 t2 ...` ; `--dry-run` (sélection et contrôle sans écriture BigQuery).
- Les comptages attendus par table sont dans `pipeline/bdnb/config.py` ; un écart arrête le chargement.
- À chaque nouveau millésime, mettre à jour `SOURCES` dans `pipeline/bdnb/config.py`.
- Exploration : `scripts\explore_bdnb.py` (rapports dans `pipeline/data/bdnb/rapports/`).

### Plateforme
Backend : `GCP_SERVICE_ACCOUNT_JSON_IMMOBILIER` dans `backend/.env`, puis `uvicorn app.main:app --reload`. Frontend : `npm run dev`. En production, déploiement par les workflows habituels.

## Structure

```
immobilier/
├── pipeline/  collectors/ · transformation/ · validators/ · loaders/ · orchestrator.py · config.py
│              bdnb/ (selection · loader · aggregations · metadonnees · orchestrator · config)
│              (+ Dockerfile, docker-compose.yml, requirements.txt)
└── scripts/   check_sources.py · inspect_dvf.py · diag_remplaces.py · convert_bdnb_parquet.py · explore_bdnb.py
gcp/immobilier/infra/                       Terraform dédié
backend/routers/immobilier/                 router.py · bdnb_router.py · schemas
backend/app/services/                       immobilier_bigquery.py · immobilier_bdnb_bigquery.py
frontend/components/immobilier/             V1 + bdnb/
```

## Limites et reste à faire

- Production : DPE en échantillon, pipeline complet (854 971) à lancer.
- CGU DGFiP (DVF) à relire.
- Écart de 1,0 % non expliqué entre la BDNB et l'API ADEME sur le nombre de DPE.
- Vue verrouillée et mobile de l'onglet BDNB sans test explicite.
- Phase 4 prévue : fiche bien (recherche par adresse, modèle de prix, recalcul 2026), cahier à part.

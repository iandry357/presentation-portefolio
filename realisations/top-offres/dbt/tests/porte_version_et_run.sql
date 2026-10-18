-- Porte de contrôle : renvoie les lignes du staging qui ne portent pas le run_id et la version_scoring
-- du run courant (le test échoue s'il y a des lignes). Variables obligatoires : run_id, version_scoring.

select
    id_unique,
    run_id,
    version_scoring
from {{ source('top_offres', 'offres_scores_staging') }}
where coalesce(run_id, '') != '{{ var("run_id") }}'
   or coalesce(version_scoring, '') != '{{ var("version_scoring") }}'

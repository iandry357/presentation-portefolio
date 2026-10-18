-- Porte de contrôle : le staging doit contenir exactement une ligne par offre à scorer
-- (le test échoue si les deux nombres diffèrent).

with staging as (

    select count(*) as nb_staging
    from {{ source('top_offres', 'offres_scores_staging') }}

),

a_scorer as (

    select countif(a_scorer) as nb_a_scorer
    from {{ ref('int_offres_a_scorer') }}

)

select
    nb_staging,
    nb_a_scorer
from staging
cross join a_scorer
where nb_staging != nb_a_scorer

-- Socle dédié à Q03 (top entreprises qui recrutent). Séparé de
-- int_offres_agg_jour car entreprise_nom est une dimension à cardinalité
-- élevée — la combiner avec les autres dimensions ferait perdre l'intérêt
-- de la pré-agrégation.
--
-- Filtre qualité appliqué ici (couche intermediate) : entreprise_nom non
-- vide, cohérent avec le filtre déjà utilisé côté backend (market_queries.py).
--
-- Grain : une ligne = une combinaison unique de
-- (date_publication, source, entreprise_nom)

with stg as (

    select *
    from {{ ref('stg_offres') }}

),

filtered as (

    select *
    from stg
    where entreprise_nom is not null
      and entreprise_nom != ''

)

select
    date_publication,
    source,
    entreprise_nom,
    count(*) as nb_offres

from filtered
group by
    date_publication,
    source,
    entreprise_nom
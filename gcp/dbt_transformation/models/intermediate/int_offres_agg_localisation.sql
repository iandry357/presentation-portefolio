-- Socle dédié à Q04 (top localisations). Séparé de int_offres_agg_jour
-- pour la même raison que int_offres_agg_entreprise : localisation_libelle
-- est une dimension à cardinalité élevée.
--
-- Filtre qualité appliqué ici (couche intermediate) : localisation_libelle
-- non vide, cohérent avec le filtre déjà utilisé côté backend.
--
-- Grain : une ligne = une combinaison unique de
-- (date_publication, source, localisation_libelle)

with stg as (

    select *
    from {{ ref('stg_offres') }}

),

filtered as (

    select *
    from stg
    where localisation_libelle is not null
      and localisation_libelle != ''

)

select
    date_publication,
    source,
    localisation_libelle,
    count(*) as nb_offres

from filtered
group by
    date_publication,
    source,
    localisation_libelle
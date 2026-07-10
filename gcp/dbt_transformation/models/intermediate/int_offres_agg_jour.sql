-- Socle commun pour les questions d'agrégation simple du catalogue /market
-- (Q01, Q02, Q05, Q06, Q07, Q08, Q09, Q10). Chaque question fait son propre
-- GROUP BY partiel sur ce modèle (en sommant nb_offres sur les dimensions
-- qu'elle n'utilise pas), plutôt que de rescanner stg_offres à chaque appel.
--
-- Grain : une ligne = une combinaison unique de
-- (date_publication, source, type_contrat, code_rome, département, salaire_present)

with stg as (

    select *
    from {{ ref('stg_offres') }}

)

select
    date_publication,
    source,
    type_contrat,
    code_rome,
    libelle_rome,
    localisation_departement,
    salaire_present,
    count(*) as nb_offres

from stg
group by
    date_publication,
    source,
    type_contrat,
    code_rome,
    libelle_rome,
    localisation_departement,
    salaire_present
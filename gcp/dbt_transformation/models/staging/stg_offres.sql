-- Miroir de emploi_marche.offres_brutes, sans filtre métier ni agrégation.
-- Seule transformation appliquée : déduplication sur id_unique, en gardant
-- la ligne la plus récemment collectée en cas de doublon (réingestion).
-- Tout contrôle qualité/filtre métier est délégué aux modèles intermediate.

with base as (

    select *
    from {{ source('emploi_marche', 'offres_brutes') }}

),

deduplicated as (

    select
        *,
        row_number() over (
            partition by id_unique
            order by date_collecte desc
        ) as rn

    from base

)

select
    id_unique,
    source,
    id_source,
    date_publication,
    date_collecte,
    titre,
    description,
    entreprise_nom,
    localisation_libelle,
    localisation_commune,
    localisation_departement,
    localisation_lat,
    localisation_lng,
    type_contrat,
    type_contrat_libelle,
    experience_libelle,
    salaire_libelle,
    salaire_min,
    salaire_max,
    salaire_present,
    code_rome,
    libelle_rome,
    secteur_activite,
    secteur_activite_libelle,
    naf_code,
    competences,
    url_offre,
    alternance

from deduplicated
where rn = 1
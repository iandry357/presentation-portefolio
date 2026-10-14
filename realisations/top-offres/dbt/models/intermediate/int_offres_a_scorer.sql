-- Offres collectées sur la fenêtre [fenetre_debut, fenetre_fin[ (UTC), normalisées, marquées
-- (filtres durs : jamais supprimées) et dédoublonnées.
-- Variables : fenetre_debut, fenetre_fin (obligatoires), version_scoring (obligatoire sauf
-- si forcer ou si offres_scores n'existe pas encore), forcer (faux par défaut).

{% set rel_scores = adapter.get_relation(database=target.database, schema=target.schema, identifier='offres_scores') if execute else none %}

with fenetre as (

    select *
    from {{ source('emploi_marche', 'stg_offres') }}
    where date_collecte >= timestamp('{{ var("fenetre_debut") }}')
      and date_collecte <  timestamp('{{ var("fenetre_fin") }}')

),

normalisee as (

    select
        id_unique,
        source,
        titre,
        entreprise_nom,
        localisation_libelle,
        localisation_departement,
        type_contrat,
        type_contrat_libelle,
        salaire_libelle,
        url_offre,
        date_publication,
        date_collecte,
        alternance,
        {{ normaliser('titre') }} as titre_normalise,
        {{ normaliser('entreprise_nom') }} as entreprise_normalise,
        {{ normaliser('localisation_libelle') }} as libelle_normalise,
        {{ normaliser("concat(coalesce(type_contrat, ''), ' | ', coalesce(type_contrat_libelle, ''))") }} as type_normalise

    from fenetre

),

localisee as (

    -- Département : colonne si renseignée, sinon extrait du libellé (parenthèses, "NN - ville",
    -- "ville - NN", code postal à 5 chiffres, mot "Paris") ; sinon inconnu (null).
    select
        *,
        coalesce(
            nullif(trim(localisation_departement), ''),
            regexp_extract(localisation_libelle, r'(?i)\((\d{2}|2[ab]|97\d)\)'),
            regexp_extract(localisation_libelle, r'^\s*(\d{2})\s*-'),
            regexp_extract(localisation_libelle, r'-\s*(\d{2})\s*$'),
            substr(regexp_extract(localisation_libelle, r'\b(\d{5})\b'), 1, 2),
            if(regexp_contains(libelle_normalise, r'\bparis\b'), '75', null)
        ) as departement

    from normalisee

),

marquee as (

    select
        *,
        case
            when regexp_contains(titre_normalise, r'\b(stage|stagiaire|internship|intern)s?\b')
              or regexp_contains(type_normalise, r'\b(stage|stagiaire|internship|intern)s?\b')
                then 'stage'
            when coalesce(alternance, false)
              or regexp_contains(titre_normalise, r'\b(alternance|alternant|alternante|apprenti|apprentie|professionnalisation|contrat (d |en )?apprentissage)s?\b')
              or regexp_contains(type_normalise, r'\b(alternance|alternant|alternante|apprentissage|apprenti|apprentie|professionnalisation)s?\b')
                then 'alternance'
            when departement is not null
              and departement not in (select code_departement from {{ ref('departements_idf') }})
                then 'hors_idf'
        end as filtre_dur,
        -- Entreprise inconnue : pas de dédoublonnage (chaque offre forme son propre groupe)
        concat(titre_normalise, ' | ', if(entreprise_normalise = '', id_unique, entreprise_normalise)) as cle_groupe

    from localisee

),

classee as (

    -- Représentant : de préférence une offre sans filtre dur, puis la plus récemment collectée
    select
        *,
        first_value(id_unique) over (
            partition by cle_groupe
            order by (filtre_dur is null) desc, date_collecte desc, id_unique
        ) as groupe_doublon

    from marquee

)

select
    id_unique,
    source,
    titre,
    titre_normalise,
    entreprise_nom,
    entreprise_normalise,
    localisation_libelle,
    departement,
    type_contrat,
    type_contrat_libelle,
    salaire_libelle,
    url_offre,
    date_publication,
    date_collecte,
    groupe_doublon,
    id_unique = groupe_doublon as est_representant,
    filtre_dur,
    (
        id_unique = groupe_doublon
        and filtre_dur is null
        {% if rel_scores is not none and not var('forcer', false) %}
        and id_unique not in (
            select id_unique
            from {{ rel_scores }}
            where version_scoring = '{{ var("version_scoring") }}'
        )
        {% endif %}
    ) as a_scorer

from classee

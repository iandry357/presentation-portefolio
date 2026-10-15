-- Top du jour : dernier score de chaque offre scorée (tout l'historique de offres_scores), plus les doublons et
-- les offres filtrées de la fenêtre courante (int_offres_a_scorer), avec les métadonnées de stg_offres et les
-- informations entreprise. Le top N et l'exclusion des offres déjà traitées sont calculés à l'affichage (backend).
-- Les entreprises exclues sont marquées (entreprise_exclue), jamais masquées ici : l'affichage choisit de les montrer.
-- Variables obligatoires : seuil_haut, seuil_bas.

with scores_courants as (

    -- Dernier score de chaque offre scorée (toutes versions de scoring confondues)
    select *
    from {{ ref('offres_scores') }}
    qualify row_number() over (partition by id_unique order by score_le desc) = 1

),

fenetre as (

    select id_unique, groupe_doublon, filtre_dur
    from {{ ref('int_offres_a_scorer') }}

),

offres as (

    -- Offres scorées (représentants), sur tout l'historique
    select
        id_unique,
        id_unique as groupe_doublon,
        cast(null as string) as filtre_dur,
        id_unique as id_score
    from scores_courants

    union all

    -- Doublons de la fenêtre courante : ils héritent du score de leur représentant
    select
        f.id_unique,
        f.groupe_doublon,
        cast(null as string) as filtre_dur,
        f.groupe_doublon as id_score
    from fenetre as f
    inner join scores_courants as s
        on s.id_unique = f.groupe_doublon
    where f.id_unique != f.groupe_doublon
      and f.filtre_dur is null

    union all

    -- Offres de la fenêtre courante marquées par un filtre dur : masquées, sans score
    select
        id_unique,
        groupe_doublon,
        filtre_dur,
        cast(null as string) as id_score
    from fenetre
    where filtre_dur is not null
      and id_unique not in (select id_unique from scores_courants)

),

base as (

    select
        o.id_unique,
        o.groupe_doublon,
        o.filtre_dur,
        o.id_score,
        b.source,
        b.titre,
        {{ normaliser('b.titre') }} as titre_normalise,
        b.entreprise_nom,
        {{ normaliser('b.entreprise_nom') }} as entreprise_normalise,
        b.localisation_libelle,
        b.type_contrat,
        b.type_contrat_libelle,
        b.salaire_libelle,
        b.url_offre,
        b.date_publication,
        b.date_collecte
    from offres as o
    inner join {{ source('emploi_marche', 'stg_offres') }} as b
        on b.id_unique = o.id_unique

),

qualifiee as (

    select
        base.*,
        s.score,
        s.categorie,
        s.raison,
        s.alertes,
        s.cible_proche,
        s.similarite,
        date(s.score_le) as date_run,
        r.type_annonceur,
        r.naf_libelle,
        r.secteur,
        r.secteur_source,
        r.origine as origine_entreprise,
        r.confiance as confiance_entreprise,
        case
            when r.type_annonceur = 'intermediaire' then 'cabinet_recrutement'
            when r.naf_code = '62.02A' then 'esn'
            else 'non_identifie'
        end as type_entreprise,
        (base.entreprise_normalise != '' and x.nom_normalise is not null) as entreprise_exclue
    from base
    left join scores_courants as s
        on s.id_unique = base.id_score
    left join {{ source('top_offres', 'entreprises_ref') }} as r
        on r.nom_normalise = base.entreprise_normalise
    left join (
        select distinct nom_normalise
        from {{ source('top_offres', 'entreprises_exclues') }}
    ) as x
        on x.nom_normalise = base.entreprise_normalise

),

listee as (

    select
        *,
        case
            when filtre_dur is not null then 'masque'
            when score >= {{ var('seuil_haut') }} then 'a_lire'
            when score >= {{ var('seuil_bas') }} then 'zone_grise'
            else 'masque'
        end as liste,
        case
            when filtre_dur is not null then filtre_dur
            when score < {{ var('seuil_bas') }} then 'score_bas'
        end as motif_masque
    from qualifiee

),

rangs as (

    -- Rang et nombre d'offres par entreprise, calculés sur les représentants affichables (une ligne par groupe)
    select
        groupe_doublon,
        row_number() over (
            partition by if(entreprise_normalise = '', id_unique, entreprise_normalise)
            order by score desc, date_collecte desc, id_unique
        ) as rang_dans_entreprise,
        count(*) over (
            partition by if(entreprise_normalise = '', id_unique, entreprise_normalise)
        ) as nb_offres_entreprise
    from listee
    where id_unique = groupe_doublon
      and liste != 'masque'

)

select
    l.id_unique,
    l.groupe_doublon,
    l.source,
    l.titre,
    l.titre_normalise,
    l.entreprise_nom,
    l.entreprise_normalise,
    l.localisation_libelle,
    l.type_contrat,
    l.type_contrat_libelle,
    l.salaire_libelle,
    l.url_offre,
    l.date_publication,
    l.date_collecte,
    l.score,
    l.categorie,
    l.raison,
    l.alertes,
    l.cible_proche,
    l.similarite,
    l.liste,
    l.motif_masque,
    l.date_run,
    l.type_annonceur,
    l.naf_libelle,
    l.secteur,
    l.secteur_source,
    l.type_entreprise,
    l.origine_entreprise,
    l.confiance_entreprise,
    l.entreprise_exclue,
    g.rang_dans_entreprise,
    g.nb_offres_entreprise
from listee as l
left join rangs as g
    on g.groupe_doublon = l.groupe_doublon
    and l.liste != 'masque'

-- Statistiques journalières au format long : nombre d'offres par jour de collecte, par dimension et par valeur.
-- Calculées sur mart_top_du_jour ; aucun contenu d'offre (exposables publiquement par le backend).
-- Dimensions : liste, categorie, cible, type_annonceur, naf_libelle, source.
-- Les offres d'entreprises exclues comptent comme masquées (comportement d'affichage par défaut).

with offres as (

    select
        date(date_collecte) as jour,
        if(entreprise_exclue, 'masque', liste) as liste,
        categorie,
        cible_proche,
        type_annonceur,
        naf_libelle,
        source
    from {{ ref('mart_top_du_jour') }}

),

dimensions as (

    select jour, 'liste' as dimension, liste as valeur from offres
    union all
    select jour, 'categorie' as dimension, categorie as valeur from offres
    union all
    select jour, 'cible' as dimension, cible_proche as valeur from offres
    union all
    select jour, 'type_annonceur' as dimension, type_annonceur as valeur from offres
    union all
    select jour, 'naf_libelle' as dimension, naf_libelle as valeur from offres
    union all
    select jour, 'source' as dimension, source as valeur from offres

),

etiquetees as (

    select
        jour,
        dimension,
        coalesce(valeur, 'inconnu') as valeur
    from dimensions

)

select
    jour,
    dimension,
    valeur,
    count(*) as nb_offres
from etiquetees
group by jour, dimension, valeur

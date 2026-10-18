-- Porte de contrôle : la part des lignes dont statut_llm n'est pas ok ne doit pas dépasser la variable
-- taux_erreur_llm_max (le test échoue sinon). Variable obligatoire, passée par l'orchestrateur.

select
    count(*) as nb_lignes,
    countif(statut_llm != 'ok') as nb_erreurs,
    safe_divide(countif(statut_llm != 'ok'), count(*)) as taux_erreur
from {{ source('top_offres', 'offres_scores_staging') }}
having safe_divide(countif(statut_llm != 'ok'), count(*)) > {{ var('taux_erreur_llm_max') }}

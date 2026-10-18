-- Porte de contrôle : renvoie les lignes statut_llm = ok dont le score est absent ou hors de 0 à 100,
-- ou dont la catégorie est absente (le test échoue s'il y a des lignes).

select
    id_unique,
    score,
    categorie
from {{ source('top_offres', 'offres_scores_staging') }}
where statut_llm = 'ok'
  and (score is null or score not between 0 and 100 or categorie is null)

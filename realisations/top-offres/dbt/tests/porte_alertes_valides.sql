-- Porte de contrôle : renvoie les alertes hors de la liste autorisée (le test échoue s'il y a des lignes).

select
    s.id_unique,
    alerte
from {{ source('top_offres', 'offres_scores_staging') }} as s,
    unnest(s.alertes) as alerte
where alerte not in (
    'salaire_incoherent',
    'titre_ambigu',
    'intermediaire',
    'seniorite_incertaine',
    'autre'
)

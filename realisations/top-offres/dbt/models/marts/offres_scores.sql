-- Historique des scores LLM fusionnés : une ligne par (id_unique, version_scoring), statut_llm = ok uniquement.
-- Alimenté depuis le staging, après la porte de contrôle (tests dbt). Un `dbt run --full-refresh`
-- ne reconstruit jamais cette table (full_refresh=false) : l'historique des scores est conservé.

{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['id_unique', 'version_scoring'],
    full_refresh=false
) }}

select
    id_unique,
    version_scoring,
    run_id,
    cible_proche,
    similarite,
    score,
    categorie,
    raison,
    alertes,
    modele,
    version_prompt,
    version_cibles,
    score_le
from {{ source('top_offres', 'offres_scores_staging') }}
where statut_llm = 'ok'

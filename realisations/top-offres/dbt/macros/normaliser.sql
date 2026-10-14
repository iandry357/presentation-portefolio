-- Normalisation d'un texte (titre, entreprise, lieu) : minuscules, sans accents ni ponctuation,
-- espaces réduits, mentions de genre supprimées (H/F, F/H, (H/F/X), M/F, H-F...).
-- Une seule règle pour toutes les colonnes : réutilisable par les marts.

{% macro normaliser(expression) -%}
    coalesce(
        trim(
            regexp_replace(
                regexp_replace(
                    regexp_replace(
                        regexp_replace(
                            lower(normalize({{ expression }}, NFD)),
                            r'\pM', ''
                        ),
                        r'\b(h|f|m)\s*[/-]\s*(h|f)(\s*[/-]\s*(x|d|nb))?\b', ' '
                    ),
                    r'[^a-z0-9]+', ' '
                ),
                r'\s+', ' '
            )
        ),
        ''
    )
{%- endmacro %}

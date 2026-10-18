-- ============================================================================
-- 021_top_offres_types_entreprise.sql
-- MVP Top Offres : types d'entreprise corrigés par l'utilisateur
-- Le type affiché est celui de cette table s'il existe, sinon le type
-- automatique du mart BigQuery (non_identifie, esn, cabinet_recrutement).
-- ============================================================================

INSERT INTO schema_migrations (filename) VALUES ('021_top_offres_types_entreprise.sql');

-- ============================================================================
-- TABLE: top_offres_types_entreprise
-- Clé = nom_normalise (même normalisation que le mart : entreprise_normalise).
-- ============================================================================

CREATE TABLE top_offres_types_entreprise (
    nom_normalise TEXT PRIMARY KEY,
    type_entreprise VARCHAR(30) NOT NULL
        CHECK (type_entreprise IN ('esn', 'conseil', 'esn_conseil', 'cabinet_recrutement', 'client_final')),
    commentaire TEXT,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Trigger updated_at (fonction définie en 001)
CREATE TRIGGER top_offres_types_entreprise_updated_at
    BEFORE UPDATE ON top_offres_types_entreprise
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Fin du script
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Table top_offres_types_entreprise created successfully';
END $$;

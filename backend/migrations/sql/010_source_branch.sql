-- ============================================================================
-- 010_source_branch.sql
-- Ajout colonne source_branch sur job_offers
-- Traçabilité : provenance de l'offre (rome | mots_cles)
-- ============================================================================

INSERT INTO schema_migrations (filename) VALUES ('010_source_branch.sql');

ALTER TABLE job_offers
    ADD COLUMN source_branch VARCHAR(10);

CREATE INDEX IF NOT EXISTS job_offers_source_branch_idx
ON job_offers (source_branch);

DO $$
BEGIN
    RAISE NOTICE '010_source_branch.sql applied successfully';
    RAISE NOTICE 'Column added: source_branch on job_offers';
END $$;
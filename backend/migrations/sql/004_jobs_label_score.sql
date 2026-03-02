-- ============================================================================
-- 004_jobs_label_score.sql
-- Ajout colonnes label et score sur job_offers
-- ============================================================================

INSERT INTO schema_migrations (filename) VALUES ('004_jobs_label_score.sql');

-- ============================================================================
-- Colonnes
-- ============================================================================

ALTER TABLE job_offers
    ADD COLUMN label VARCHAR(20)
        CHECK (label IN ('basique', 'medium', 'priorité')),
    ADD COLUMN score FLOAT;

-- ============================================================================
-- Index sur label pour filtres frontend
-- ============================================================================

CREATE INDEX IF NOT EXISTS job_offers_label_idx
ON job_offers (label);

-- ============================================================================
-- Fin du script
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '004_jobs_label_score.sql applied successfully';
    RAISE NOTICE 'Columns added: label, score on job_offers';
END $$;
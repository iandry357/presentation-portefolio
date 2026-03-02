-- ============================================================================
-- 006_jobs_status_enregistre.sql
-- Ajout du statut 'enregistré' sur job_offers
-- ============================================================================

INSERT INTO schema_migrations (filename) VALUES ('006_jobs_status_enregistre.sql');

ALTER TABLE job_offers
    DROP CONSTRAINT job_offers_status_check;

ALTER TABLE job_offers
    ADD CONSTRAINT job_offers_status_check
    CHECK (status IN ('nouveau', 'existant', 'ferme', 'consulte', 'postule', 'enregistre'));

DO $$
BEGIN
    RAISE NOTICE '006_jobs_status_enregistre.sql applied successfully';
    RAISE NOTICE 'Status enregistré added to job_offers';
END $$;
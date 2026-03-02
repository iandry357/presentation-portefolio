-- ============================================================================
-- 005_jobs_rome_source.sql
-- Ajout colonne rome_source_intitule sur job_offers
-- Traçabilité : intitulé Mistral ayant généré le code ROME de l'offre
-- ============================================================================

INSERT INTO schema_migrations (filename) VALUES ('005_jobs_rome_source.sql');

ALTER TABLE job_offers
    ADD COLUMN rome_source_intitule VARCHAR(255);

CREATE INDEX IF NOT EXISTS job_offers_rome_source_intitule_idx
ON job_offers (rome_source_intitule);

DO $$
BEGIN
    RAISE NOTICE '005_jobs_rome_source.sql applied successfully';
    RAISE NOTICE 'Column added: rome_source_intitule on job_offers';
END $$;
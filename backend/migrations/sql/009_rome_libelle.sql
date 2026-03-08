-- ============================================================================
-- 009_rome_libelle.sql
-- Ajout colonne rome_libelle sur job_offers
-- Traçabilité : libellé ROME retourné par ROMEO pour l'offre
-- ============================================================================

INSERT INTO schema_migrations (filename) VALUES ('009_rome_libelle.sql');

ALTER TABLE job_offers
    ADD COLUMN rome_libelle VARCHAR(255);

CREATE INDEX IF NOT EXISTS job_offers_rome_libelle_idx
ON job_offers (rome_libelle);

DO $$
BEGIN
    RAISE NOTICE '009_rome_libelle.sql applied successfully';
    RAISE NOTICE 'Column added: rome_libelle on job_offers';
END $$;
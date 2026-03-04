-- ============================================================================
-- 007_jobs_status_manuel.sql
-- Ajout des statuts 'enregistre' et 'manuel' dans job_offers.status
-- ============================================================================

INSERT INTO schema_migrations (filename) VALUES ('007_jobs_status_manuel.sql');

-- PostgreSQL ne permet pas de modifier un CHECK directement
-- On supprime l'ancien et on recrée avec les nouvelles valeurs

ALTER TABLE job_offers DROP CONSTRAINT IF EXISTS job_offers_status_check;

ALTER TABLE job_offers ADD CONSTRAINT job_offers_status_check
  CHECK (status IN ('nouveau', 'existant', 'ferme', 'consulte', 'postule', 'enregistre', 'manuel'));

DO $$
BEGIN
    RAISE NOTICE 'Statuts enregistre et manuel ajoutés au CHECK de job_offers.status';
END $$;
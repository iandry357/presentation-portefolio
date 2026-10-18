-- ============================================================================
-- 019_jobs_status_brouillon.sql
-- Ajout du statut 'brouillon' dans job_offers.status (MVP Top Offres)
-- ============================================================================

INSERT INTO schema_migrations (filename) VALUES ('019_jobs_status_brouillon.sql');

-- PostgreSQL ne permet pas de modifier un CHECK directement
-- On supprime l'ancien et on recrée avec les nouvelles valeurs

ALTER TABLE job_offers DROP CONSTRAINT IF EXISTS job_offers_status_check;

ALTER TABLE job_offers ADD CONSTRAINT job_offers_status_check
  CHECK (status IN ('nouveau', 'existant', 'ferme', 'consulte', 'postule', 'enregistre', 'manuel', 'brouillon'));

DO $$
BEGIN
    RAISE NOTICE 'Statut brouillon ajouté au CHECK de job_offers.status';
END $$;

 
-- ============================================================================
-- 015_external_job_offer.sql
-- Support des offres externes (hors France Travail)
-- - ft_id devient nullable
-- - Ajout colonne source_offer
-- - score et label deviennent nullable
-- - label garde sa valeur par défaut 'basique'
-- ============================================================================

INSERT INTO schema_migrations (filename) VALUES ('015_external_job_offer.sql');

-- 1. ft_id nullable
ALTER TABLE job_offers
    ALTER COLUMN ft_id DROP NOT NULL;

-- 2. Index unique partiel sur ft_id (uniquement sur valeurs non nulles)
DROP INDEX IF EXISTS ix_job_offers_ft_id;
CREATE UNIQUE INDEX ix_job_offers_ft_id
    ON job_offers (ft_id)
    WHERE ft_id IS NOT NULL;

-- 3. Ajout colonne source_offer
ALTER TABLE job_offers
    ADD COLUMN IF NOT EXISTS source_offer VARCHAR(100) NOT NULL DEFAULT 'france_travail';

-- 4. score nullable
ALTER TABLE job_offers
    ALTER COLUMN score DROP NOT NULL;

-- 5. label nullable avec default basique
ALTER TABLE job_offers
    ALTER COLUMN label DROP NOT NULL,
    ALTER COLUMN label SET DEFAULT 'basique';

-- Vérification
SELECT column_name, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'job_offers'
AND column_name IN ('ft_id', 'source_offer', 'score', 'label')
ORDER BY column_name;
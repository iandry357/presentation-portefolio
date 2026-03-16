-- ============================================================================
-- 013_cv_embedding_status.sql
-- Ajout colonnes embedding_status pour suivi régénération embeddings
-- ============================================================================

-- Enregistrer cette migration
INSERT INTO schema_migrations (filename) VALUES ('013_cv_embedding_status.sql');

-- ============================================================================
-- TABLE: experiences
-- ============================================================================

-- Ajout colonne embedding_status
ALTER TABLE experiences
ADD COLUMN IF NOT EXISTS embedding_status VARCHAR(20) DEFAULT 'done' NOT NULL;

-- Commentaire pour documentation
COMMENT ON COLUMN experiences.embedding_status IS 'Statut de génération des embeddings: done, pending, failed';

-- Index pour filtrer les expériences en attente de régénération
CREATE INDEX IF NOT EXISTS experiences_embedding_status_idx 
ON experiences (embedding_status) 
WHERE embedding_status IN ('pending', 'failed');

-- ============================================================================
-- TABLE: projects
-- ============================================================================

-- Ajout colonne embedding_status
ALTER TABLE projects
ADD COLUMN IF NOT EXISTS embedding_status VARCHAR(20) DEFAULT 'done' NOT NULL;

-- Commentaire pour documentation
COMMENT ON COLUMN projects.embedding_status IS 'Statut de génération des embeddings: done, pending, failed';

-- Index pour filtrer les projets en attente de régénération
CREATE INDEX IF NOT EXISTS projects_embedding_status_idx 
ON projects (embedding_status) 
WHERE embedding_status IN ('pending', 'failed');

-- ============================================================================
-- Vérification
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 013 appliquée avec succès';
    RAISE NOTICE 'Colonnes embedding_status ajoutées sur experiences et projects';
    RAISE NOTICE 'Valeur par défaut: done (données existantes conservent leurs embeddings)';
END $$;
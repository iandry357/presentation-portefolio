 
-- Migration 008 : Ajout colonne is_stage sur experiences
-- Permet de distinguer les stages des expériences professionnelles
-- et de les pondérer différemment dans le pipeline RAG
INSERT INTO schema_migrations (filename) VALUES ('008_experiences_is_stage.sql');
ALTER TABLE experiences
ADD COLUMN IF NOT EXISTS is_stage BOOLEAN DEFAULT FALSE;

-- Mettre à jour les stages existants
-- Adapte les IDs selon tes données réelles
UPDATE experiences SET is_stage = TRUE WHERE id IN (1, 2, 3);

-- Vérification
SELECT id, role, start_date, is_stage FROM experiences ORDER BY start_date;
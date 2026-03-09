 INSERT INTO schema_migrations (filename) VALUES ('011_jobs_notes.sql');
-- Migration 011 — Ajout colonne notes sur job_offers
ALTER TABLE job_offers
ADD COLUMN IF NOT EXISTS notes TEXT;
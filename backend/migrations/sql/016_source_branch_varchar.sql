INSERT INTO schema_migrations (filename) VALUES ('016_source_branch_varchar.sql');

ALTER TABLE job_offers
ALTER COLUMN source_branch TYPE VARCHAR(50);
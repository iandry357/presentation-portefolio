-- ============================================================================
-- 022_top_offres_decision_expire.sql
-- MVP Top Offres : ajout de la décision 'expire' (offre plus en ligne),
-- traitée comme 'pas_interesse' par le top du jour.
-- ============================================================================

INSERT INTO schema_migrations (filename) VALUES ('022_top_offres_decision_expire.sql');

ALTER TABLE top_offres_decisions
    DROP CONSTRAINT top_offres_decisions_decision_check;

ALTER TABLE top_offres_decisions
    ADD CONSTRAINT top_offres_decisions_decision_check
    CHECK (decision IN ('pas_interesse', 'interesse', 'expire'));

DO $$
BEGIN
    RAISE NOTICE 'Decision expire added to top_offres_decisions';
END $$;

-- ============================================================================
-- 020_top_offres_decisions.sql
-- MVP Top Offres : décisions de l'utilisateur sur les offres du top du jour
-- Seules 'pas_interesse' et 'interesse' sont stockées ici : les états
-- brouillon / enregistree se lisent via job_offer_id -> job_offers.status.
-- ============================================================================

INSERT INTO schema_migrations (filename) VALUES ('020_top_offres_decisions.sql');

-- ============================================================================
-- TABLE: top_offres_decisions
-- Clé = id_unique de l'offre exacte (BigQuery, mart_top_du_jour).
-- groupe_doublon : clé de groupe de doublons, enregistrée en plus.
-- titre_normalise / entreprise_normalise : rapprochement avec job_offers.
-- job_offer_id : NULL pour 'pas_interesse' ; si l'offre de job_offers est
-- supprimée, la décision est conservée (ON DELETE SET NULL).
-- ============================================================================

CREATE TABLE top_offres_decisions (
    id_unique TEXT PRIMARY KEY,
    decision VARCHAR(20) NOT NULL
        CHECK (decision IN ('pas_interesse', 'interesse')),
    job_offer_id INTEGER REFERENCES job_offers(id) ON DELETE SET NULL,
    groupe_doublon TEXT NOT NULL,
    titre_normalise TEXT NOT NULL DEFAULT '',
    entreprise_normalise TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX top_offres_decisions_job_offer_id_idx ON top_offres_decisions (job_offer_id);
CREATE INDEX top_offres_decisions_groupe_idx ON top_offres_decisions (groupe_doublon);

-- Trigger updated_at (fonction définie en 001)
CREATE TRIGGER top_offres_decisions_updated_at
    BEFORE UPDATE ON top_offres_decisions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Fin du script
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Table top_offres_decisions created successfully';
END $$;

-- ============================================================================
-- 002_complete_logging.sql
-- Enrichissement tables pour logging complet RAG
-- ============================================================================

-- Vérifier que migration non déjà appliquée
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_migrations WHERE filename = '002_complete_logging.sql') THEN
        RAISE EXCEPTION 'Migration 002_complete_logging.sql already applied';
    END IF;
END $$;

-- ============================================================================
-- ENRICHIR retrieval_logs
-- ============================================================================

ALTER TABLE retrieval_logs 
  ADD COLUMN nb_chunks_retrieved INTEGER DEFAULT 0,
  ADD COLUMN llm_provider VARCHAR(50),
  ADD COLUMN embedding_tokens INTEGER DEFAULT 0,
  ADD COLUMN llm_tokens INTEGER DEFAULT 0,
  ADD COLUMN embedding_cost DECIMAL(10,6) DEFAULT 0.0,
  ADD COLUMN llm_cost DECIMAL(10,6) DEFAULT 0.0,
  ADD COLUMN total_cost DECIMAL(10,6) DEFAULT 0.0,
  ADD COLUMN latency_retrieval_ms INTEGER,
  ADD COLUMN latency_generation_ms INTEGER,
  ADD COLUMN latency_total_ms INTEGER;

-- Index sur provider pour stats
CREATE INDEX IF NOT EXISTS retrieval_logs_llm_provider_idx 
ON retrieval_logs (llm_provider);

-- ============================================================================
-- ENRICHIR chat_sessions
-- ============================================================================

ALTER TABLE chat_sessions
  ADD COLUMN avg_latency_ms INTEGER DEFAULT 0,
  ADD COLUMN providers_used JSONB DEFAULT '{}';

-- ============================================================================
-- ENREGISTRER migration
-- ============================================================================

INSERT INTO schema_migrations (filename) VALUES ('002_complete_logging.sql');

-- Confirmation
DO $$
BEGIN
    RAISE NOTICE '✅ Migration 002 applied successfully';
    RAISE NOTICE 'retrieval_logs enriched: tokens, costs, latencies, provider';
    RAISE NOTICE 'chat_sessions enriched: avg_latency_ms, providers_used';
END $$;
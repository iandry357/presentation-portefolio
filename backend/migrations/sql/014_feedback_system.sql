-- ============================================================================
-- 014_feedback_system.sql
-- Système de feedback par page
-- ============================================================================

-- Enregistrer cette migration
INSERT INTO schema_migrations (filename) VALUES ('014_feedback_system.sql');

-- ============================================================================
-- TABLE: page_feedbacks
-- ============================================================================

CREATE TABLE page_feedbacks (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    user_id INTEGER DEFAULT NULL,  -- FK future vers table users
    page_route VARCHAR(255) NOT NULL,
    page_type VARCHAR(50) NOT NULL,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    job_offer_id INTEGER DEFAULT NULL REFERENCES job_offers(id) ON DELETE SET NULL,
    company_profile_id INTEGER DEFAULT NULL REFERENCES company_profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT now() NOT NULL
);

-- Index pour recherches rapides
CREATE INDEX page_feedbacks_session_id_idx ON page_feedbacks (session_id);
CREATE INDEX page_feedbacks_created_at_idx ON page_feedbacks (created_at DESC);
CREATE INDEX page_feedbacks_page_type_idx ON page_feedbacks (page_type);
CREATE INDEX page_feedbacks_job_offer_id_idx ON page_feedbacks (job_offer_id);
CREATE INDEX page_feedbacks_company_profile_id_idx ON page_feedbacks (company_profile_id);

-- ============================================================================
-- TABLE: feedback_answers
-- ============================================================================

CREATE TABLE feedback_answers (
    id SERIAL PRIMARY KEY,
    feedback_id INTEGER NOT NULL REFERENCES page_feedbacks(id) ON DELETE CASCADE,
    question_key VARCHAR(100) NOT NULL,
    comment TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT now() NOT NULL
);

-- Index pour jointures rapides
CREATE INDEX feedback_answers_feedback_id_idx ON feedback_answers (feedback_id);

-- ============================================================================
-- Fin du script
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Feedback system tables created successfully';
    RAISE NOTICE 'Tables: page_feedbacks, feedback_answers';
    RAISE NOTICE 'Ready to collect user feedback!';
END $$;
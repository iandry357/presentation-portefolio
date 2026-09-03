-- ============================================================================
-- 017_gestion_patrimoine_messages.sql
-- Sessions et historique de conversation du MVP gestion-patrimoine
-- ============================================================================

-- Enregistrer cette migration
INSERT INTO schema_migrations (filename) VALUES ('017_gestion_patrimoine_messages.sql');

-- ============================================================================
-- TABLE: gestion_patrimoine_sessions
-- Une session = un profil client généré par profil_agent. session_id généré
-- côté backend (Python uuid4()) à la création du profil, pas de valeur par
-- défaut côté SQL.
-- ============================================================================

CREATE TABLE gestion_patrimoine_sessions (
    session_id UUID PRIMARY KEY,
    thematique VARCHAR(50) NOT NULL,
    profil JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT now() NOT NULL
);

-- Index pour recherches rapides
CREATE INDEX gestion_patrimoine_sessions_created_at_idx ON gestion_patrimoine_sessions (created_at DESC);
CREATE INDEX gestion_patrimoine_sessions_thematique_idx ON gestion_patrimoine_sessions (thematique);

-- ============================================================================
-- TABLE: gestion_patrimoine_messages
-- Un enregistrement par échange. role distingue explicitement les 3 sources
-- possibles pour ne jamais dépendre de cout_estime pour deviner qui a parlé :
--   - 'user'         : message de l'utilisateur (tours suivants du chat)
--   - 'profil_agent' : génération du profil via Mistral (coût API réel)
--   - 'assistant'     : réponse du LLM local OVH (cout_estime = 0 explicite)
-- ============================================================================

CREATE TABLE gestion_patrimoine_messages (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES gestion_patrimoine_sessions(session_id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'profil_agent', 'assistant')),
    contenu TEXT NOT NULL,
    tokens_entree INTEGER NOT NULL DEFAULT 0,
    tokens_sortie INTEGER NOT NULL DEFAULT 0,
    cout_estime NUMERIC(10, 6) NOT NULL DEFAULT 0,
    latence_ms INTEGER NOT NULL DEFAULT 0,
    articles_cites JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP DEFAULT now() NOT NULL
);

-- Index pour jointures et tris rapides
CREATE INDEX gestion_patrimoine_messages_session_id_idx ON gestion_patrimoine_messages (session_id);
CREATE INDEX gestion_patrimoine_messages_created_at_idx ON gestion_patrimoine_messages (created_at DESC);
CREATE INDEX gestion_patrimoine_messages_role_idx ON gestion_patrimoine_messages (role);

-- ============================================================================
-- Fin du script
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Gestion-patrimoine tables created successfully';
    RAISE NOTICE 'Tables: gestion_patrimoine_sessions, gestion_patrimoine_messages';
    RAISE NOTICE 'Ready to track profiles and conversations!';
END $$;
-- ============================================================================
-- 001_init_schema.sql
-- Initialisation base de données Portfolio RAG
-- ============================================================================

-- Extension pgvector pour embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- TABLE: schema_migrations (tracking SQL migrations)
-- ============================================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT now()
);

-- Enregistrer cette migration
INSERT INTO schema_migrations (filename) VALUES ('001_init_schema.sql');

-- ============================================================================
-- FONCTION: Trigger updated_at automatique
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TABLE: experiences
-- ============================================================================

CREATE TABLE experiences (
    id SERIAL PRIMARY KEY,
    company VARCHAR(255) NOT NULL,
    role VARCHAR(255) NOT NULL,
    mission_type VARCHAR(50),
    start_date DATE NOT NULL,
    end_date DATE,
    duration_months INTEGER,
    location VARCHAR(255),
    context TEXT,
    technologies TEXT[],
    embedding VECTOR(1024),
    created_at TIMESTAMP DEFAULT now() NOT NULL,
    updated_at TIMESTAMP DEFAULT now() NOT NULL
);

-- Index HNSW pour recherche vectorielle
CREATE INDEX IF NOT EXISTS experiences_embedding_idx 
ON experiences USING hnsw (embedding vector_cosine_ops);

-- Index sur dates pour filtres temporels
CREATE INDEX IF NOT EXISTS experiences_dates_idx 
ON experiences (start_date DESC, end_date DESC);

-- Trigger updated_at
CREATE TRIGGER experiences_updated_at
    BEFORE UPDATE ON experiences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- TABLE: projects
-- ============================================================================

CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    experience_id INTEGER NOT NULL REFERENCES experiences(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    objective TEXT,
    problem TEXT,
    solution TEXT,
    results TEXT,
    impact TEXT,
    stack TEXT,
    start_date DATE,
    end_date DATE,
    duration_months INTEGER,
    collaborators TEXT,
    project_type VARCHAR(50),
    embedding VECTOR(1024),
    created_at TIMESTAMP DEFAULT now() NOT NULL,
    updated_at TIMESTAMP DEFAULT now() NOT NULL
);

-- Index HNSW pour recherche vectorielle
CREATE INDEX IF NOT EXISTS projects_embedding_idx 
ON projects USING hnsw (embedding vector_cosine_ops);

-- Index sur FK pour jointures rapides
CREATE INDEX IF NOT EXISTS projects_experience_id_idx 
ON projects (experience_id);

-- Trigger updated_at
CREATE TRIGGER projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- TABLE: formations
-- ============================================================================

CREATE TABLE formations (
    id SERIAL PRIMARY KEY,
    institution VARCHAR(255) NOT NULL,
    degree VARCHAR(255) NOT NULL,
    field VARCHAR(255),
    start_date DATE NOT NULL,
    end_date DATE,
    location VARCHAR(255),
    description TEXT,
    key_learnings TEXT,
    embedding VECTOR(1024),
    created_at TIMESTAMP DEFAULT now() NOT NULL,
    updated_at TIMESTAMP DEFAULT now() NOT NULL
);

-- Index HNSW pour recherche vectorielle
CREATE INDEX IF NOT EXISTS formations_embedding_idx 
ON formations USING hnsw (embedding vector_cosine_ops);

-- Index sur dates
CREATE INDEX IF NOT EXISTS formations_dates_idx 
ON formations (start_date DESC, end_date DESC);

-- Trigger updated_at
CREATE TRIGGER formations_updated_at
    BEFORE UPDATE ON formations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- TABLE: skills
-- ============================================================================

CREATE TABLE skills (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    category VARCHAR(100),
    proficiency_level VARCHAR(50),
    created_at TIMESTAMP DEFAULT now() NOT NULL
);

-- Index sur name pour recherches rapides
CREATE INDEX IF NOT EXISTS skills_name_idx ON skills (name);

-- Index sur category pour filtres
CREATE INDEX IF NOT EXISTS skills_category_idx ON skills (category);

-- ============================================================================
-- TABLES: Relations many-to-many
-- ============================================================================

CREATE TABLE experience_skills (
    experience_id INTEGER NOT NULL REFERENCES experiences(id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (experience_id, skill_id)
);

CREATE TABLE project_skills (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (project_id, skill_id)
);

-- Index pour jointures rapides
CREATE INDEX IF NOT EXISTS experience_skills_experience_id_idx 
ON experience_skills (experience_id);

CREATE INDEX IF NOT EXISTS experience_skills_skill_id_idx 
ON experience_skills (skill_id);

CREATE INDEX IF NOT EXISTS project_skills_project_id_idx 
ON project_skills (project_id);

CREATE INDEX IF NOT EXISTS project_skills_skill_id_idx 
ON project_skills (skill_id);

-- ============================================================================
-- TABLES: Chat & Sessions
-- ============================================================================

CREATE TABLE chat_sessions (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    user_identifier VARCHAR(255),
    created_at TIMESTAMP DEFAULT now() NOT NULL,
    question_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    total_cost DECIMAL(10, 6) DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS chat_sessions_session_id_idx 
ON chat_sessions (session_id);

CREATE INDEX IF NOT EXISTS chat_sessions_created_at_idx 
ON chat_sessions (created_at DESC);

CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS chat_messages_session_id_idx 
ON chat_messages (session_id);

CREATE INDEX IF NOT EXISTS chat_messages_created_at_idx 
ON chat_messages (created_at DESC);

-- ============================================================================
-- TABLES: Retrieval & Metrics
-- ============================================================================

CREATE TABLE retrieval_logs (
    id SERIAL PRIMARY KEY,
    query_id UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    retrieved_chunks JSONB,
    retrieval_method VARCHAR(50),
    latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS retrieval_logs_session_id_idx 
ON retrieval_logs (session_id);

CREATE INDEX IF NOT EXISTS retrieval_logs_created_at_idx 
ON retrieval_logs (created_at DESC);

CREATE TABLE feedback_logs (
    id SERIAL PRIMARY KEY,
    query_id UUID NOT NULL REFERENCES retrieval_logs(query_id) ON DELETE CASCADE,
    thumbs_up BOOLEAN,
    comment TEXT,
    created_at TIMESTAMP DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS feedback_logs_query_id_idx 
ON feedback_logs (query_id);

-- ============================================================================
-- Fin du script
-- ============================================================================

-- Afficher confirmation
DO $$
BEGIN
    RAISE NOTICE 'Schema initialized successfully';
    RAISE NOTICE 'Tables created: experiences, projects, formations, skills';
    RAISE NOTICE 'Relations created: experience_skills, project_skills';
    RAISE NOTICE 'Chat tables created: chat_sessions, chat_messages, retrieval_logs, feedback_logs';
    RAISE NOTICE 'HNSW indexes created on embeddings columns';
END $$;
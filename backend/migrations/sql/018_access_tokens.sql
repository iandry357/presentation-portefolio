-- ============================================================================
-- 018_access_tokens.sql
-- Contrôle d'accès public / privé : jetons de privilège + compteur anti brute-force
-- Indépendant de chat_sessions (aucune FK).
-- ============================================================================

-- Enregistrer cette migration
INSERT INTO schema_migrations (filename) VALUES ('018_access_tokens.sql');

-- ============================================================================
-- TABLE: access_tokens
-- Un enregistrement par jeton de privilège actif. Seul le hash SHA-256 (hex) du
-- jeton est stocké : le jeton en clair n'existe que dans le cookie httpOnly.
-- Fenêtre glissante : expires_at est repoussé à chaque requête protégée réussie.
-- ============================================================================

CREATE TABLE access_tokens (
    id SERIAL PRIMARY KEY,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);

-- Index pour la purge des jetons expirés (token_hash est déjà indexé via UNIQUE)
CREATE INDEX access_tokens_expires_at_idx ON access_tokens (expires_at);

-- ============================================================================
-- TABLE: access_attempts
-- Compteur d'échecs de saisie du code, clé = cookie visiteur (visitor_id généré
-- côté backend, Python uuid4(), pas de valeur par défaut côté SQL).
-- blocked_until NULL = non bloqué. Remise à zéro à la lecture une fois
-- blocked_until dépassé, ou immédiatement si le code saisi est correct.
-- ============================================================================

CREATE TABLE access_attempts (
    visitor_id UUID PRIMARY KEY,
    failed_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_count >= 0),
    blocked_until TIMESTAMPTZ DEFAULT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Index pour la purge des anciennes lignes
CREATE INDEX access_attempts_updated_at_idx ON access_attempts (updated_at);

-- Trigger updated_at (fonction définie en 001)
CREATE TRIGGER access_attempts_updated_at
    BEFORE UPDATE ON access_attempts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Fin du script
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Access control tables created successfully';
    RAISE NOTICE 'Tables: access_tokens, access_attempts';
END $$;

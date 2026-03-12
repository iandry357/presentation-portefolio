-- ============================================================
-- Migration 012 — company_profiles
-- ============================================================
 INSERT INTO schema_migrations (filename) VALUES ('012_company_profiles.sql');
-- ------------------------------------------------------------
-- TABLE company_profiles
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS company_profiles (

    -- Identité
    id                      SERIAL PRIMARY KEY,
    name                    VARCHAR(255) NOT NULL,          -- nom normalisé (lowercase, sans forme juridique)
    name_input              VARCHAR(255) NOT NULL,          -- nom brut saisi ou détecté

    -- Données par couche
    discovery               JSONB,                          -- Agent 1 : SIREN, URLs référence, famille 1
    legal_data              JSONB,                          -- Agent 2 : santé financière, activité, image employeur
    actualites              JSONB,                          -- refresh indépendant : articles, signaux recrutement
    memo                    TEXT,                           -- Agent 3 : mémo Markdown final

    -- Statuts par couche
    discovery_status        VARCHAR(10)  NOT NULL DEFAULT 'pending'
                                CHECK (discovery_status IN ('pending', 'done', 'failed')),

    legal_status            VARCHAR(10)  NOT NULL DEFAULT 'pending'
                                CHECK (legal_status IN ('pending', 'done', 'failed')),

    actualites_status       VARCHAR(10)  NOT NULL DEFAULT 'pending'
                                CHECK (actualites_status IN ('pending', 'done', 'failed')),

    memo_status             VARCHAR(10)  NOT NULL DEFAULT 'pending'
                                CHECK (memo_status IN ('pending', 'done', 'failed')),

    -- Contrôle mémo
    recalcul_count          INTEGER      NOT NULL DEFAULT 0,
    recalcul_history        JSONB        NOT NULL DEFAULT '[]'::jsonb,

    -- Horodatage
    actualites_updated_at   TIMESTAMP,                      -- dernière mise à jour des actualités
    created_at              TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP    NOT NULL DEFAULT NOW()

);

-- Unicité sur le nom normalisé
CREATE UNIQUE INDEX IF NOT EXISTS uix_company_profiles_name
    ON company_profiles (name);

-- Index recherche par statut global (utile pour monitoring pipeline)
CREATE INDEX IF NOT EXISTS idx_company_profiles_discovery_status
    ON company_profiles (discovery_status);

CREATE INDEX IF NOT EXISTS idx_company_profiles_memo_status
    ON company_profiles (memo_status);

-- ------------------------------------------------------------
-- MODIFICATION TABLE job_offers
-- FK nullable vers company_profiles
-- ------------------------------------------------------------

ALTER TABLE job_offers
    ADD COLUMN IF NOT EXISTS company_profile_id INTEGER
        REFERENCES company_profiles (id)
        ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_job_offers_company_profile_id
    ON job_offers (company_profile_id);

-- ------------------------------------------------------------
-- Trigger updated_at automatique sur company_profiles
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION update_company_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_company_profiles_updated_at
    BEFORE UPDATE ON company_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_company_profiles_updated_at();
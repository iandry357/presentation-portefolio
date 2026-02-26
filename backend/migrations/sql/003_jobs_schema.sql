-- ============================================================================
-- 003_jobs_schema.sql
-- Tables offres France Travail - offre brute + fiche enrichie
-- ============================================================================

-- Enregistrer cette migration
INSERT INTO schema_migrations (filename) VALUES ('003_jobs_schema.sql');

-- ============================================================================
-- TABLE: job_offers (offres brutes France Travail)
-- ============================================================================

CREATE TABLE job_offers (
    id                      SERIAL PRIMARY KEY,

    -- Identifiant France Travail (dédoublonnage)
    ft_id                   VARCHAR(50) NOT NULL UNIQUE,

    -- Infos principales
    title                   VARCHAR(255) NOT NULL,
    description             TEXT,
    contract_type           VARCHAR(50),
    contract_label          VARCHAR(100),
    work_time               VARCHAR(100),

    -- Expérience
    experience_code         VARCHAR(10),
    experience_label        VARCHAR(255),

    -- ROME
    rome_code               VARCHAR(10),

    -- Localisation
    location_label          VARCHAR(255),
    location_postal_code    VARCHAR(10),
    location_lat            FLOAT,
    location_lng            FLOAT,

    -- Entreprise
    company_name            VARCHAR(255),
    company_description     TEXT,
    company_url             TEXT,

    -- Salaire (libellé brut, parsing par le Crew)
    salary_label            VARCHAR(255),

    -- Secteur
    sector_label            VARCHAR(255),
    naf_code                VARCHAR(20),

    -- URLs
    offer_url               TEXT,

    -- Dates France Travail
    ft_published_at         TIMESTAMP,
    ft_updated_at           TIMESTAMP,

    -- Données brutes complètes
    raw_data                JSONB NOT NULL,

    -- Suivi statut
    -- nouveau   : offre < 24h en base
    -- existant  : offre >= 24h en base
    -- ferme     : offre disparue du scheduler
    -- consulte  : page détail ouverte
    -- postule   : marqué manuellement
    status                  VARCHAR(20) NOT NULL DEFAULT 'nouveau'
                            CHECK (status IN ('nouveau', 'existant', 'ferme', 'consulte', 'postule')),
    last_seen_at            TIMESTAMP DEFAULT now() NOT NULL,
    applied_at              TIMESTAMP,

    created_at              TIMESTAMP DEFAULT now() NOT NULL,
    updated_at              TIMESTAMP DEFAULT now() NOT NULL
);

-- Index pour dédoublonnage et lookups rapides
CREATE INDEX IF NOT EXISTS job_offers_ft_id_idx
ON job_offers (ft_id);

-- Index pour filtres frontend
CREATE INDEX IF NOT EXISTS job_offers_status_idx
ON job_offers (status);

CREATE INDEX IF NOT EXISTS job_offers_contract_type_idx
ON job_offers (contract_type);

CREATE INDEX IF NOT EXISTS job_offers_rome_code_idx
ON job_offers (rome_code);

CREATE INDEX IF NOT EXISTS job_offers_location_postal_code_idx
ON job_offers (location_postal_code);

CREATE INDEX IF NOT EXISTS job_offers_ft_published_at_idx
ON job_offers (ft_published_at DESC);

CREATE INDEX IF NOT EXISTS job_offers_created_at_idx
ON job_offers (created_at DESC);

-- Trigger updated_at
CREATE TRIGGER job_offers_updated_at
    BEFORE UPDATE ON job_offers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- TABLE: job_enriched (fiches enrichies par le Crew)
-- ============================================================================

CREATE TABLE job_enriched (
    id                  SERIAL PRIMARY KEY,

    -- Référence offre brute
    job_offer_id        INTEGER NOT NULL REFERENCES job_offers(id) ON DELETE CASCADE,

    -- Score pgvector interne (jamais exposé au frontend)
    score               FLOAT NOT NULL DEFAULT 0.0,

    -- Résultats du Crew
    parsed_data         JSONB,   -- Agent Parser : salaire parsé, stack, expérience numérique...
    analysis            JSONB,   -- Agent Analyste : points forts/faibles vs profil
    summary             TEXT,    -- Agent Rédacteur : fiche synthétique rédigée

    -- Traçabilité des prompts et recalculs
    initial_prompt      TEXT,
    recalcul_history    JSONB DEFAULT '[]'::jsonb,
    recalcul_count      INTEGER NOT NULL DEFAULT 0
                        CHECK (recalcul_count <= 3),

    created_at          TIMESTAMP DEFAULT now() NOT NULL,
    updated_at          TIMESTAMP DEFAULT now() NOT NULL
);

-- Index FK pour jointures rapides
CREATE INDEX IF NOT EXISTS job_enriched_job_offer_id_idx
ON job_enriched (job_offer_id);

-- Index sur score pour tri par pertinence
CREATE INDEX IF NOT EXISTS job_enriched_score_idx
ON job_enriched (score DESC);

-- Trigger updated_at
CREATE TRIGGER job_enriched_updated_at
    BEFORE UPDATE ON job_enriched
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- Fin du script
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Jobs schema created successfully';
    RAISE NOTICE 'Tables created: job_offers, job_enriched';
    RAISE NOTICE 'Indexes created on: status, contract_type, rome_code, postal_code, score';
END $$;
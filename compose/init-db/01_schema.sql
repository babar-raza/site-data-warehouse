-- GSC Data Warehouse Schema
-- Phase 1: Core tables and indexes

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop existing schema if needed (for clean installs)
DROP SCHEMA IF EXISTS gsc CASCADE;
CREATE SCHEMA gsc;

-- Set default search path
SET search_path TO gsc, public;

-- =============================================
-- DIMENSION TABLES
-- =============================================

-- Dimension: Properties
CREATE TABLE IF NOT EXISTS gsc.dim_property (
    property_id SERIAL PRIMARY KEY,
    property_url VARCHAR(500) UNIQUE NOT NULL,
    property_type VARCHAR(50) NOT NULL, -- 'URL_PREFIX', 'DOMAIN', 'SC_DOMAIN'
    has_bulk_export BOOLEAN DEFAULT FALSE,
    api_only BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Dimension: Pages
CREATE TABLE IF NOT EXISTS gsc.dim_page (
    page_id SERIAL PRIMARY KEY,
    property_id INTEGER REFERENCES gsc.dim_property(property_id),
    page_url TEXT NOT NULL,
    page_path TEXT,
    is_canonical BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(property_id, page_url)
);

-- Dimension: Queries
CREATE TABLE IF NOT EXISTS gsc.dim_query (
    query_id SERIAL PRIMARY KEY,
    query_text TEXT UNIQUE NOT NULL,
    query_hash VARCHAR(64) GENERATED ALWAYS AS (encode(digest(query_text, 'sha256'), 'hex')) STORED,
    is_branded BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on query_hash for faster lookups
CREATE INDEX idx_dim_query_hash ON gsc.dim_query(query_hash);

-- =============================================
-- FACT TABLE
-- =============================================

-- Main fact table for GSC daily data
CREATE TABLE IF NOT EXISTS gsc.fact_gsc_daily (
    date DATE NOT NULL,
    property VARCHAR(500) NOT NULL,
    url TEXT NOT NULL,
    query TEXT NOT NULL,
    country VARCHAR(3) NOT NULL,
    device VARCHAR(20) NOT NULL,
    clicks INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    ctr NUMERIC(10,6) DEFAULT 0,
    position NUMERIC(10,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Composite primary key
    PRIMARY KEY (date, property, url, query, country, device)
);

-- Create indexes for common query patterns
CREATE INDEX idx_fact_gsc_date ON gsc.fact_gsc_daily(date DESC);
CREATE INDEX idx_fact_gsc_property ON gsc.fact_gsc_daily(property);
CREATE INDEX idx_fact_gsc_url ON gsc.fact_gsc_daily(url);
CREATE INDEX idx_fact_gsc_query ON gsc.fact_gsc_daily(query);
CREATE INDEX idx_fact_gsc_date_property ON gsc.fact_gsc_daily(date DESC, property);

-- Create covering index for common aggregations
CREATE INDEX idx_fact_gsc_covering ON gsc.fact_gsc_daily(
    date DESC, 
    property, 
    clicks, 
    impressions
) INCLUDE (ctr, position);

-- =============================================
-- WATERMARK TABLE
-- =============================================

-- Track ingestion watermarks per property and source
CREATE TABLE IF NOT EXISTS gsc.ingest_watermarks (
    watermark_id SERIAL PRIMARY KEY,
    property VARCHAR(500) NOT NULL,
    source_type VARCHAR(10) NOT NULL CHECK (source_type IN ('bq', 'api')),
    last_date DATE,
    last_partition VARCHAR(50),
    rows_processed BIGINT DEFAULT 0,
    last_run_at TIMESTAMP,
    last_run_status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(property, source_type)
);

-- =============================================
-- AUDIT AND MONITORING
-- =============================================

-- Ingestion audit log
CREATE TABLE IF NOT EXISTS gsc.audit_log (
    audit_id SERIAL PRIMARY KEY,
    process_name VARCHAR(100) NOT NULL,
    property VARCHAR(500),
    source_type VARCHAR(10),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    rows_inserted INTEGER DEFAULT 0,
    rows_updated INTEGER DEFAULT 0,
    rows_failed INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'running',
    error_details TEXT,
    metadata JSONB
);

-- =============================================
-- HELPER FUNCTIONS
-- =============================================

-- Function to update timestamps
CREATE OR REPLACE FUNCTION gsc.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply update trigger to tables with updated_at
CREATE TRIGGER update_dim_property_updated_at BEFORE UPDATE ON gsc.dim_property
    FOR EACH ROW EXECUTE FUNCTION gsc.update_updated_at_column();

CREATE TRIGGER update_dim_page_updated_at BEFORE UPDATE ON gsc.dim_page
    FOR EACH ROW EXECUTE FUNCTION gsc.update_updated_at_column();

CREATE TRIGGER update_fact_gsc_daily_updated_at BEFORE UPDATE ON gsc.fact_gsc_daily
    FOR EACH ROW EXECUTE FUNCTION gsc.update_updated_at_column();

CREATE TRIGGER update_ingest_watermarks_updated_at BEFORE UPDATE ON gsc.ingest_watermarks
    FOR EACH ROW EXECUTE FUNCTION gsc.update_updated_at_column();

-- =============================================
-- UPSERT STORED PROCEDURE
-- =============================================

-- Create a function for UPSERT operations on fact table
CREATE OR REPLACE FUNCTION gsc.upsert_fact_gsc_daily(
    p_date DATE,
    p_property VARCHAR(500),
    p_url TEXT,
    p_query TEXT,
    p_country VARCHAR(3),
    p_device VARCHAR(20),
    p_clicks INTEGER,
    p_impressions INTEGER,
    p_ctr NUMERIC(10,6),
    p_position NUMERIC(10,2)
) RETURNS VOID AS $$
BEGIN
    INSERT INTO gsc.fact_gsc_daily (
        date, property, url, query, country, device,
        clicks, impressions, ctr, position
    ) VALUES (
        p_date, p_property, p_url, p_query, p_country, p_device,
        p_clicks, p_impressions, p_ctr, p_position
    )
    ON CONFLICT (date, property, url, query, country, device)
    DO UPDATE SET
        clicks = EXCLUDED.clicks,
        impressions = EXCLUDED.impressions,
        ctr = EXCLUDED.ctr,
        position = EXCLUDED.position,
        updated_at = CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- INITIAL DATA AND PERMISSIONS
-- =============================================

-- Grant permissions to gsc_user (assuming the user exists)
GRANT ALL PRIVILEGES ON SCHEMA gsc TO gsc_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA gsc TO gsc_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA gsc TO gsc_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA gsc TO gsc_user;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA gsc 
    GRANT ALL PRIVILEGES ON TABLES TO gsc_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA gsc 
    GRANT ALL PRIVILEGES ON SEQUENCES TO gsc_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA gsc 
    GRANT EXECUTE ON FUNCTIONS TO gsc_user;

-- Create initial watermark entries for mock properties (from Phase 0)
INSERT INTO gsc.dim_property (property_url, property_type, has_bulk_export, api_only)
VALUES 
    ('https://example.com/', 'URL_PREFIX', true, false),
    ('https://subdomain.example.com/', 'URL_PREFIX', false, true),
    ('sc-domain:example.net', 'SC_DOMAIN', true, false)
ON CONFLICT (property_url) DO NOTHING;

-- Initialize watermarks
INSERT INTO gsc.ingest_watermarks (property, source_type, last_date, last_run_status)
SELECT 
    property_url,
    CASE 
        WHEN has_bulk_export THEN 'bq'
        ELSE 'api'
    END,
    '2025-01-01'::DATE,
    'pending'
FROM gsc.dim_property
ON CONFLICT (property, source_type) DO NOTHING;

-- =============================================
-- STATISTICS AND MAINTENANCE
-- =============================================

-- Update table statistics
ANALYZE gsc.fact_gsc_daily;
ANALYZE gsc.dim_property;
ANALYZE gsc.dim_page;
ANALYZE gsc.dim_query;
ANALYZE gsc.ingest_watermarks;

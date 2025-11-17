-- GA4 Data Schema
-- Stores daily GA4 metrics by page path

SET search_path TO gsc, public;

-- Drop existing table if needed (for clean installs)
DROP TABLE IF EXISTS gsc.fact_ga4_daily CASCADE;

-- Create fact table for GA4 daily data
CREATE TABLE gsc.fact_ga4_daily (
    date DATE NOT NULL,
    property VARCHAR(255) NOT NULL,
    page_path TEXT NOT NULL,
    sessions INTEGER DEFAULT 0,
    engaged_sessions INTEGER DEFAULT 0,
    engagement_rate NUMERIC(5,4) DEFAULT 0,
    bounce_rate NUMERIC(5,4) DEFAULT 0,
    conversions INTEGER DEFAULT 0,
    conversion_rate NUMERIC(5,4) DEFAULT 0,
    avg_session_duration NUMERIC(10,2) DEFAULT 0,
    page_views INTEGER DEFAULT 0,
    avg_time_on_page NUMERIC(10,2) DEFAULT 0,
    exits INTEGER DEFAULT 0,
    exit_rate NUMERIC(5,4) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date, property, page_path)
);

-- Create indexes for common query patterns
CREATE INDEX idx_ga4_date ON gsc.fact_ga4_daily(date DESC);
CREATE INDEX idx_ga4_property ON gsc.fact_ga4_daily(property);
CREATE INDEX idx_ga4_page_path ON gsc.fact_ga4_daily(page_path);
CREATE INDEX idx_ga4_date_property ON gsc.fact_ga4_daily(date DESC, property);
CREATE INDEX idx_ga4_date_page ON gsc.fact_ga4_daily(date DESC, page_path);

-- Create covering index for common aggregations
CREATE INDEX idx_ga4_covering ON gsc.fact_ga4_daily(
    date DESC,
    property,
    sessions,
    conversions
) INCLUDE (engagement_rate, bounce_rate);

-- Add update trigger
CREATE TRIGGER update_fact_ga4_daily_updated_at 
    BEFORE UPDATE ON gsc.fact_ga4_daily
    FOR EACH ROW EXECUTE FUNCTION gsc.update_updated_at_column();

-- Grant permissions
GRANT ALL PRIVILEGES ON gsc.fact_ga4_daily TO gsc_user;

-- Create watermark entries for GA4
INSERT INTO gsc.ingest_watermarks (property, source_type, last_date, last_run_status)
VALUES 
    ('https://example.com/', 'ga4', '2025-01-01'::DATE, 'pending')
ON CONFLICT (property, source_type) DO NOTHING;

-- Update table statistics
ANALYZE gsc.fact_ga4_daily;

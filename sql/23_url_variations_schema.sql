-- URL Variations Schema for tracking URL variations
-- This enables consolidation of URL variations that represent the same content
-- Created: 2025-11-26
-- Purpose: Track and analyze URL variations (query params, fragments, trailing slashes, case, protocol)

CREATE SCHEMA IF NOT EXISTS analytics;

-- Main table for tracking URL variations
CREATE TABLE IF NOT EXISTS analytics.url_variations (
    id SERIAL PRIMARY KEY,
    property VARCHAR(255) NOT NULL,
    canonical_url VARCHAR(2000) NOT NULL,
    variation_url VARCHAR(2000) NOT NULL,
    variation_type VARCHAR(50) NOT NULL,  -- 'query_param', 'fragment', 'trailing_slash', 'case', 'protocol', 'other'
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    occurrences INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(property, canonical_url, variation_url)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_url_variations_property ON analytics.url_variations(property);
CREATE INDEX IF NOT EXISTS idx_url_variations_canonical ON analytics.url_variations(canonical_url);
CREATE INDEX IF NOT EXISTS idx_url_variations_variation ON analytics.url_variations(variation_url);
CREATE INDEX IF NOT EXISTS idx_url_variations_type ON analytics.url_variations(variation_type);
CREATE INDEX IF NOT EXISTS idx_url_variations_last_seen ON analytics.url_variations(last_seen);
CREATE INDEX IF NOT EXISTS idx_url_variations_occurrences ON analytics.url_variations(occurrences DESC);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_url_variations_property_canonical ON analytics.url_variations(property, canonical_url);
CREATE INDEX IF NOT EXISTS idx_url_variations_property_type ON analytics.url_variations(property, variation_type);

-- View for consolidation candidates (URLs with multiple variations)
CREATE OR REPLACE VIEW analytics.vw_url_consolidation_candidates AS
SELECT
    property,
    canonical_url,
    COUNT(DISTINCT variation_url) as variation_count,
    ARRAY_AGG(DISTINCT variation_type) as variation_types,
    SUM(occurrences) as total_occurrences,
    MIN(first_seen) as first_seen,
    MAX(last_seen) as last_seen,
    ARRAY_AGG(DISTINCT variation_url ORDER BY variation_url) as variations
FROM analytics.url_variations
GROUP BY property, canonical_url
HAVING COUNT(DISTINCT variation_url) > 1
ORDER BY COUNT(DISTINCT variation_url) DESC, SUM(occurrences) DESC;

-- View for recent variations (last 30 days)
CREATE OR REPLACE VIEW analytics.vw_recent_url_variations AS
SELECT
    property,
    canonical_url,
    variation_url,
    variation_type,
    occurrences,
    first_seen,
    last_seen,
    EXTRACT(EPOCH FROM (last_seen - first_seen)) / 86400 as days_active
FROM analytics.url_variations
WHERE last_seen >= CURRENT_TIMESTAMP - INTERVAL '30 days'
ORDER BY last_seen DESC, occurrences DESC;

-- View for variation type summary by property
CREATE OR REPLACE VIEW analytics.vw_url_variation_summary AS
SELECT
    property,
    variation_type,
    COUNT(*) as variation_count,
    SUM(occurrences) as total_occurrences,
    COUNT(DISTINCT canonical_url) as affected_urls,
    MIN(first_seen) as first_seen,
    MAX(last_seen) as last_seen
FROM analytics.url_variations
GROUP BY property, variation_type
ORDER BY property, total_occurrences DESC;

-- View for high-impact variations (many occurrences)
CREATE OR REPLACE VIEW analytics.vw_high_impact_url_variations AS
SELECT
    property,
    canonical_url,
    variation_url,
    variation_type,
    occurrences,
    first_seen,
    last_seen,
    ROUND(occurrences::NUMERIC / NULLIF(EXTRACT(EPOCH FROM (last_seen - first_seen)) / 86400, 0), 2) as avg_occurrences_per_day
FROM analytics.url_variations
WHERE occurrences >= 10
ORDER BY occurrences DESC, last_seen DESC;

-- Function to update last_seen timestamp
CREATE OR REPLACE FUNCTION analytics.update_url_variation_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update timestamp
DROP TRIGGER IF EXISTS trg_url_variations_update ON analytics.url_variations;
CREATE TRIGGER trg_url_variations_update
    BEFORE UPDATE ON analytics.url_variations
    FOR EACH ROW
    EXECUTE FUNCTION analytics.update_url_variation_timestamp();

-- Function to clean old variations (optional maintenance)
CREATE OR REPLACE FUNCTION analytics.cleanup_old_url_variations(days_threshold INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM analytics.url_variations
    WHERE last_seen < CURRENT_TIMESTAMP - (days_threshold || ' days')::INTERVAL
    AND occurrences < 5;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Comments for documentation
COMMENT ON TABLE analytics.url_variations IS 'Tracks URL variations to identify consolidation opportunities';
COMMENT ON COLUMN analytics.url_variations.property IS 'Property identifier (e.g., sc-domain:example.com)';
COMMENT ON COLUMN analytics.url_variations.canonical_url IS 'Normalized canonical URL without tracking parameters';
COMMENT ON COLUMN analytics.url_variations.variation_url IS 'Original URL with variations (tracking params, fragments, etc.)';
COMMENT ON COLUMN analytics.url_variations.variation_type IS 'Type of variation: query_param, fragment, trailing_slash, case, protocol, other';
COMMENT ON COLUMN analytics.url_variations.occurrences IS 'Number of times this variation has been observed';

COMMENT ON VIEW analytics.vw_url_consolidation_candidates IS 'URLs with multiple variations that may need consolidation';
COMMENT ON VIEW analytics.vw_recent_url_variations IS 'URL variations observed in the last 30 days';
COMMENT ON VIEW analytics.vw_url_variation_summary IS 'Summary of variation types by property';
COMMENT ON VIEW analytics.vw_high_impact_url_variations IS 'Variations with high occurrence counts';

COMMENT ON FUNCTION analytics.cleanup_old_url_variations IS 'Removes old URL variations with low occurrence counts (maintenance function)';

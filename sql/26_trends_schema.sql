-- Google Trends Schema
-- Stores trends data for keyword analysis and correlation with GSC performance

CREATE SCHEMA IF NOT EXISTS trends;

-- =============================================
-- TABLES
-- =============================================

-- Stores daily interest scores for keywords
CREATE TABLE IF NOT EXISTS trends.keyword_interest (
    id SERIAL PRIMARY KEY,
    property VARCHAR(255) NOT NULL,
    keyword VARCHAR(500) NOT NULL,
    date DATE NOT NULL,
    interest_score INTEGER, -- 0-100 scale from Google Trends
    is_partial BOOLEAN DEFAULT FALSE, -- True for incomplete/current week data
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(property, keyword, date)
);

-- Stores related queries discovered through trends
CREATE TABLE IF NOT EXISTS trends.related_queries (
    id SERIAL PRIMARY KEY,
    property VARCHAR(255) NOT NULL,
    keyword VARCHAR(500) NOT NULL,
    related_query VARCHAR(500) NOT NULL,
    query_type VARCHAR(50) NOT NULL, -- 'rising' or 'top'
    score INTEGER, -- Relative score/percentage
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(property, keyword, related_query, query_type, collected_at)
);

-- Tracks collection runs for monitoring and debugging
CREATE TABLE IF NOT EXISTS trends.collection_runs (
    id SERIAL PRIMARY KEY,
    property VARCHAR(255) NOT NULL,
    keywords_collected INTEGER DEFAULT 0,
    keywords_failed INTEGER DEFAULT 0,
    related_queries_collected INTEGER DEFAULT 0,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'running', -- 'running', 'completed', 'failed'
    error_message TEXT
);

-- =============================================
-- INDEXES
-- =============================================

-- For querying trends by property and keyword
CREATE INDEX IF NOT EXISTS idx_trends_property_keyword
    ON trends.keyword_interest(property, keyword);

-- For time-series queries
CREATE INDEX IF NOT EXISTS idx_trends_date
    ON trends.keyword_interest(date DESC);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_trends_property_date
    ON trends.keyword_interest(property, date DESC);

-- For related queries lookups
CREATE INDEX IF NOT EXISTS idx_related_property
    ON trends.related_queries(property, keyword);

CREATE INDEX IF NOT EXISTS idx_related_type
    ON trends.related_queries(query_type);

-- For collection run monitoring
CREATE INDEX IF NOT EXISTS idx_collection_runs_property
    ON trends.collection_runs(property, started_at DESC);

-- =============================================
-- VIEWS
-- =============================================

-- View: Recent trends performance for correlation with GSC
CREATE OR REPLACE VIEW trends.vw_keyword_trends_30d AS
SELECT
    property,
    keyword,
    AVG(interest_score) as avg_interest,
    MAX(interest_score) as peak_interest,
    MIN(interest_score) as min_interest,
    STDDEV(interest_score) as interest_volatility,
    COUNT(*) as data_points,
    MAX(date) as latest_date
FROM trends.keyword_interest
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
    AND is_partial = FALSE
GROUP BY property, keyword
HAVING COUNT(*) >= 7; -- At least a week of data

-- View: Rising related queries for opportunity identification
CREATE OR REPLACE VIEW trends.vw_rising_opportunities AS
SELECT
    property,
    keyword,
    related_query,
    score,
    collected_at
FROM trends.related_queries
WHERE query_type = 'rising'
    AND collected_at >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY score DESC NULLS LAST;

-- View: Collection health monitoring
CREATE OR REPLACE VIEW trends.vw_collection_health AS
SELECT
    property,
    COUNT(*) as total_runs,
    SUM(keywords_collected) as total_keywords_collected,
    SUM(keywords_failed) as total_keywords_failed,
    MAX(completed_at) as last_successful_run,
    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration_seconds
FROM trends.collection_runs
WHERE status = 'completed'
    AND started_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY property;

-- =============================================
-- PERMISSIONS
-- =============================================

-- Grant permissions to gsc_user
GRANT ALL PRIVILEGES ON SCHEMA trends TO gsc_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA trends TO gsc_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA trends TO gsc_user;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA trends
    GRANT ALL PRIVILEGES ON TABLES TO gsc_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA trends
    GRANT ALL PRIVILEGES ON SEQUENCES TO gsc_user;

-- =============================================
-- STATISTICS
-- =============================================

-- Update table statistics
ANALYZE trends.keyword_interest;
ANALYZE trends.related_queries;
ANALYZE trends.collection_runs;

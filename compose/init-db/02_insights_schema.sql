-- GSC Insights Engine Schema
-- Phase 2: GA4, Content Metadata, and Insights tables

SET search_path TO gsc, public;

-- =============================================
-- GA4 INTEGRATION
-- =============================================

-- GA4 Daily Behavior Data
CREATE TABLE IF NOT EXISTS gsc.ga4_daily_behavior (
    date DATE NOT NULL,
    page_path TEXT NOT NULL,
    source_medium VARCHAR(200),
    ga_sessions INTEGER DEFAULT 0,
    ga_engaged_sessions INTEGER DEFAULT 0,
    ga_engagement_rate NUMERIC(10,4) DEFAULT 0,
    ga_conversions INTEGER DEFAULT 0,
    ga_bounce_rate NUMERIC(10,4) DEFAULT 0,
    ga_avg_session_duration NUMERIC(10,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date, page_path, source_medium)
);

CREATE INDEX idx_ga4_date ON gsc.ga4_daily_behavior(date DESC);
CREATE INDEX idx_ga4_page_path ON gsc.ga4_daily_behavior(page_path);
CREATE INDEX idx_ga4_date_page ON gsc.ga4_daily_behavior(date DESC, page_path);

-- =============================================
-- CONTENT METADATA
-- =============================================

-- Content Metadata
CREATE TABLE IF NOT EXISTS gsc.content_metadata (
    page_path TEXT PRIMARY KEY,
    property VARCHAR(500) NOT NULL,
    last_modified_date TIMESTAMP,
    publish_date DATE,
    author VARCHAR(200),
    word_count INTEGER,
    semantic_topic VARCHAR(200),
    content_type VARCHAR(50),
    is_indexable BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_content_page_path ON gsc.content_metadata(page_path);
CREATE INDEX idx_content_property ON gsc.content_metadata(property);
CREATE INDEX idx_content_modified ON gsc.content_metadata(last_modified_date DESC);

-- =============================================
-- INSIGHTS TABLE
-- =============================================

-- Insights table (canonical model from plan)
CREATE TABLE IF NOT EXISTS gsc.insights (
    id VARCHAR(64) PRIMARY KEY,
    generated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    property VARCHAR(500) NOT NULL,
    entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('page', 'query', 'directory', 'property')),
    entity_id TEXT NOT NULL,
    category VARCHAR(20) NOT NULL CHECK (category IN ('risk', 'opportunity', 'trend', 'diagnosis')),
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    severity VARCHAR(10) NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
    confidence NUMERIC(3,2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    metrics JSONB NOT NULL,
    window_days INTEGER NOT NULL,
    source VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'investigating', 'diagnosed', 'actioned', 'resolved')),
    linked_insight_id VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (linked_insight_id) REFERENCES gsc.insights(id) ON DELETE SET NULL
);

CREATE INDEX idx_insights_generated_at ON gsc.insights(generated_at DESC);
CREATE INDEX idx_insights_property ON gsc.insights(property);
CREATE INDEX idx_insights_entity ON gsc.insights(entity_type, entity_id);
CREATE INDEX idx_insights_category ON gsc.insights(category);
CREATE INDEX idx_insights_status ON gsc.insights(status);
CREATE INDEX idx_insights_severity ON gsc.insights(severity DESC);
CREATE INDEX idx_insights_source ON gsc.insights(source);
CREATE INDEX idx_insights_linked ON gsc.insights(linked_insight_id) WHERE linked_insight_id IS NOT NULL;

-- =============================================
-- UPDATE TRIGGERS
-- =============================================

-- Update triggers for new tables
CREATE TRIGGER update_ga4_daily_behavior_updated_at 
    BEFORE UPDATE ON gsc.ga4_daily_behavior
    FOR EACH ROW EXECUTE FUNCTION gsc.update_updated_at_column();

CREATE TRIGGER update_content_metadata_updated_at 
    BEFORE UPDATE ON gsc.content_metadata
    FOR EACH ROW EXECUTE FUNCTION gsc.update_updated_at_column();

CREATE TRIGGER update_insights_updated_at 
    BEFORE UPDATE ON gsc.insights
    FOR EACH ROW EXECUTE FUNCTION gsc.update_updated_at_column();

-- =============================================
-- PERMISSIONS
-- =============================================

-- Grant permissions
GRANT ALL PRIVILEGES ON gsc.ga4_daily_behavior TO gsc_user;
GRANT ALL PRIVILEGES ON gsc.content_metadata TO gsc_user;
GRANT ALL PRIVILEGES ON gsc.insights TO gsc_user;

-- =============================================
-- MOCK DATA FOR DEVELOPMENT/TESTING
-- =============================================

-- Insert mock data for development/testing
INSERT INTO gsc.content_metadata (page_path, property, last_modified_date, publish_date, word_count, semantic_topic)
VALUES 
    ('/page1', 'https://example.com/', NOW() - INTERVAL '2 days', CURRENT_DATE - 7, 1500, 'SEO Best Practices'),
    ('/page2', 'https://example.com/', NOW() - INTERVAL '30 days', CURRENT_DATE - 60, 2200, 'Technical SEO')
ON CONFLICT (page_path) DO NOTHING;

-- =============================================
-- STATISTICS
-- =============================================

-- Update table statistics
ANALYZE gsc.ga4_daily_behavior;
ANALYZE gsc.content_metadata;
ANALYZE gsc.insights;

-- =============================================
-- INSIGHTS TABLE FOR UNIFIED INSIGHT ENGINE
-- =============================================
-- This table is the canonical storage for insights generated
-- by the InsightEngine (insights_core/engine.py)
-- 
-- Schema matches: insights_core/models.py::Insight
-- Used by: InsightRepository, all Detectors, MCP tools, API
--
-- Migration safety: Idempotent (IF NOT EXISTS), can run multiple times

SET search_path TO gsc, public;

-- =============================================
-- CREATE UPDATE FUNCTION (IF NOT EXISTS)
-- =============================================

CREATE OR REPLACE FUNCTION gsc.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- MAIN TABLE
-- =============================================

CREATE TABLE IF NOT EXISTS gsc.insights (
    -- Primary identification (deterministic hash prevents duplicates)
    id VARCHAR(64) PRIMARY KEY,
    generated_at TIMESTAMP NOT NULL,
    
    -- Entity identification (what this insight is about)
    property VARCHAR(500) NOT NULL,
    entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN ('page', 'query', 'directory', 'property')),
    entity_id TEXT NOT NULL,
    
    -- Insight classification
    category VARCHAR(50) NOT NULL CHECK (category IN ('risk', 'opportunity', 'trend', 'diagnosis')),
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
    confidence NUMERIC(3,2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    
    -- Context and metrics (JSONB for flexible schema + indexing)
    metrics JSONB NOT NULL,
    window_days INTEGER NOT NULL CHECK (window_days > 0 AND window_days <= 365),
    source VARCHAR(100) NOT NULL,
    
    -- Workflow tracking
    status VARCHAR(50) NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'investigating', 'diagnosed', 'actioned', 'resolved')),
    linked_insight_id VARCHAR(64),
    
    -- Audit timestamps (UTC, no timezone to avoid conversion issues)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key to self for diagnosis->risk linking
    CONSTRAINT fk_linked_insight 
        FOREIGN KEY (linked_insight_id) 
        REFERENCES gsc.insights(id) 
        ON DELETE SET NULL
);

-- =============================================
-- INDEXES FOR QUERY PERFORMANCE
-- =============================================

-- Single-column indexes (for filtering)
CREATE INDEX IF NOT EXISTS idx_insights_property ON gsc.insights(property);
CREATE INDEX IF NOT EXISTS idx_insights_category ON gsc.insights(category);
CREATE INDEX IF NOT EXISTS idx_insights_status ON gsc.insights(status);
CREATE INDEX IF NOT EXISTS idx_insights_generated_at ON gsc.insights(generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_insights_entity_type ON gsc.insights(entity_type);
CREATE INDEX IF NOT EXISTS idx_insights_severity ON gsc.insights(severity);
CREATE INDEX IF NOT EXISTS idx_insights_source ON gsc.insights(source);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_insights_property_category_status 
    ON gsc.insights(property, category, status);

CREATE INDEX IF NOT EXISTS idx_insights_property_generated 
    ON gsc.insights(property, generated_at DESC);

CREATE INDEX IF NOT EXISTS idx_insights_entity 
    ON gsc.insights(entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_insights_category_severity_status 
    ON gsc.insights(category, severity, status);

CREATE INDEX IF NOT EXISTS idx_insights_status_generated 
    ON gsc.insights(status, generated_at DESC) 
    WHERE status IN ('new', 'diagnosed');

-- Partial index for linked insights (only where not null)
CREATE INDEX IF NOT EXISTS idx_insights_linked 
    ON gsc.insights(linked_insight_id) 
    WHERE linked_insight_id IS NOT NULL;

-- GIN index for JSONB metrics searching
CREATE INDEX IF NOT EXISTS idx_insights_metrics_gin 
    ON gsc.insights USING GIN(metrics);

-- =============================================
-- TRIGGERS
-- =============================================

-- Auto-update updated_at timestamp on any update
DROP TRIGGER IF EXISTS update_insights_updated_at ON gsc.insights;
CREATE TRIGGER update_insights_updated_at 
    BEFORE UPDATE ON gsc.insights
    FOR EACH ROW 
    EXECUTE FUNCTION gsc.update_updated_at_column();

-- =============================================
-- VALIDATION FUNCTION
-- =============================================

CREATE OR REPLACE FUNCTION gsc.validate_insights_table()
RETURNS TABLE(
    check_name TEXT,
    check_status TEXT,
    check_value TEXT,
    check_message TEXT
) AS $$
BEGIN
    -- Check 1: Total insights count
    RETURN QUERY
    SELECT 
        'total_insights'::TEXT,
        'INFO'::TEXT,
        COUNT(*)::TEXT,
        'Total insights in table'::TEXT
    FROM gsc.insights;
    
    -- Check 2: Insights by category
    RETURN QUERY
    SELECT 
        'insights_by_category'::TEXT,
        'INFO'::TEXT,
        category || ': ' || COUNT(*)::TEXT,
        'Distribution by category'::TEXT
    FROM gsc.insights
    GROUP BY category;
    
    -- Check 3: Insights by status
    RETURN QUERY
    SELECT 
        'insights_by_status'::TEXT,
        'INFO'::TEXT,
        status || ': ' || COUNT(*)::TEXT,
        'Distribution by status'::TEXT
    FROM gsc.insights
    GROUP BY status;
    
    -- Check 4: Recent insights (last 24 hours)
    RETURN QUERY
    SELECT 
        'recent_insights'::TEXT,
        CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'WARN' END::TEXT,
        COUNT(*)::TEXT,
        'Insights generated in last 24 hours'::TEXT
    FROM gsc.insights
    WHERE generated_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours';
    
    -- Check 5: Orphaned linked insights (broken foreign keys shouldn't exist, but check anyway)
    RETURN QUERY
    SELECT 
        'orphaned_links'::TEXT,
        CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END::TEXT,
        COUNT(*)::TEXT,
        'Insights with linked_insight_id pointing to non-existent ID'::TEXT
    FROM gsc.insights i
    WHERE i.linked_insight_id IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM gsc.insights l WHERE l.id = i.linked_insight_id
        );
    
    -- Check 6: Invalid confidence values (should be caught by CHECK constraint)
    RETURN QUERY
    SELECT 
        'invalid_confidence'::TEXT,
        CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END::TEXT,
        COUNT(*)::TEXT,
        'Insights with confidence outside 0.0-1.0 range'::TEXT
    FROM gsc.insights
    WHERE confidence < 0 OR confidence > 1;
    
    -- Check 7: Table indexes exist
    RETURN QUERY
    SELECT 
        'indexes_exist'::TEXT,
        CASE WHEN COUNT(*) >= 10 THEN 'PASS' ELSE 'FAIL' END::TEXT,
        COUNT(*)::TEXT,
        'Number of indexes on insights table (expect 10+)'::TEXT
    FROM pg_indexes
    WHERE schemaname = 'gsc' AND tablename = 'insights';
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- HELPER VIEWS
-- =============================================

-- View: Active insights requiring action
CREATE OR REPLACE VIEW gsc.vw_insights_actionable AS
SELECT 
    id,
    generated_at,
    property,
    entity_type,
    entity_id,
    category,
    title,
    description,
    severity,
    confidence,
    metrics,
    source,
    status,
    linked_insight_id,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - generated_at))/3600 as hours_old
FROM gsc.insights
WHERE status IN ('new', 'diagnosed')
ORDER BY 
    CASE severity 
        WHEN 'high' THEN 1 
        WHEN 'medium' THEN 2 
        WHEN 'low' THEN 3 
    END,
    generated_at DESC;

-- View: Insight summary statistics by property
CREATE OR REPLACE VIEW gsc.vw_insights_stats AS
SELECT 
    property,
    category,
    severity,
    status,
    COUNT(*) as insight_count,
    AVG(confidence) as avg_confidence,
    MIN(generated_at) as first_generated,
    MAX(generated_at) as last_generated,
    COUNT(DISTINCT entity_id) as unique_entities
FROM gsc.insights
GROUP BY property, category, severity, status;

-- =============================================
-- PERMISSIONS
-- =============================================

GRANT SELECT, INSERT, UPDATE, DELETE ON gsc.insights TO gsc_user;
GRANT SELECT ON gsc.vw_insights_actionable TO gsc_user;
GRANT SELECT ON gsc.vw_insights_stats TO gsc_user;
GRANT EXECUTE ON FUNCTION gsc.validate_insights_table() TO gsc_user;

-- =============================================
-- DOCUMENTATION
-- =============================================

COMMENT ON TABLE gsc.insights IS 
'Canonical insight storage for Unified Insight Engine. Stores anomalies, diagnoses, opportunities, and trends detected by InsightEngine detectors.';

COMMENT ON COLUMN gsc.insights.id IS 
'Deterministic SHA256 hash from property|entity_type|entity_id|category|source|window_days. Prevents duplicates.';

COMMENT ON COLUMN gsc.insights.entity_type IS 
'Type of entity: page (URL), query (search term), directory (path prefix), property (entire site)';

COMMENT ON COLUMN gsc.insights.category IS 
'Insight type: risk (problem detected), opportunity (growth potential), trend (pattern analysis), diagnosis (root cause)';

COMMENT ON COLUMN gsc.insights.metrics IS 
'JSONB snapshot of metrics that triggered this insight. Flexible schema per detector. Example: {"gsc_clicks": 1250, "gsc_clicks_change": -45.2}';

COMMENT ON COLUMN gsc.insights.linked_insight_id IS 
'Links diagnosis insights to their originating risk/opportunity insights for traceability';

COMMENT ON COLUMN gsc.insights.status IS 
'Workflow state: new (just created), investigating (being analyzed), diagnosed (root cause found), actioned (fix deployed), resolved (verified fixed)';

-- =============================================
-- INITIALIZATION
-- =============================================

-- Analyze table for query optimization (safe even if empty)
ANALYZE gsc.insights;

-- Success notification
DO $$ 
BEGIN 
    RAISE NOTICE '✓ Insights table created successfully';
    RAISE NOTICE '✓ Run: SELECT * FROM gsc.validate_insights_table() to verify';
    RAISE NOTICE '✓ Table schema matches insights_core/models.py::Insight';
END $$;

-- =============================================
-- ACTIONS SCHEMA
-- =============================================
-- Purpose: Track actionable tasks generated from insights
-- Dependencies: 11_insights_table.sql (gsc.insights)
-- Phase: Tier 1, Item #1 (Actions Layer with Priority Scoring)

SET search_path TO gsc, public;

-- =============================================
-- ACTIONS TABLE
-- =============================================
-- Transforms insights into trackable, prioritized to-do items
-- Supports workflow: insight → action → execution → outcome

CREATE TABLE IF NOT EXISTS gsc.actions (
    -- Identity
    action_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    insight_id VARCHAR(64) REFERENCES gsc.insights(id) ON DELETE CASCADE,

    -- Classification
    action_type VARCHAR(100) NOT NULL,
    -- Action types:
    --   - rewrite_meta: Update meta description/title
    --   - improve_content: Enhance content quality
    --   - fix_technical: Fix technical SEO issues
    --   - add_links: Add internal/external links
    --   - create_content: Create new content
    --   - prune_content: Remove/consolidate pages
    --   - improve_ux: UX/design improvements
    --   - optimize_speed: Performance optimization

    category VARCHAR(50) NOT NULL,
    -- Categories: content, technical, ux, performance, strategy

    -- Details
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    page_path TEXT NOT NULL,
    property VARCHAR(500) NOT NULL,

    -- Prioritization
    priority_score DECIMAL(5,2) NOT NULL DEFAULT 0,
    -- Calculated as: (impact_score * effort_inverse * urgency_multiplier)
    -- Range: 0-100 (higher = more priority)

    impact_score INT NOT NULL CHECK (impact_score BETWEEN 1 AND 10),
    -- 1-3: Low impact
    -- 4-7: Medium impact
    -- 8-10: High impact

    effort_score INT NOT NULL CHECK (effort_score BETWEEN 1 AND 10),
    -- 1-3: Low effort (<1 hour)
    -- 4-7: Medium effort (1-8 hours)
    -- 8-10: High effort (1+ days)

    urgency VARCHAR(20) NOT NULL DEFAULT 'medium',
    -- low, medium, high, critical

    estimated_hours DECIMAL(5,1),
    -- Estimated implementation time

    -- Workflow
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    -- pending, in_progress, blocked, completed, cancelled, deferred

    owner VARCHAR(100),
    -- Person/team responsible

    assigned_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    due_date TIMESTAMP,

    -- Implementation tracking
    implementation_notes TEXT,
    blockers TEXT,
    related_actions UUID[],
    -- Array of related action IDs

    -- Outcome measurement
    outcome VARCHAR(50),
    -- improved, no_change, worsened, unknown

    outcome_confidence DECIMAL(3,2),
    -- 0.0 to 1.0 confidence in outcome

    metrics_before JSONB,
    -- Store baseline metrics: {clicks: 100, position: 5.0, ctr: 3.5}

    metrics_after JSONB,
    -- Store post-implementation metrics

    lift_pct DECIMAL(6,2),
    -- Percentage change in primary metric

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100) DEFAULT 'system',

    -- Constraints
    CONSTRAINT valid_status CHECK (
        status IN ('pending', 'in_progress', 'blocked', 'completed', 'cancelled', 'deferred')
    ),
    CONSTRAINT valid_urgency CHECK (
        urgency IN ('low', 'medium', 'high', 'critical')
    ),
    CONSTRAINT valid_outcome CHECK (
        outcome IS NULL OR outcome IN ('improved', 'no_change', 'worsened', 'unknown')
    ),
    CONSTRAINT completed_requires_dates CHECK (
        status != 'completed' OR (started_at IS NOT NULL AND completed_at IS NOT NULL)
    )
);

-- =============================================
-- INDEXES
-- =============================================
-- Performance optimization for common queries

CREATE INDEX IF NOT EXISTS idx_actions_insight_id ON gsc.actions(insight_id);
CREATE INDEX IF NOT EXISTS idx_actions_status ON gsc.actions(status);
CREATE INDEX IF NOT EXISTS idx_actions_priority ON gsc.actions(priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_actions_owner ON gsc.actions(owner) WHERE owner IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_actions_page_path ON gsc.actions(page_path);
CREATE INDEX IF NOT EXISTS idx_actions_property ON gsc.actions(property);
CREATE INDEX IF NOT EXISTS idx_actions_created ON gsc.actions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_actions_due_date ON gsc.actions(due_date) WHERE due_date IS NOT NULL;

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_actions_status_priority ON gsc.actions(status, priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_actions_property_status ON gsc.actions(property, status);

-- JSONB indexes for metric analysis
CREATE INDEX IF NOT EXISTS idx_actions_metrics_before ON gsc.actions USING gin(metrics_before);
CREATE INDEX IF NOT EXISTS idx_actions_metrics_after ON gsc.actions USING gin(metrics_after);

-- =============================================
-- TRIGGER: Update timestamp
-- =============================================
CREATE OR REPLACE FUNCTION gsc.update_actions_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;

    -- Auto-set assigned_at when owner is set
    IF NEW.owner IS NOT NULL AND OLD.owner IS NULL THEN
        NEW.assigned_at = CURRENT_TIMESTAMP;
    END IF;

    -- Auto-set started_at when status changes to in_progress
    IF NEW.status = 'in_progress' AND OLD.status != 'in_progress' THEN
        NEW.started_at = COALESCE(NEW.started_at, CURRENT_TIMESTAMP);
    END IF;

    -- Auto-set completed_at when status changes to completed
    IF NEW.status = 'completed' AND OLD.status != 'completed' THEN
        NEW.completed_at = COALESCE(NEW.completed_at, CURRENT_TIMESTAMP);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER actions_update_timestamp
    BEFORE UPDATE ON gsc.actions
    FOR EACH ROW
    EXECUTE FUNCTION gsc.update_actions_timestamp();

-- =============================================
-- FUNCTION: Calculate Priority Score
-- =============================================
-- Formula: (impact / 10) * (10 / effort) * urgency_multiplier * 100
-- Result: 0-100 scale (higher = more priority)

CREATE OR REPLACE FUNCTION gsc.calculate_priority_score(
    p_impact INT,
    p_effort INT,
    p_urgency VARCHAR
) RETURNS DECIMAL(5,2) AS $$
DECLARE
    urgency_multiplier DECIMAL(3,2);
BEGIN
    -- Validate inputs
    IF p_impact < 1 OR p_impact > 10 THEN
        RAISE EXCEPTION 'Impact must be between 1 and 10';
    END IF;
    IF p_effort < 1 OR p_effort > 10 THEN
        RAISE EXCEPTION 'Effort must be between 1 and 10';
    END IF;

    -- Map urgency to multiplier
    urgency_multiplier := CASE p_urgency
        WHEN 'critical' THEN 2.0
        WHEN 'high' THEN 1.5
        WHEN 'medium' THEN 1.0
        WHEN 'low' THEN 0.7
        ELSE 1.0
    END;

    -- Calculate priority: (impact/10) * (10/effort) * urgency * 100
    -- Examples:
    --   High impact (9), Low effort (2), Critical urgency = 90.0
    --   Medium impact (5), Medium effort (5), Medium urgency = 50.0
    --   Low impact (3), High effort (8), Low urgency = 2.6

    RETURN ROUND(
        (p_impact::DECIMAL / 10.0) *
        (10.0 / p_effort::DECIMAL) *
        urgency_multiplier *
        100.0,
        2
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =============================================
-- TRIGGER: Auto-calculate priority on insert/update
-- =============================================
CREATE OR REPLACE FUNCTION gsc.auto_calculate_priority()
RETURNS TRIGGER AS $$
BEGIN
    NEW.priority_score := gsc.calculate_priority_score(
        NEW.impact_score,
        NEW.effort_score,
        NEW.urgency
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER actions_auto_priority
    BEFORE INSERT OR UPDATE OF impact_score, effort_score, urgency ON gsc.actions
    FOR EACH ROW
    EXECUTE FUNCTION gsc.auto_calculate_priority();

-- =============================================
-- VIEW: Top Priority Actions
-- =============================================
CREATE OR REPLACE VIEW gsc.vw_top_priority_actions AS
SELECT
    action_id,
    title,
    action_type,
    category,
    page_path,
    property,
    priority_score,
    impact_score,
    effort_score,
    urgency,
    status,
    owner,
    due_date,
    created_at,
    CASE
        WHEN due_date IS NOT NULL AND due_date < CURRENT_TIMESTAMP THEN true
        ELSE false
    END AS is_overdue,
    CASE
        WHEN priority_score >= 75 THEN 'critical'
        WHEN priority_score >= 50 THEN 'high'
        WHEN priority_score >= 25 THEN 'medium'
        ELSE 'low'
    END AS priority_label
FROM gsc.actions
WHERE status IN ('pending', 'in_progress', 'blocked')
ORDER BY priority_score DESC, created_at ASC;

COMMENT ON VIEW gsc.vw_top_priority_actions IS 'Top priority pending actions ordered by priority score';

-- =============================================
-- VIEW: Action Performance Analytics
-- =============================================
CREATE OR REPLACE VIEW gsc.vw_action_performance AS
SELECT
    action_id,
    action_type,
    category,
    page_path,
    property,
    status,
    outcome,
    lift_pct,
    impact_score,
    effort_score,
    priority_score,
    estimated_hours,
    EXTRACT(EPOCH FROM (completed_at - started_at)) / 3600.0 AS actual_hours,
    metrics_before,
    metrics_after,
    completed_at
FROM gsc.actions
WHERE status = 'completed'
    AND outcome IS NOT NULL
    AND metrics_before IS NOT NULL
    AND metrics_after IS NOT NULL;

COMMENT ON VIEW gsc.vw_action_performance IS 'Completed actions with performance metrics for learning';

-- =============================================
-- COMMENTS
-- =============================================
COMMENT ON TABLE gsc.actions IS 'Actionable tasks generated from insights with priority scoring';
COMMENT ON COLUMN gsc.actions.priority_score IS 'Calculated priority (0-100): higher = more important';
COMMENT ON COLUMN gsc.actions.impact_score IS 'Expected impact (1-10): business value of completing this action';
COMMENT ON COLUMN gsc.actions.effort_score IS 'Required effort (1-10): time/complexity to complete';
COMMENT ON COLUMN gsc.actions.metrics_before IS 'Baseline metrics before implementation (JSON)';
COMMENT ON COLUMN gsc.actions.metrics_after IS 'Metrics after implementation (JSON)';
COMMENT ON COLUMN gsc.actions.lift_pct IS 'Percentage change in primary metric (positive = improvement)';

-- =============================================
-- VERIFICATION
-- =============================================
DO $$
BEGIN
    RAISE NOTICE 'Actions schema created successfully ✓';
    RAISE NOTICE 'Table: gsc.actions';
    RAISE NOTICE 'Views: vw_top_priority_actions, vw_action_performance';
    RAISE NOTICE 'Functions: calculate_priority_score()';
END $$;

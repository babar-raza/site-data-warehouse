-- GSC Actions Schema
-- Actionable tasks generated from insights
-- Must run after 02_insights_schema.sql

SET search_path TO gsc, public;

-- =============================================
-- ACTIONS TABLE
-- =============================================

CREATE TABLE IF NOT EXISTS gsc.actions (
    id VARCHAR(64) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    insight_id VARCHAR(64) REFERENCES gsc.insights(id) ON DELETE CASCADE,
    property VARCHAR(500) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    estimated_effort VARCHAR(20),
    estimated_impact TEXT,
    assigned_to VARCHAR(100),
    due_date TIMESTAMP,
    completed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- Additional columns for action generator
    instructions JSONB DEFAULT '[]'::jsonb,
    effort VARCHAR(50),
    outcome JSONB
);

-- =============================================
-- INDEXES
-- =============================================

CREATE INDEX IF NOT EXISTS idx_actions_insight_id ON gsc.actions(insight_id);
CREATE INDEX IF NOT EXISTS idx_actions_property ON gsc.actions(property);
CREATE INDEX IF NOT EXISTS idx_actions_status ON gsc.actions(status);
CREATE INDEX IF NOT EXISTS idx_actions_priority ON gsc.actions(priority);
CREATE INDEX IF NOT EXISTS idx_actions_action_type ON gsc.actions(action_type);
CREATE INDEX IF NOT EXISTS idx_actions_assigned_to ON gsc.actions(assigned_to);
CREATE INDEX IF NOT EXISTS idx_actions_created_at ON gsc.actions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_actions_due_date ON gsc.actions(due_date);
CREATE INDEX IF NOT EXISTS idx_actions_property_status ON gsc.actions(property, status);
CREATE INDEX IF NOT EXISTS idx_actions_property_status_priority ON gsc.actions(property, status, priority);
CREATE INDEX IF NOT EXISTS idx_actions_property_type_status ON gsc.actions(property, action_type, status);
CREATE INDEX IF NOT EXISTS idx_actions_status_created ON gsc.actions(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_actions_property_completed ON gsc.actions(property, completed_at DESC) WHERE completed_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_actions_property_created ON gsc.actions(property, created_at DESC);

-- =============================================
-- UPDATE TRIGGER
-- =============================================

CREATE TRIGGER update_actions_updated_at
    BEFORE UPDATE ON gsc.actions
    FOR EACH ROW EXECUTE FUNCTION gsc.update_updated_at_column();

-- =============================================
-- PERMISSIONS
-- =============================================

GRANT ALL PRIVILEGES ON gsc.actions TO gsc_user;

-- =============================================
-- COMMENTS
-- =============================================

COMMENT ON TABLE gsc.actions IS 'Actionable tasks generated from insights';
COMMENT ON COLUMN gsc.actions.id IS 'Unique action identifier';
COMMENT ON COLUMN gsc.actions.insight_id IS 'Reference to the insight that triggered this action';
COMMENT ON COLUMN gsc.actions.property IS 'GSC property this action applies to';
COMMENT ON COLUMN gsc.actions.action_type IS 'Category of action';
COMMENT ON COLUMN gsc.actions.priority IS 'Action priority (critical, high, medium, low)';
COMMENT ON COLUMN gsc.actions.estimated_effort IS 'Estimated effort required';
COMMENT ON COLUMN gsc.actions.instructions IS 'JSON array of step-by-step instructions';
COMMENT ON COLUMN gsc.actions.effort IS 'Effort level for action generator compatibility';
COMMENT ON COLUMN gsc.actions.outcome IS 'JSON with results after completion';

-- Verification
DO $$
BEGIN
    RAISE NOTICE 'Actions schema created successfully';
END $$;

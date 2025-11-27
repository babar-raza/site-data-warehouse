-- Actions Schema
-- Table for storing actionable tasks generated from insights

CREATE TABLE IF NOT EXISTS gsc.actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    insight_id UUID REFERENCES gsc.insights(id) ON DELETE CASCADE,
    property TEXT NOT NULL,
    action_type TEXT NOT NULL, -- 'content_update', 'technical', 'content_restructure', 'investigation', 'general'
    title TEXT NOT NULL,
    description TEXT,
    instructions JSONB, -- Array of step-by-step instructions
    priority TEXT NOT NULL CHECK (priority IN ('critical', 'high', 'medium', 'low')),
    effort TEXT NOT NULL CHECK (effort IN ('low', 'medium', 'high')),
    estimated_impact JSONB, -- Expected metrics improvements
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
    assigned_to TEXT, -- Username or email of person assigned
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    outcome JSONB, -- Results after action completion
    metadata JSONB -- Additional context
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_actions_insight_id ON gsc.actions(insight_id);
CREATE INDEX IF NOT EXISTS idx_actions_property ON gsc.actions(property);
CREATE INDEX IF NOT EXISTS idx_actions_status ON gsc.actions(status);
CREATE INDEX IF NOT EXISTS idx_actions_priority ON gsc.actions(priority);
CREATE INDEX IF NOT EXISTS idx_actions_action_type ON gsc.actions(action_type);
CREATE INDEX IF NOT EXISTS idx_actions_assigned_to ON gsc.actions(assigned_to);
CREATE INDEX IF NOT EXISTS idx_actions_created_at ON gsc.actions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_actions_property_status ON gsc.actions(property, status);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_actions_property_status_priority
    ON gsc.actions(property, status, priority);

-- Comments for documentation
COMMENT ON TABLE gsc.actions IS 'Actionable tasks generated from insights';
COMMENT ON COLUMN gsc.actions.id IS 'Unique action identifier';
COMMENT ON COLUMN gsc.actions.insight_id IS 'Reference to the insight that triggered this action';
COMMENT ON COLUMN gsc.actions.property IS 'GSC property this action applies to';
COMMENT ON COLUMN gsc.actions.action_type IS 'Category of action (content_update, technical, etc.)';
COMMENT ON COLUMN gsc.actions.title IS 'Action title';
COMMENT ON COLUMN gsc.actions.description IS 'Detailed description of the action';
COMMENT ON COLUMN gsc.actions.instructions IS 'JSON array of step-by-step instructions';
COMMENT ON COLUMN gsc.actions.priority IS 'Action priority (critical, high, medium, low)';
COMMENT ON COLUMN gsc.actions.effort IS 'Estimated effort required (low, medium, high)';
COMMENT ON COLUMN gsc.actions.estimated_impact IS 'JSON with expected improvements (traffic_potential, ranking_improvement, etc.)';
COMMENT ON COLUMN gsc.actions.status IS 'Current status (pending, in_progress, completed, cancelled)';
COMMENT ON COLUMN gsc.actions.assigned_to IS 'Person assigned to this action';
COMMENT ON COLUMN gsc.actions.created_at IS 'When the action was created';
COMMENT ON COLUMN gsc.actions.started_at IS 'When work on the action began';
COMMENT ON COLUMN gsc.actions.completed_at IS 'When the action was completed';
COMMENT ON COLUMN gsc.actions.outcome IS 'JSON with actual results after completion';
COMMENT ON COLUMN gsc.actions.metadata IS 'Additional context data';

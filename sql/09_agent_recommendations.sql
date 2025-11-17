-- Agent Recommendations Table
-- Stores actionable recommendations from strategist agent

SET search_path TO gsc, public;

-- Drop existing table if needed
DROP TABLE IF EXISTS gsc.agent_recommendations CASCADE;

-- Create agent_recommendations table
CREATE TABLE gsc.agent_recommendations (
    id SERIAL PRIMARY KEY,
    diagnosis_id INTEGER REFERENCES gsc.agent_diagnoses(id),
    agent_name VARCHAR(50) NOT NULL,
    recommendation_type VARCHAR(50) NOT NULL,
    action_items JSONB NOT NULL,
    priority INTEGER NOT NULL CHECK (priority >= 1 AND priority <= 5),
    estimated_effort_hours INTEGER NOT NULL CHECK (estimated_effort_hours > 0),
    expected_impact VARCHAR(20) NOT NULL CHECK (expected_impact IN ('low', 'medium', 'high')),
    expected_traffic_lift_pct NUMERIC(5,2) CHECK (expected_traffic_lift_pct >= 0 AND expected_traffic_lift_pct <= 100),
    recommended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    implemented BOOLEAN DEFAULT FALSE,
    implemented_at TIMESTAMP,
    actual_impact JSONB,
    notes TEXT,
    metadata JSONB
);

-- Create indexes
CREATE INDEX idx_agent_recommendations_diagnosis ON gsc.agent_recommendations(diagnosis_id);
CREATE INDEX idx_agent_recommendations_agent ON gsc.agent_recommendations(agent_name);
CREATE INDEX idx_agent_recommendations_type ON gsc.agent_recommendations(recommendation_type);
CREATE INDEX idx_agent_recommendations_priority ON gsc.agent_recommendations(priority ASC);
CREATE INDEX idx_agent_recommendations_impact ON gsc.agent_recommendations(expected_impact);
CREATE INDEX idx_agent_recommendations_recommended ON gsc.agent_recommendations(recommended_at DESC);
CREATE INDEX idx_agent_recommendations_implemented ON gsc.agent_recommendations(implemented, implemented_at);
CREATE INDEX idx_agent_recommendations_action_items ON gsc.agent_recommendations USING GIN(action_items);

-- Grant permissions
GRANT ALL PRIVILEGES ON gsc.agent_recommendations TO gsc_user;
GRANT ALL PRIVILEGES ON SEQUENCE gsc.agent_recommendations_id_seq TO gsc_user;

-- Add comments
COMMENT ON TABLE gsc.agent_recommendations IS 'Stores actionable recommendations from strategist agent';
COMMENT ON COLUMN gsc.agent_recommendations.recommendation_type IS 'Type of recommendation (content_optimization, internal_linking, technical_fixes, etc.)';
COMMENT ON COLUMN gsc.agent_recommendations.priority IS 'Priority level 1-5 (1=highest)';
COMMENT ON COLUMN gsc.agent_recommendations.expected_impact IS 'Expected impact level (low, medium, high)';
COMMENT ON COLUMN gsc.agent_recommendations.expected_traffic_lift_pct IS 'Expected traffic lift percentage';
COMMENT ON COLUMN gsc.agent_recommendations.action_items IS 'Detailed action items and implementation steps';

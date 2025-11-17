-- Agent Executions Table
-- Stores execution records and outcomes from dispatcher agent

SET search_path TO gsc, public;

-- Drop existing table if needed
DROP TABLE IF EXISTS gsc.agent_executions CASCADE;

-- Create agent_executions table
CREATE TABLE gsc.agent_executions (
    id SERIAL PRIMARY KEY,
    recommendation_id INTEGER REFERENCES gsc.agent_recommendations(id),
    agent_name VARCHAR(50) NOT NULL DEFAULT 'dispatcher',
    execution_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'rolled_back')),
    execution_details JSONB NOT NULL DEFAULT '{}',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    validation_result JSONB DEFAULT '{}',
    outcome_metrics JSONB DEFAULT '{}',
    rollback_details JSONB,
    error_message TEXT,
    dry_run BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}'
);

-- Create indexes
CREATE INDEX idx_agent_executions_recommendation ON gsc.agent_executions(recommendation_id);
CREATE INDEX idx_agent_executions_agent ON gsc.agent_executions(agent_name);
CREATE INDEX idx_agent_executions_type ON gsc.agent_executions(execution_type);
CREATE INDEX idx_agent_executions_status ON gsc.agent_executions(status);
CREATE INDEX idx_agent_executions_started ON gsc.agent_executions(started_at DESC);
CREATE INDEX idx_agent_executions_completed ON gsc.agent_executions(completed_at DESC);
CREATE INDEX idx_agent_executions_details ON gsc.agent_executions USING GIN(execution_details);
CREATE INDEX idx_agent_executions_metrics ON gsc.agent_executions USING GIN(outcome_metrics);

-- Grant permissions
GRANT ALL PRIVILEGES ON gsc.agent_executions TO gsc_user;
GRANT ALL PRIVILEGES ON SEQUENCE gsc.agent_executions_id_seq TO gsc_user;

-- Add comments
COMMENT ON TABLE gsc.agent_executions IS 'Stores execution records and outcomes from dispatcher agent';
COMMENT ON COLUMN gsc.agent_executions.execution_type IS 'Type of execution (content_update, pr_creation, notification, etc.)';
COMMENT ON COLUMN gsc.agent_executions.status IS 'Execution status: pending, in_progress, completed, failed, rolled_back';
COMMENT ON COLUMN gsc.agent_executions.execution_details IS 'Detailed execution information and parameters';
COMMENT ON COLUMN gsc.agent_executions.validation_result IS 'Validation results after execution';
COMMENT ON COLUMN gsc.agent_executions.outcome_metrics IS 'Performance metrics collected over monitoring period';

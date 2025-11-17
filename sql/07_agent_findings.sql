-- Agent Findings Table
-- Stores findings from various agents (watcher, diagnostician, etc.)

SET search_path TO gsc, public;

-- Drop existing table if needed
DROP TABLE IF EXISTS gsc.agent_findings CASCADE;

-- Create agent_findings table
CREATE TABLE gsc.agent_findings (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(50) NOT NULL,
    finding_type VARCHAR(50) NOT NULL,  -- 'anomaly', 'trend', 'opportunity', 'alert'
    severity VARCHAR(20) NOT NULL,       -- 'critical', 'warning', 'info'
    affected_pages JSONB,
    metrics JSONB,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP,
    notes TEXT,
    metadata JSONB
);

-- Create indexes
CREATE INDEX idx_agent_findings_agent ON gsc.agent_findings(agent_name);
CREATE INDEX idx_agent_findings_type ON gsc.agent_findings(finding_type);
CREATE INDEX idx_agent_findings_severity ON gsc.agent_findings(severity);
CREATE INDEX idx_agent_findings_detected ON gsc.agent_findings(detected_at DESC);
CREATE INDEX idx_agent_findings_processed ON gsc.agent_findings(processed, detected_at DESC);
CREATE INDEX idx_agent_findings_metrics ON gsc.agent_findings USING GIN(metrics);

-- Grant permissions
GRANT ALL PRIVILEGES ON gsc.agent_findings TO gsc_user;
GRANT ALL PRIVILEGES ON SEQUENCE gsc.agent_findings_id_seq TO gsc_user;

-- Add comments
COMMENT ON TABLE gsc.agent_findings IS 'Stores findings from various monitoring agents';
COMMENT ON COLUMN gsc.agent_findings.finding_type IS 'Type: anomaly, trend, opportunity, alert';
COMMENT ON COLUMN gsc.agent_findings.severity IS 'Severity: critical, warning, info';
COMMENT ON COLUMN gsc.agent_findings.affected_pages IS 'Array of affected page URLs';
COMMENT ON COLUMN gsc.agent_findings.metrics IS 'Detailed metrics and context about the finding';

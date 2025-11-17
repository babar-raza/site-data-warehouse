-- Agent Diagnoses Table
-- Stores root cause analysis and diagnoses from diagnostician agent

SET search_path TO gsc, public;

-- Drop existing table if needed
DROP TABLE IF EXISTS gsc.agent_diagnoses CASCADE;

-- Create agent_diagnoses table
CREATE TABLE gsc.agent_diagnoses (
    id SERIAL PRIMARY KEY,
    finding_id INTEGER REFERENCES gsc.agent_findings(id),
    agent_name VARCHAR(50) NOT NULL,
    root_cause VARCHAR(100) NOT NULL,
    confidence_score NUMERIC(3,2) NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
    supporting_evidence JSONB,
    related_pages JSONB,
    diagnosed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE,
    notes TEXT,
    metadata JSONB
);

-- Create indexes
CREATE INDEX idx_agent_diagnoses_finding ON gsc.agent_diagnoses(finding_id);
CREATE INDEX idx_agent_diagnoses_agent ON gsc.agent_diagnoses(agent_name);
CREATE INDEX idx_agent_diagnoses_root_cause ON gsc.agent_diagnoses(root_cause);
CREATE INDEX idx_agent_diagnoses_confidence ON gsc.agent_diagnoses(confidence_score DESC);
CREATE INDEX idx_agent_diagnoses_diagnosed ON gsc.agent_diagnoses(diagnosed_at DESC);
CREATE INDEX idx_agent_diagnoses_evidence ON gsc.agent_diagnoses USING GIN(supporting_evidence);

-- Grant permissions
GRANT ALL PRIVILEGES ON gsc.agent_diagnoses TO gsc_user;
GRANT ALL PRIVILEGES ON SEQUENCE gsc.agent_diagnoses_id_seq TO gsc_user;

-- Add comments
COMMENT ON TABLE gsc.agent_diagnoses IS 'Stores root cause analysis and diagnoses from diagnostician agent';
COMMENT ON COLUMN gsc.agent_diagnoses.root_cause IS 'Identified root cause category';
COMMENT ON COLUMN gsc.agent_diagnoses.confidence_score IS 'Confidence score between 0 and 1';
COMMENT ON COLUMN gsc.agent_diagnoses.supporting_evidence IS 'Evidence supporting the diagnosis';
COMMENT ON COLUMN gsc.agent_diagnoses.related_pages IS 'Array of related page URLs';

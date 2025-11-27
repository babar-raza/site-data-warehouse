-- =====================================================
-- Multi-Agent Orchestration Schema
-- =====================================================
-- Purpose: Track LangGraph workflows and agent decisions
-- Phase: 4
-- Dependencies: uuid-ossp extension
-- =====================================================

-- Create schema
CREATE SCHEMA IF NOT EXISTS orchestration;

-- =====================================================
-- WORKFLOWS TABLE
-- =====================================================
-- Track multi-agent workflow executions
CREATE TABLE orchestration.workflows (
    workflow_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_name TEXT NOT NULL,
    workflow_type TEXT NOT NULL, -- daily_analysis, emergency_response, optimization, validation

    -- Trigger
    trigger_type TEXT, -- scheduled, event, manual
    trigger_event JSONB, -- Event that triggered the workflow

    -- State
    state JSONB, -- Current workflow state (LangGraph state)
    status TEXT DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),

    -- Context
    property TEXT,
    page_path TEXT,
    metadata JSONB,

    -- Timing
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INT,

    -- Results
    result JSONB, -- Final workflow result
    actions_taken JSONB[], -- Array of actions taken
    recommendations JSONB[], -- Array of recommendations

    -- Error handling
    error_message TEXT,
    error_details JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_workflows_status ON orchestration.workflows(status);
CREATE INDEX idx_workflows_type ON orchestration.workflows(workflow_type);
CREATE INDEX idx_workflows_started ON orchestration.workflows(started_at DESC);
CREATE INDEX idx_workflows_property ON orchestration.workflows(property);

COMMENT ON TABLE orchestration.workflows IS 'Multi-agent workflow execution tracking';


-- =====================================================
-- WORKFLOW STEPS TABLE
-- =====================================================
-- Track individual steps within a workflow
CREATE TABLE orchestration.workflow_steps (
    step_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id UUID REFERENCES orchestration.workflows(workflow_id) ON DELETE CASCADE,

    step_name TEXT NOT NULL,
    step_type TEXT NOT NULL, -- agent_analysis, decision, action, validation
    agent_name TEXT, -- Which agent executed this step

    -- Execution
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INT,
    status TEXT DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'skipped')),

    -- Input/Output
    input_data JSONB,
    output_data JSONB,

    -- Error handling
    error_message TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_workflow_steps_workflow ON orchestration.workflow_steps(workflow_id);
CREATE INDEX idx_workflow_steps_status ON orchestration.workflow_steps(status);
CREATE INDEX idx_workflow_steps_agent ON orchestration.workflow_steps(agent_name);

COMMENT ON TABLE orchestration.workflow_steps IS 'Individual steps within workflows';


-- =====================================================
-- AGENT DECISIONS TABLE
-- =====================================================
-- Track decisions made by AI agents
CREATE TABLE orchestration.agent_decisions (
    decision_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id UUID REFERENCES orchestration.workflows(workflow_id) ON DELETE CASCADE,
    step_id UUID REFERENCES orchestration.workflow_steps(step_id) ON DELETE CASCADE,

    agent_name TEXT NOT NULL, -- serp_analyst, performance_agent, content_optimizer, etc.
    decision_type TEXT NOT NULL, -- recommend_action, validate_intervention, analyze_trend

    -- Decision
    decision TEXT NOT NULL, -- The actual decision made
    reasoning TEXT, -- LLM-generated explanation
    confidence FLOAT CHECK (confidence BETWEEN 0 AND 1), -- Confidence score 0-1

    -- Recommendations
    recommendations JSONB, -- Array of specific recommendations
    priority TEXT CHECK (priority IN ('low', 'medium', 'high', 'critical')),

    -- Context
    analysis_data JSONB, -- Data analyzed to make decision
    property TEXT,
    page_path TEXT,

    -- Outcome tracking
    was_executed BOOLEAN DEFAULT false,
    execution_result JSONB,
    outcome_validation JSONB, -- Did the decision lead to positive outcomes?

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_agent_decisions_workflow ON orchestration.agent_decisions(workflow_id);
CREATE INDEX idx_agent_decisions_agent ON orchestration.agent_decisions(agent_name);
CREATE INDEX idx_agent_decisions_type ON orchestration.agent_decisions(decision_type);
CREATE INDEX idx_agent_decisions_executed ON orchestration.agent_decisions(was_executed);
CREATE INDEX idx_agent_decisions_property ON orchestration.agent_decisions(property);

COMMENT ON TABLE orchestration.agent_decisions IS 'AI agent decisions with reasoning and confidence';


-- =====================================================
-- AGENT PERFORMANCE TABLE
-- =====================================================
-- Track agent performance metrics
CREATE TABLE orchestration.agent_performance (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name TEXT NOT NULL,

    -- Time window
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Performance metrics
    total_decisions INT DEFAULT 0,
    executed_decisions INT DEFAULT 0,
    successful_outcomes INT DEFAULT 0,
    failed_outcomes INT DEFAULT 0,

    avg_confidence FLOAT,
    avg_execution_time_ms FLOAT,

    -- Accuracy metrics
    true_positives INT DEFAULT 0, -- Correct positive recommendations
    false_positives INT DEFAULT 0, -- Incorrect recommendations
    true_negatives INT DEFAULT 0, -- Correctly avoided bad recommendations
    false_negatives INT DEFAULT 0, -- Missed opportunities

    precision FLOAT, -- TP / (TP + FP)
    recall FLOAT, -- TP / (TP + FN)
    f1_score FLOAT, -- 2 * (precision * recall) / (precision + recall)

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(agent_name, period_start, period_end)
);

CREATE INDEX idx_agent_performance_agent ON orchestration.agent_performance(agent_name);
CREATE INDEX idx_agent_performance_period ON orchestration.agent_performance(period_start DESC);

COMMENT ON TABLE orchestration.agent_performance IS 'Agent performance metrics and accuracy tracking';


-- =====================================================
-- AGENT FEEDBACK TABLE
-- =====================================================
-- Human feedback on agent decisions (for continuous improvement)
CREATE TABLE orchestration.agent_feedback (
    feedback_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    decision_id UUID REFERENCES orchestration.agent_decisions(decision_id),

    -- Feedback
    feedback_type TEXT CHECK (feedback_type IN ('approve', 'reject', 'modify', 'flag')),
    feedback_text TEXT,
    provided_by TEXT NOT NULL,

    -- Impact
    was_helpful BOOLEAN,
    alternative_recommendation TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_agent_feedback_decision ON orchestration.agent_feedback(decision_id);
CREATE INDEX idx_agent_feedback_type ON orchestration.agent_feedback(feedback_type);

COMMENT ON TABLE orchestration.agent_feedback IS 'Human feedback on agent decisions for learning';


-- =====================================================
-- AUTOMATION QUEUE TABLE
-- =====================================================
-- Queue for automated actions approved by agents
CREATE TABLE orchestration.automation_queue (
    queue_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id UUID REFERENCES orchestration.workflows(workflow_id),
    decision_id UUID REFERENCES orchestration.agent_decisions(decision_id),

    action_type TEXT NOT NULL, -- create_pr, update_content, fix_cwv, etc.
    action_config JSONB NOT NULL,

    -- Priority
    priority INT DEFAULT 5, -- 1 (highest) to 10 (lowest)
    estimated_impact TEXT, -- high, medium, low

    -- Scheduling
    scheduled_for TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    execute_after TIMESTAMP,

    -- Execution
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'executing', 'completed', 'failed', 'cancelled')),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    result JSONB,
    error_message TEXT,

    -- Approval (if required)
    requires_approval BOOLEAN DEFAULT false,
    approved_by TEXT,
    approved_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_automation_queue_status ON orchestration.automation_queue(status, priority DESC)
    WHERE status IN ('pending', 'failed');
CREATE INDEX idx_automation_queue_scheduled ON orchestration.automation_queue(scheduled_for);
CREATE INDEX idx_automation_queue_workflow ON orchestration.automation_queue(workflow_id);

COMMENT ON TABLE orchestration.automation_queue IS 'Queue for automated actions from agent decisions';


-- =====================================================
-- VIEWS
-- =====================================================

-- Active workflows
CREATE OR REPLACE VIEW orchestration.vw_active_workflows AS
SELECT
    w.workflow_id,
    w.workflow_name,
    w.workflow_type,
    w.property,
    w.status,
    w.started_at,
    EXTRACT(EPOCH FROM (NOW() - w.started_at)) / 60 as running_minutes,
    COUNT(ws.step_id) as total_steps,
    COUNT(ws.step_id) FILTER (WHERE ws.status = 'completed') as completed_steps,
    COUNT(ws.step_id) FILTER (WHERE ws.status = 'failed') as failed_steps
FROM orchestration.workflows w
LEFT JOIN orchestration.workflow_steps ws ON w.workflow_id = ws.workflow_id
WHERE w.status = 'running'
GROUP BY w.workflow_id, w.workflow_name, w.workflow_type, w.property, w.status, w.started_at
ORDER BY w.started_at DESC;

COMMENT ON VIEW orchestration.vw_active_workflows IS 'Currently running workflows with progress';


-- Agent decision summary
CREATE OR REPLACE VIEW orchestration.vw_agent_decision_summary AS
SELECT
    ad.agent_name,
    ad.decision_type,
    COUNT(*) as total_decisions,
    COUNT(*) FILTER (WHERE ad.was_executed = true) as executed_count,
    ROUND(AVG(ad.confidence), 3) as avg_confidence,
    COUNT(*) FILTER (WHERE ad.priority = 'critical') as critical_count,
    COUNT(*) FILTER (WHERE ad.priority = 'high') as high_count,
    MAX(ad.created_at) as last_decision_at
FROM orchestration.agent_decisions ad
WHERE ad.created_at >= NOW() - INTERVAL '7 days'
GROUP BY ad.agent_name, ad.decision_type
ORDER BY total_decisions DESC;

COMMENT ON VIEW orchestration.vw_agent_decision_summary IS 'Summary of agent decisions in last 7 days';


-- Automation queue status
CREATE OR REPLACE VIEW orchestration.vw_automation_queue_status AS
SELECT
    status,
    action_type,
    COUNT(*) as count,
    AVG(priority) as avg_priority,
    MIN(scheduled_for) as next_execution,
    COUNT(*) FILTER (WHERE requires_approval = true AND approved_at IS NULL) as pending_approval
FROM orchestration.automation_queue
WHERE status IN ('pending', 'executing')
GROUP BY status, action_type
ORDER BY status, count DESC;

COMMENT ON VIEW orchestration.vw_automation_queue_status IS 'Current automation queue status';


-- Workflow success rate
CREATE OR REPLACE VIEW orchestration.vw_workflow_success_rate AS
SELECT
    workflow_type,
    COUNT(*) as total_runs,
    COUNT(*) FILTER (WHERE status = 'completed') as successful_runs,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_runs,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE status = 'completed') / NULLIF(COUNT(*), 0),
        2
    ) as success_rate_pct,
    AVG(duration_seconds) FILTER (WHERE status = 'completed') as avg_duration_seconds,
    MAX(started_at) as last_run_at
FROM orchestration.workflows
WHERE started_at >= NOW() - INTERVAL '30 days'
GROUP BY workflow_type
ORDER BY total_runs DESC;

COMMENT ON VIEW orchestration.vw_workflow_success_rate IS 'Workflow success rates over last 30 days';


-- =====================================================
-- FUNCTIONS
-- =====================================================

-- Start a workflow
CREATE OR REPLACE FUNCTION orchestration.start_workflow(
    p_workflow_name TEXT,
    p_workflow_type TEXT,
    p_trigger_type TEXT DEFAULT 'manual',
    p_trigger_event JSONB DEFAULT NULL,
    p_property TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_workflow_id UUID;
BEGIN
    INSERT INTO orchestration.workflows (
        workflow_name,
        workflow_type,
        trigger_type,
        trigger_event,
        property,
        metadata,
        status,
        state
    ) VALUES (
        p_workflow_name,
        p_workflow_type,
        p_trigger_type,
        p_trigger_event,
        p_property,
        p_metadata,
        'running',
        '{}'::JSONB
    ) RETURNING workflow_id INTO v_workflow_id;

    RETURN v_workflow_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION orchestration.start_workflow IS 'Initialize a new workflow execution';


-- Complete a workflow
CREATE OR REPLACE FUNCTION orchestration.complete_workflow(
    p_workflow_id UUID,
    p_status TEXT,
    p_result JSONB DEFAULT NULL,
    p_error_message TEXT DEFAULT NULL
) RETURNS VOID AS $$
DECLARE
    v_started_at TIMESTAMP;
BEGIN
    SELECT started_at INTO v_started_at
    FROM orchestration.workflows
    WHERE workflow_id = p_workflow_id;

    UPDATE orchestration.workflows
    SET
        status = p_status,
        completed_at = NOW(),
        duration_seconds = EXTRACT(EPOCH FROM (NOW() - v_started_at)),
        result = p_result,
        error_message = p_error_message
    WHERE workflow_id = p_workflow_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION orchestration.complete_workflow IS 'Mark workflow as completed or failed';


-- Add workflow step
CREATE OR REPLACE FUNCTION orchestration.add_workflow_step(
    p_workflow_id UUID,
    p_step_name TEXT,
    p_step_type TEXT,
    p_agent_name TEXT DEFAULT NULL,
    p_input_data JSONB DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_step_id UUID;
BEGIN
    INSERT INTO orchestration.workflow_steps (
        workflow_id,
        step_name,
        step_type,
        agent_name,
        input_data,
        status
    ) VALUES (
        p_workflow_id,
        p_step_name,
        p_step_type,
        p_agent_name,
        p_input_data,
        'running'
    ) RETURNING step_id INTO v_step_id;

    RETURN v_step_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION orchestration.add_workflow_step IS 'Add a step to a running workflow';


-- Complete workflow step
CREATE OR REPLACE FUNCTION orchestration.complete_workflow_step(
    p_step_id UUID,
    p_status TEXT,
    p_output_data JSONB DEFAULT NULL,
    p_error_message TEXT DEFAULT NULL
) RETURNS VOID AS $$
DECLARE
    v_started_at TIMESTAMP;
BEGIN
    SELECT started_at INTO v_started_at
    FROM orchestration.workflow_steps
    WHERE step_id = p_step_id;

    UPDATE orchestration.workflow_steps
    SET
        status = p_status,
        completed_at = NOW(),
        duration_ms = EXTRACT(EPOCH FROM (NOW() - v_started_at)) * 1000,
        output_data = p_output_data,
        error_message = p_error_message
    WHERE step_id = p_step_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION orchestration.complete_workflow_step IS 'Mark workflow step as completed or failed';


-- Record agent decision
CREATE OR REPLACE FUNCTION orchestration.record_agent_decision(
    p_workflow_id UUID,
    p_step_id UUID,
    p_agent_name TEXT,
    p_decision_type TEXT,
    p_decision TEXT,
    p_reasoning TEXT,
    p_confidence FLOAT,
    p_recommendations JSONB DEFAULT NULL,
    p_priority TEXT DEFAULT 'medium',
    p_property TEXT DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_decision_id UUID;
BEGIN
    INSERT INTO orchestration.agent_decisions (
        workflow_id,
        step_id,
        agent_name,
        decision_type,
        decision,
        reasoning,
        confidence,
        recommendations,
        priority,
        property
    ) VALUES (
        p_workflow_id,
        p_step_id,
        p_agent_name,
        p_decision_type,
        p_decision,
        p_reasoning,
        p_confidence,
        p_recommendations,
        p_priority,
        p_property
    ) RETURNING decision_id INTO v_decision_id;

    RETURN v_decision_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION orchestration.record_agent_decision IS 'Record an agent decision with reasoning';


-- Queue automated action
CREATE OR REPLACE FUNCTION orchestration.queue_action(
    p_workflow_id UUID,
    p_decision_id UUID,
    p_action_type TEXT,
    p_action_config JSONB,
    p_priority INT DEFAULT 5,
    p_requires_approval BOOLEAN DEFAULT false
) RETURNS UUID AS $$
DECLARE
    v_queue_id UUID;
BEGIN
    INSERT INTO orchestration.automation_queue (
        workflow_id,
        decision_id,
        action_type,
        action_config,
        priority,
        requires_approval,
        status
    ) VALUES (
        p_workflow_id,
        p_decision_id,
        p_action_type,
        p_action_config,
        p_priority,
        p_requires_approval,
        'pending'
    ) RETURNING queue_id INTO v_queue_id;

    RETURN v_queue_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION orchestration.queue_action IS 'Add automated action to execution queue';


-- =====================================================
-- TRIGGERS
-- =====================================================

-- Update agent performance on decision execution
CREATE OR REPLACE FUNCTION orchestration.update_agent_performance()
RETURNS TRIGGER AS $$
BEGIN
    -- This would be populated by a scheduled job
    -- that aggregates agent_decisions data
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =====================================================
-- GRANTS
-- =====================================================

GRANT USAGE ON SCHEMA orchestration TO gsc_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA orchestration TO gsc_user;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA orchestration TO gsc_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA orchestration TO gsc_user;


-- =====================================================
-- SAMPLE DATA
-- =====================================================

-- Example workflow (commented out)
/*
-- Start a daily analysis workflow
SELECT orchestration.start_workflow(
    'Daily SEO Analysis',
    'daily_analysis',
    'scheduled',
    '{"schedule": "daily", "time": "08:00"}'::JSONB,
    'https://blog.aspose.net',
    '{"scope": "full_property"}'::JSONB
);
*/

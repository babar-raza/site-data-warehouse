-- Actions Metrics Views
-- Views for Grafana dashboard queries
-- Created for TASKCARD-036: Actions Command Center Dashboard

-- Actions by Status
CREATE OR REPLACE VIEW gsc.vw_actions_by_status AS
SELECT
    property,
    status,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY property), 1) as percentage
FROM gsc.actions
GROUP BY property, status;

COMMENT ON VIEW gsc.vw_actions_by_status IS 'Action count and percentage by status for each property';

-- Actions by Priority
CREATE OR REPLACE VIEW gsc.vw_actions_by_priority AS
SELECT
    property,
    priority,
    COUNT(*) as count,
    COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
    COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress_count,
    COUNT(*) FILTER (WHERE status = 'completed') as completed_count,
    COUNT(*) FILTER (WHERE status IN ('cancelled', 'dismissed')) as cancelled_count
FROM gsc.actions
GROUP BY property, priority;

COMMENT ON VIEW gsc.vw_actions_by_priority IS 'Action count breakdown by priority and status';

-- Actions Timeline
CREATE OR REPLACE VIEW gsc.vw_actions_timeline AS
SELECT
    property,
    DATE_TRUNC('day', created_at)::date as date,
    COUNT(*) as actions_created,
    COUNT(*) FILTER (WHERE status = 'completed') as actions_completed,
    COUNT(*) FILTER (WHERE status = 'in_progress') as actions_in_progress,
    COUNT(*) FILTER (WHERE status = 'pending') as actions_pending
FROM gsc.actions
WHERE created_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY property, DATE_TRUNC('day', created_at)::date
ORDER BY date DESC;

COMMENT ON VIEW gsc.vw_actions_timeline IS 'Daily action creation and completion timeline for last 90 days';

-- Completion Rate by Week
CREATE OR REPLACE VIEW gsc.vw_actions_completion_rate AS
SELECT
    property,
    DATE_TRUNC('week', created_at)::date as week,
    COUNT(*) as total_created,
    COUNT(*) FILTER (WHERE status = 'completed') as completed,
    COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress,
    COUNT(*) FILTER (WHERE status IN ('cancelled', 'dismissed')) as cancelled,
    COUNT(*) FILTER (WHERE status = 'pending') as pending,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'completed') / NULLIF(COUNT(*), 0), 1) as completion_rate_pct,
    AVG(EXTRACT(EPOCH FROM (completed_at - created_at))/86400) FILTER (WHERE status = 'completed') as avg_days_to_complete,
    MIN(EXTRACT(EPOCH FROM (completed_at - created_at))/86400) FILTER (WHERE status = 'completed') as min_days_to_complete,
    MAX(EXTRACT(EPOCH FROM (completed_at - created_at))/86400) FILTER (WHERE status = 'completed') as max_days_to_complete
FROM gsc.actions
WHERE created_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY property, DATE_TRUNC('week', created_at)::date
ORDER BY week DESC;

COMMENT ON VIEW gsc.vw_actions_completion_rate IS 'Weekly action completion metrics and statistics';

-- Actions by Action Type
CREATE OR REPLACE VIEW gsc.vw_actions_by_type AS
SELECT
    property,
    action_type,
    COUNT(*) as total_count,
    COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
    COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress_count,
    COUNT(*) FILTER (WHERE status = 'completed') as completed_count,
    AVG(EXTRACT(EPOCH FROM (completed_at - created_at))/86400) FILTER (WHERE status = 'completed') as avg_days_to_complete,
    MIN(created_at) as first_action_date,
    MAX(created_at) as latest_action_date
FROM gsc.actions
GROUP BY property, action_type
ORDER BY total_count DESC;

COMMENT ON VIEW gsc.vw_actions_by_type IS 'Action metrics grouped by action type';

-- Pending Actions Summary
CREATE OR REPLACE VIEW gsc.vw_pending_actions_summary AS
SELECT
    property,
    COUNT(*) as total_pending,
    COUNT(*) FILTER (WHERE priority = 'critical') as critical_count,
    COUNT(*) FILTER (WHERE priority = 'high') as high_count,
    COUNT(*) FILTER (WHERE priority = 'medium') as medium_count,
    COUNT(*) FILTER (WHERE priority = 'low') as low_count,
    COUNT(*) FILTER (WHERE effort = 'low') as low_effort_count,
    COUNT(*) FILTER (WHERE effort = 'medium') as medium_effort_count,
    COUNT(*) FILTER (WHERE effort = 'high') as high_effort_count,
    MIN(created_at) as oldest_action_date,
    MAX(created_at) as newest_action_date,
    AVG(EXTRACT(DAY FROM (CURRENT_TIMESTAMP - created_at))) as avg_age_days,
    MAX(EXTRACT(DAY FROM (CURRENT_TIMESTAMP - created_at))) as max_age_days
FROM gsc.actions
WHERE status = 'pending'
GROUP BY property;

COMMENT ON VIEW gsc.vw_pending_actions_summary IS 'Summary of all pending actions by property';

-- Actions by Effort
CREATE OR REPLACE VIEW gsc.vw_actions_by_effort AS
SELECT
    property,
    effort,
    COUNT(*) as count,
    COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
    COUNT(*) FILTER (WHERE status = 'completed') as completed_count,
    AVG(EXTRACT(EPOCH FROM (completed_at - created_at))/86400) FILTER (WHERE status = 'completed') as avg_days_to_complete
FROM gsc.actions
GROUP BY property, effort
ORDER BY
    CASE effort
        WHEN 'low' THEN 1
        WHEN 'medium' THEN 2
        WHEN 'high' THEN 3
        ELSE 4
    END;

COMMENT ON VIEW gsc.vw_actions_by_effort IS 'Action metrics grouped by estimated effort level';

-- Actions with Estimated Impact
CREATE OR REPLACE VIEW gsc.vw_actions_impact_summary AS
SELECT
    property,
    action_type,
    priority,
    COUNT(*) as action_count,
    AVG((estimated_impact->>'traffic_impact')::numeric) FILTER (WHERE estimated_impact->>'traffic_impact' IS NOT NULL) as avg_traffic_impact,
    AVG((estimated_impact->>'ranking_impact')::numeric) FILTER (WHERE estimated_impact->>'ranking_impact' IS NOT NULL) as avg_ranking_impact,
    AVG((estimated_impact->>'conversion_impact')::numeric) FILTER (WHERE estimated_impact->>'conversion_impact' IS NOT NULL) as avg_conversion_impact
FROM gsc.actions
WHERE estimated_impact IS NOT NULL
GROUP BY property, action_type, priority;

COMMENT ON VIEW gsc.vw_actions_impact_summary IS 'Summary of actions with their estimated impacts';

-- Recent Activity Feed
CREATE OR REPLACE VIEW gsc.vw_actions_recent_activity AS
SELECT
    property,
    action_type,
    title,
    status,
    priority,
    effort,
    created_at,
    completed_at,
    EXTRACT(DAY FROM (COALESCE(completed_at, CURRENT_TIMESTAMP) - created_at)) as age_days
FROM gsc.actions
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
   OR completed_at >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY COALESCE(completed_at, created_at) DESC;

COMMENT ON VIEW gsc.vw_actions_recent_activity IS 'Recent action activity for activity feed displays';

-- Add indexes for dashboard performance
CREATE INDEX IF NOT EXISTS idx_actions_property_status ON gsc.actions(property, status);
CREATE INDEX IF NOT EXISTS idx_actions_property_created ON gsc.actions(property, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_actions_property_completed ON gsc.actions(property, completed_at DESC) WHERE completed_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_actions_priority ON gsc.actions(priority);
CREATE INDEX IF NOT EXISTS idx_actions_effort ON gsc.actions(effort);
CREATE INDEX IF NOT EXISTS idx_actions_action_type ON gsc.actions(action_type);
CREATE INDEX IF NOT EXISTS idx_actions_status_created ON gsc.actions(status, created_at DESC);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_actions_property_status_priority ON gsc.actions(property, status, priority);
CREATE INDEX IF NOT EXISTS idx_actions_property_type_status ON gsc.actions(property, action_type, status);

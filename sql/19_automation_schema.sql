-- =====================================================
-- Automation Schema (Auto-PR Generation)
-- =====================================================
-- Purpose: Track automated pull requests and deployments
-- Phase: 3
-- Dependencies: uuid-ossp extension
-- =====================================================

-- Create schema
CREATE SCHEMA IF NOT EXISTS automation;

-- =====================================================
-- PULL REQUESTS TABLE
-- =====================================================
-- Track automated pull requests
CREATE TABLE automation.pull_requests (
    pr_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Repository info
    repo_owner TEXT NOT NULL,
    repo_name TEXT NOT NULL,
    branch_name TEXT NOT NULL,

    -- PR details
    pr_number INT,  -- GitHub PR number (NULL until created)
    pr_url TEXT,  -- GitHub PR URL
    pr_title TEXT NOT NULL,
    pr_description TEXT,

    -- Status
    status TEXT DEFAULT 'created',  -- created, open, merged, closed, failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    merged_at TIMESTAMP,
    closed_at TIMESTAMP,

    -- Related data
    property TEXT,  -- Which property this PR is for
    recommendations JSONB,  -- Recommendations that triggered this PR
    files_changed INT DEFAULT 0,
    commits_count INT DEFAULT 0,

    -- Results
    deployment_url TEXT,  -- URL after deployment
    rollback_info JSONB,  -- Info for rollback if needed

    -- Metadata
    created_by_agent TEXT DEFAULT 'auto_pr_generator',
    labels TEXT[],

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_pr_repo ON automation.pull_requests(repo_owner, repo_name);
CREATE INDEX idx_pr_status ON automation.pull_requests(status);
CREATE INDEX idx_pr_created ON automation.pull_requests(created_at DESC);
CREATE INDEX idx_pr_property ON automation.pull_requests(property);
CREATE INDEX idx_pr_number ON automation.pull_requests(pr_number) WHERE pr_number IS NOT NULL;

-- Auto-update timestamp
CREATE TRIGGER update_pull_requests_updated_at
    BEFORE UPDATE ON automation.pull_requests
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE automation.pull_requests IS 'Track automated GitHub pull requests';
COMMENT ON COLUMN automation.pull_requests.status IS 'PR status: created, open, merged, closed, failed';
COMMENT ON COLUMN automation.pull_requests.recommendations IS 'Recommendations that triggered this PR';


-- =====================================================
-- FILE CHANGES TABLE
-- =====================================================
-- Track individual file changes in PRs
CREATE TABLE automation.file_changes (
    change_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pr_id UUID NOT NULL REFERENCES automation.pull_requests(pr_id) ON DELETE CASCADE,

    -- File info
    file_path TEXT NOT NULL,
    change_type TEXT NOT NULL,  -- created, modified, deleted

    -- Change details
    old_content TEXT,  -- Content before change
    new_content TEXT,  -- Content after change
    diff TEXT,  -- Unified diff

    -- Recommendation that triggered this change
    recommendation_type TEXT,  -- update_meta, add_schema, improve_content, etc.
    recommendation_data JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_file_changes_pr ON automation.file_changes(pr_id);
CREATE INDEX idx_file_changes_type ON automation.file_changes(change_type);
CREATE INDEX idx_file_changes_rec_type ON automation.file_changes(recommendation_type);

COMMENT ON TABLE automation.file_changes IS 'Individual file changes in automated PRs';


-- =====================================================
-- DEPLOYMENT HISTORY TABLE
-- =====================================================
-- Track deployments of automated changes
CREATE TABLE automation.deployments (
    deployment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pr_id UUID REFERENCES automation.pull_requests(pr_id),

    -- Deployment info
    environment TEXT NOT NULL,  -- production, staging, preview
    deployment_url TEXT,
    commit_sha TEXT,

    -- Status
    status TEXT DEFAULT 'pending',  -- pending, in_progress, success, failed
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    -- Results
    error_message TEXT,
    logs TEXT,

    -- Metadata
    deployed_by TEXT DEFAULT 'github_actions',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_deployments_pr ON automation.deployments(pr_id);
CREATE INDEX idx_deployments_status ON automation.deployments(status);
CREATE INDEX idx_deployments_env ON automation.deployments(environment);
CREATE INDEX idx_deployments_started ON automation.deployments(started_at DESC);

COMMENT ON TABLE automation.deployments IS 'Track deployments of automated changes';


-- =====================================================
-- ROLLBACKS TABLE
-- =====================================================
-- Track rollbacks of failed changes
CREATE TABLE automation.rollbacks (
    rollback_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pr_id UUID REFERENCES automation.pull_requests(pr_id),
    deployment_id UUID REFERENCES automation.deployments(deployment_id),

    -- Rollback details
    reason TEXT NOT NULL,
    rollback_commit_sha TEXT,
    rollback_pr_number INT,

    -- Status
    status TEXT DEFAULT 'initiated',  -- initiated, in_progress, completed, failed
    initiated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    -- Results
    success BOOLEAN,
    error_message TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_rollbacks_pr ON automation.rollbacks(pr_id);
CREATE INDEX idx_rollbacks_deployment ON automation.rollbacks(deployment_id);
CREATE INDEX idx_rollbacks_status ON automation.rollbacks(status);

COMMENT ON TABLE automation.rollbacks IS 'Track rollbacks of failed automated changes';


-- =====================================================
-- VIEWS
-- =====================================================

-- Active PRs summary
CREATE OR REPLACE VIEW automation.vw_active_prs AS
SELECT
    pr_id,
    repo_owner,
    repo_name,
    branch_name,
    pr_number,
    pr_url,
    pr_title,
    status,
    property,
    files_changed,
    created_at,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - created_at))/3600 as hours_open
FROM automation.pull_requests
WHERE status IN ('created', 'open')
ORDER BY created_at DESC;

COMMENT ON VIEW automation.vw_active_prs IS 'Currently active pull requests';


-- PR success rate by property
CREATE OR REPLACE VIEW automation.vw_pr_success_rate AS
SELECT
    property,
    COUNT(*) as total_prs,
    COUNT(*) FILTER (WHERE status = 'merged') as merged_count,
    COUNT(*) FILTER (WHERE status = 'closed') as closed_count,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_count,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'merged') /
          NULLIF(COUNT(*), 0), 2) as merge_rate_pct,
    AVG(EXTRACT(EPOCH FROM (merged_at - created_at))/3600) FILTER (WHERE status = 'merged') as avg_hours_to_merge
FROM automation.pull_requests
WHERE property IS NOT NULL
GROUP BY property;

COMMENT ON VIEW automation.vw_pr_success_rate IS 'PR success metrics by property';


-- Recent deployments
CREATE OR REPLACE VIEW automation.vw_recent_deployments AS
SELECT
    d.deployment_id,
    d.environment,
    d.status,
    d.deployment_url,
    d.started_at,
    d.completed_at,
    EXTRACT(EPOCH FROM (d.completed_at - d.started_at))/60 as duration_minutes,
    pr.repo_owner,
    pr.repo_name,
    pr.pr_number,
    pr.property
FROM automation.deployments d
LEFT JOIN automation.pull_requests pr ON d.pr_id = pr.pr_id
WHERE d.started_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
ORDER BY d.started_at DESC;

COMMENT ON VIEW automation.vw_recent_deployments IS 'Recent deployments in last 30 days';


-- Automation stats
CREATE OR REPLACE VIEW automation.vw_automation_stats AS
SELECT
    COUNT(DISTINCT pr_id) as total_prs,
    COUNT(DISTINCT pr_id) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '7 days') as prs_last_week,
    COUNT(DISTINCT pr_id) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '30 days') as prs_last_month,
    COUNT(DISTINCT pr_id) FILTER (WHERE status = 'merged') as total_merged,
    SUM(files_changed) as total_files_changed,
    COUNT(DISTINCT property) as properties_automated
FROM automation.pull_requests;

COMMENT ON VIEW automation.vw_automation_stats IS 'Overall automation statistics';


-- =====================================================
-- FUNCTIONS
-- =====================================================

-- Function to get PR status summary
CREATE OR REPLACE FUNCTION automation.get_pr_summary(
    p_pr_id UUID
) RETURNS TABLE (
    pr_number INT,
    status TEXT,
    files_changed INT,
    recommendations_count INT,
    has_deployment BOOLEAN,
    deployment_status TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pr.pr_number,
        pr.status,
        pr.files_changed,
        jsonb_array_length(COALESCE(pr.recommendations, '[]'::jsonb))::INT,
        EXISTS(SELECT 1 FROM automation.deployments WHERE pr_id = p_pr_id),
        (SELECT status FROM automation.deployments WHERE pr_id = p_pr_id ORDER BY started_at DESC LIMIT 1)
    FROM automation.pull_requests pr
    WHERE pr.pr_id = p_pr_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION automation.get_pr_summary IS 'Get summary for a pull request';


-- Function to track PR lifecycle duration
CREATE OR REPLACE FUNCTION automation.get_pr_lifecycle_duration(
    p_property TEXT DEFAULT NULL,
    p_days_back INT DEFAULT 90
) RETURNS TABLE (
    avg_hours_to_create FLOAT,
    avg_hours_to_merge FLOAT,
    avg_hours_to_deploy FLOAT,
    total_prs_analyzed BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        AVG(EXTRACT(EPOCH FROM (pr.created_at - pr.created_at))/3600) as avg_hours_to_create,  -- Always 0, just placeholder
        AVG(EXTRACT(EPOCH FROM (pr.merged_at - pr.created_at))/3600) FILTER (WHERE pr.status = 'merged'),
        AVG(EXTRACT(EPOCH FROM (d.completed_at - pr.created_at))/3600) FILTER (WHERE d.status = 'success'),
        COUNT(DISTINCT pr.pr_id)
    FROM automation.pull_requests pr
    LEFT JOIN automation.deployments d ON pr.pr_id = d.pr_id
    WHERE pr.created_at >= CURRENT_DATE - p_days_back
        AND (p_property IS NULL OR pr.property = p_property);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION automation.get_pr_lifecycle_duration IS 'Calculate average PR lifecycle durations';


-- =====================================================
-- GRANTS
-- =====================================================

-- Grant permissions to gsc_user
GRANT USAGE ON SCHEMA automation TO gsc_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA automation TO gsc_user;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA automation TO gsc_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA automation TO gsc_user;

-- =====================================================
-- SAMPLE DATA (for testing)
-- =====================================================

-- Insert sample PR (commented out by default)
/*
INSERT INTO automation.pull_requests (
    repo_owner,
    repo_name,
    branch_name,
    pr_title,
    pr_description,
    property,
    recommendations,
    status
) VALUES (
    'myorg',
    'blog',
    'auto-optimize-20251121',
    'Auto-optimize: Update meta descriptions for 10 pages',
    'Automated optimization based on SEO recommendations...',
    'https://blog.aspose.net',
    '[{"type": "update_meta", "page": "/cells/python/", "priority": 85}]'::jsonb,
    'created'
);
*/

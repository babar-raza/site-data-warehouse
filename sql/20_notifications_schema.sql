-- =====================================================
-- Notifications & Alerting Schema
-- =====================================================
-- Purpose: Real-time alerts and notifications for SEO metrics
-- Phase: 4
-- Dependencies: uuid-ossp extension
-- =====================================================

-- Create schema
CREATE SCHEMA IF NOT EXISTS notifications;

-- =====================================================
-- ALERT RULES TABLE
-- =====================================================
-- Define conditions that trigger alerts
CREATE TABLE notifications.alert_rules (
    rule_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rule_name TEXT NOT NULL,
    rule_type TEXT NOT NULL, -- serp_drop, cwv_violation, traffic_anomaly, task_failure
    property TEXT, -- NULL = applies to all properties
    page_path TEXT, -- NULL = applies to all pages
    query_id UUID, -- Specific query to monitor (for SERP alerts)

    -- Conditions (JSON format for flexibility)
    conditions JSONB NOT NULL,
    /*
    Examples:
    SERP Drop: {"position_drop": 3, "timeframe_hours": 24}
    CWV Violation: {"lcp_max": 2500, "cls_max": 0.1, "performance_score_min": 90}
    Traffic Anomaly: {"drop_percentage": 20, "detection_method": "ml"}
    */

    -- Alert configuration
    severity TEXT DEFAULT 'medium' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    channels TEXT[] DEFAULT ARRAY['slack'], -- slack, email, webhook, sms
    channel_config JSONB, -- Channel-specific configuration (webhook URLs, email addresses)

    -- Suppression settings
    suppression_window_minutes INT DEFAULT 60, -- Don't re-alert for this many minutes
    max_alerts_per_day INT DEFAULT 10, -- Prevent alert spam

    -- Status
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT
);

CREATE INDEX idx_alert_rules_type ON notifications.alert_rules(rule_type);
CREATE INDEX idx_alert_rules_property ON notifications.alert_rules(property);
CREATE INDEX idx_alert_rules_active ON notifications.alert_rules(is_active) WHERE is_active = true;

COMMENT ON TABLE notifications.alert_rules IS 'Alert rule definitions with conditions and channels';
COMMENT ON COLUMN notifications.alert_rules.conditions IS 'JSONB object defining trigger conditions';
COMMENT ON COLUMN notifications.alert_rules.channels IS 'Array of notification channels to use';


-- =====================================================
-- ALERT HISTORY TABLE
-- =====================================================
-- Track all alerts triggered
CREATE TABLE notifications.alert_history (
    alert_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rule_id UUID REFERENCES notifications.alert_rules(rule_id),

    -- Alert details
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rule_name TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    severity TEXT NOT NULL,

    -- Context
    property TEXT,
    page_path TEXT,
    query_id UUID,

    -- Alert content
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata JSONB, -- Additional context data

    -- Notification status
    channels_sent TEXT[], -- Which channels succeeded
    channels_failed TEXT[], -- Which channels failed
    send_attempts INT DEFAULT 0,
    last_send_attempt TIMESTAMP,

    -- Resolution
    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'investigating', 'resolved', 'false_positive', 'suppressed')),
    resolved_at TIMESTAMP,
    resolved_by TEXT,
    resolution_notes TEXT,

    -- Metrics
    time_to_resolve_minutes INT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_alert_history_triggered ON notifications.alert_history(triggered_at DESC);
CREATE INDEX idx_alert_history_property ON notifications.alert_history(property);
CREATE INDEX idx_alert_history_rule ON notifications.alert_history(rule_id);
CREATE INDEX idx_alert_history_status ON notifications.alert_history(status) WHERE status = 'open';
CREATE INDEX idx_alert_history_severity ON notifications.alert_history(severity);

COMMENT ON TABLE notifications.alert_history IS 'Historical record of all triggered alerts';


-- =====================================================
-- CHANNEL CONFIGURATIONS TABLE
-- =====================================================
-- Store credentials and settings for notification channels
CREATE TABLE notifications.channel_configs (
    config_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel_type TEXT NOT NULL CHECK (channel_type IN ('slack', 'email', 'webhook', 'sms')),
    config_name TEXT NOT NULL,

    -- Configuration (encrypted sensitive data recommended)
    configuration JSONB NOT NULL,
    /*
    Slack: {"webhook_url": "https://hooks.slack.com/...", "channel": "#alerts"}
    Email: {"smtp_host": "smtp.gmail.com", "smtp_port": 587, "from_email": "alerts@example.com", "to_emails": ["team@example.com"]}
    Webhook: {"url": "https://api.pagerduty.com/...", "headers": {"Authorization": "Token ..."}}
    SMS: {"provider": "twilio", "account_sid": "...", "auth_token": "...", "from_number": "+1234567890"}
    */

    -- Status
    is_active BOOLEAN DEFAULT true,
    last_test_at TIMESTAMP,
    last_test_success BOOLEAN,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_channel_configs_type ON notifications.channel_configs(channel_type);
CREATE INDEX idx_channel_configs_active ON notifications.channel_configs(is_active) WHERE is_active = true;

COMMENT ON TABLE notifications.channel_configs IS 'Notification channel credentials and settings';


-- =====================================================
-- ALERT SUPPRESSIONS TABLE
-- =====================================================
-- Temporarily suppress alerts for maintenance windows or known issues
CREATE TABLE notifications.suppressions (
    suppression_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    suppression_name TEXT NOT NULL,

    -- What to suppress
    rule_id UUID REFERENCES notifications.alert_rules(rule_id), -- NULL = all rules
    property TEXT, -- NULL = all properties
    alert_type TEXT, -- NULL = all types

    -- Duration
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,

    -- Reason
    reason TEXT,
    created_by TEXT,

    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_suppressions_active ON notifications.suppressions(is_active, start_time, end_time)
    WHERE is_active = true;

COMMENT ON TABLE notifications.suppressions IS 'Temporary alert suppressions for maintenance windows';


-- =====================================================
-- NOTIFICATION QUEUE TABLE
-- =====================================================
-- Queue for pending notifications (for retry logic)
CREATE TABLE notifications.notification_queue (
    queue_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_id UUID REFERENCES notifications.alert_history(alert_id),

    channel_type TEXT NOT NULL,
    channel_config JSONB NOT NULL,

    -- Message
    payload JSONB NOT NULL, -- Full message to send

    -- Queue status
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'sending', 'sent', 'failed')),
    attempts INT DEFAULT 0,
    max_attempts INT DEFAULT 3,
    next_attempt_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_error TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP
);

CREATE INDEX idx_queue_status ON notifications.notification_queue(status, next_attempt_at)
    WHERE status IN ('pending', 'failed');

COMMENT ON TABLE notifications.notification_queue IS 'Queue for notification delivery with retry logic';


-- =====================================================
-- ALERT AGGREGATIONS TABLE
-- =====================================================
-- Group similar alerts to prevent spam
CREATE TABLE notifications.alert_aggregations (
    aggregation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    aggregation_key TEXT NOT NULL, -- Unique key for grouping (e.g., "serp_drop:blog.aspose.net")

    -- Aggregation window
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,

    -- Aggregated data
    alert_count INT DEFAULT 0,
    alert_ids UUID[], -- Array of individual alert IDs
    first_alert_at TIMESTAMP,
    last_alert_at TIMESTAMP,

    -- Summary
    summary_title TEXT,
    summary_message TEXT,

    -- Notification status
    notification_sent BOOLEAN DEFAULT false,
    notification_sent_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_aggregations_key ON notifications.alert_aggregations(aggregation_key);
CREATE INDEX idx_aggregations_window ON notifications.alert_aggregations(window_start, window_end);

COMMENT ON TABLE notifications.alert_aggregations IS 'Aggregated alerts to prevent notification spam';


-- =====================================================
-- VIEWS
-- =====================================================

-- Active alerts summary
CREATE OR REPLACE VIEW notifications.vw_active_alerts AS
SELECT
    ah.alert_id,
    ah.triggered_at,
    ah.rule_name,
    ah.rule_type,
    ah.severity,
    ah.property,
    ah.page_path,
    ah.title,
    ah.message,
    ah.status,
    ar.channels,
    EXTRACT(EPOCH FROM (NOW() - ah.triggered_at)) / 60 as age_minutes
FROM notifications.alert_history ah
LEFT JOIN notifications.alert_rules ar ON ah.rule_id = ar.rule_id
WHERE ah.status = 'open'
ORDER BY ah.triggered_at DESC;

COMMENT ON VIEW notifications.vw_active_alerts IS 'Currently active (unresolved) alerts';


-- Alert statistics by rule
CREATE OR REPLACE VIEW notifications.vw_alert_stats_by_rule AS
SELECT
    ar.rule_id,
    ar.rule_name,
    ar.rule_type,
    ar.severity,
    COUNT(*) FILTER (WHERE ah.triggered_at >= NOW() - INTERVAL '24 hours') as alerts_24h,
    COUNT(*) FILTER (WHERE ah.triggered_at >= NOW() - INTERVAL '7 days') as alerts_7d,
    COUNT(*) FILTER (WHERE ah.triggered_at >= NOW() - INTERVAL '30 days') as alerts_30d,
    COUNT(*) FILTER (WHERE ah.status = 'false_positive') as false_positives,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE ah.status = 'false_positive') /
        NULLIF(COUNT(*), 0),
        2
    ) as false_positive_rate,
    AVG(ah.time_to_resolve_minutes) FILTER (WHERE ah.status = 'resolved') as avg_resolution_time_minutes,
    ar.is_active
FROM notifications.alert_rules ar
LEFT JOIN notifications.alert_history ah ON ar.rule_id = ah.rule_id
WHERE ah.triggered_at >= NOW() - INTERVAL '30 days' OR ah.alert_id IS NULL
GROUP BY ar.rule_id, ar.rule_name, ar.rule_type, ar.severity, ar.is_active
ORDER BY alerts_24h DESC;

COMMENT ON VIEW notifications.vw_alert_stats_by_rule IS 'Alert statistics and performance metrics by rule';


-- Recent alert timeline
CREATE OR REPLACE VIEW notifications.vw_recent_alerts AS
SELECT
    ah.alert_id,
    ah.triggered_at,
    ah.rule_name,
    ah.rule_type,
    ah.severity,
    ah.property,
    ah.title,
    ah.status,
    ah.channels_sent,
    CASE
        WHEN ah.resolved_at IS NOT NULL THEN
            EXTRACT(EPOCH FROM (ah.resolved_at - ah.triggered_at)) / 60
        ELSE NULL
    END as resolution_time_minutes
FROM notifications.alert_history ah
WHERE ah.triggered_at >= NOW() - INTERVAL '7 days'
ORDER BY ah.triggered_at DESC;

COMMENT ON VIEW notifications.vw_recent_alerts IS 'Alerts from the last 7 days with resolution times';


-- Alert health metrics
CREATE OR REPLACE VIEW notifications.vw_alert_health AS
SELECT
    'Alert System Health' as metric_category,
    COUNT(*) FILTER (WHERE status = 'open' AND triggered_at < NOW() - INTERVAL '24 hours') as stale_alerts_24h,
    COUNT(*) FILTER (WHERE status = 'open' AND severity = 'critical') as critical_open,
    COUNT(*) FILTER (WHERE status = 'open' AND severity = 'high') as high_open,
    COUNT(*) FILTER (WHERE channels_failed IS NOT NULL AND array_length(channels_failed, 1) > 0) as failed_deliveries_24h,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE array_length(channels_sent, 1) > 0) /
        NULLIF(COUNT(*), 0),
        2
    ) as delivery_success_rate_24h,
    COUNT(*) FILTER (WHERE status = 'false_positive') as false_positives_7d
FROM notifications.alert_history
WHERE triggered_at >= NOW() - INTERVAL '7 days';

COMMENT ON VIEW notifications.vw_alert_health IS 'Overall alert system health metrics';


-- =====================================================
-- FUNCTIONS
-- =====================================================

-- Check if alert should be suppressed
CREATE OR REPLACE FUNCTION notifications.is_suppressed(
    p_rule_id UUID,
    p_property TEXT,
    p_alert_type TEXT
) RETURNS BOOLEAN AS $$
DECLARE
    v_suppressed BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM notifications.suppressions
        WHERE is_active = true
            AND NOW() BETWEEN start_time AND end_time
            AND (rule_id IS NULL OR rule_id = p_rule_id)
            AND (property IS NULL OR property = p_property)
            AND (alert_type IS NULL OR alert_type = p_alert_type)
    ) INTO v_suppressed;

    RETURN v_suppressed;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION notifications.is_suppressed IS 'Check if an alert should be suppressed based on active suppressions';


-- Create alert from rule
CREATE OR REPLACE FUNCTION notifications.trigger_alert(
    p_rule_id UUID,
    p_property TEXT,
    p_page_path TEXT,
    p_title TEXT,
    p_message TEXT,
    p_metadata JSONB DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_alert_id UUID;
    v_rule RECORD;
    v_is_suppressed BOOLEAN;
    v_recent_count INT;
BEGIN
    -- Get rule details
    SELECT * INTO v_rule
    FROM notifications.alert_rules
    WHERE rule_id = p_rule_id AND is_active = true;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Alert rule % not found or inactive', p_rule_id;
    END IF;

    -- Check suppression
    v_is_suppressed := notifications.is_suppressed(p_rule_id, p_property, v_rule.rule_type);

    -- Check suppression window
    SELECT COUNT(*) INTO v_recent_count
    FROM notifications.alert_history
    WHERE rule_id = p_rule_id
        AND property = p_property
        AND triggered_at > NOW() - (v_rule.suppression_window_minutes || ' minutes')::INTERVAL;

    -- Check daily limit
    IF v_recent_count >= v_rule.max_alerts_per_day THEN
        -- Create but mark as suppressed
        INSERT INTO notifications.alert_history (
            rule_id, rule_name, rule_type, severity, property, page_path,
            title, message, metadata, status
        ) VALUES (
            p_rule_id, v_rule.rule_name, v_rule.rule_type, v_rule.severity,
            p_property, p_page_path, p_title, p_message, p_metadata, 'suppressed'
        ) RETURNING alert_id INTO v_alert_id;

        RETURN v_alert_id;
    END IF;

    -- Create alert
    INSERT INTO notifications.alert_history (
        rule_id, rule_name, rule_type, severity, property, page_path,
        title, message, metadata, status
    ) VALUES (
        p_rule_id, v_rule.rule_name, v_rule.rule_type, v_rule.severity,
        p_property, p_page_path, p_title, p_message, p_metadata,
        CASE WHEN v_is_suppressed THEN 'suppressed' ELSE 'open' END
    ) RETURNING alert_id INTO v_alert_id;

    -- Queue notifications if not suppressed
    IF NOT v_is_suppressed THEN
        -- Add to notification queue for each channel
        INSERT INTO notifications.notification_queue (alert_id, channel_type, channel_config, payload)
        SELECT
            v_alert_id,
            unnest(v_rule.channels),
            v_rule.channel_config,
            jsonb_build_object(
                'alert_id', v_alert_id,
                'title', p_title,
                'message', p_message,
                'severity', v_rule.severity,
                'property', p_property,
                'metadata', p_metadata
            );
    END IF;

    RETURN v_alert_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION notifications.trigger_alert IS 'Create an alert from a rule with suppression logic';


-- Resolve alert
CREATE OR REPLACE FUNCTION notifications.resolve_alert(
    p_alert_id UUID,
    p_resolved_by TEXT,
    p_resolution_notes TEXT DEFAULT NULL,
    p_is_false_positive BOOLEAN DEFAULT false
) RETURNS VOID AS $$
DECLARE
    v_triggered_at TIMESTAMP;
BEGIN
    SELECT triggered_at INTO v_triggered_at
    FROM notifications.alert_history
    WHERE alert_id = p_alert_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Alert % not found', p_alert_id;
    END IF;

    UPDATE notifications.alert_history
    SET
        status = CASE WHEN p_is_false_positive THEN 'false_positive' ELSE 'resolved' END,
        resolved_at = NOW(),
        resolved_by = p_resolved_by,
        resolution_notes = p_resolution_notes,
        time_to_resolve_minutes = EXTRACT(EPOCH FROM (NOW() - v_triggered_at)) / 60
    WHERE alert_id = p_alert_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION notifications.resolve_alert IS 'Mark an alert as resolved or false positive';


-- Get pending notifications
CREATE OR REPLACE FUNCTION notifications.get_pending_notifications()
RETURNS TABLE (
    queue_id UUID,
    alert_id UUID,
    channel_type TEXT,
    channel_config JSONB,
    payload JSONB,
    attempts INT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        nq.queue_id,
        nq.alert_id,
        nq.channel_type,
        nq.channel_config,
        nq.payload,
        nq.attempts
    FROM notifications.notification_queue nq
    WHERE nq.status IN ('pending', 'failed')
        AND nq.next_attempt_at <= NOW()
        AND nq.attempts < nq.max_attempts
    ORDER BY nq.created_at
    LIMIT 100;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION notifications.get_pending_notifications IS 'Get notifications ready to be sent';


-- =====================================================
-- TRIGGERS
-- =====================================================

-- Update updated_at timestamp
CREATE OR REPLACE FUNCTION notifications.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER alert_rules_updated_at
    BEFORE UPDATE ON notifications.alert_rules
    FOR EACH ROW
    EXECUTE FUNCTION notifications.update_updated_at();

CREATE TRIGGER channel_configs_updated_at
    BEFORE UPDATE ON notifications.channel_configs
    FOR EACH ROW
    EXECUTE FUNCTION notifications.update_updated_at();


-- =====================================================
-- GRANTS
-- =====================================================

GRANT USAGE ON SCHEMA notifications TO gsc_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA notifications TO gsc_user;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA notifications TO gsc_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA notifications TO gsc_user;


-- =====================================================
-- SAMPLE DATA
-- =====================================================

-- Example alert rules (commented out)
/*
-- SERP position drop alert
INSERT INTO notifications.alert_rules (rule_name, rule_type, property, conditions, severity, channels, channel_config)
VALUES (
    'SERP Position Drop >3',
    'serp_drop',
    'https://blog.aspose.net',
    '{"position_drop": 3, "timeframe_hours": 24}',
    'high',
    ARRAY['slack', 'email'],
    '{"slack_channel": "#seo-alerts", "email_recipients": ["seo-team@example.com"]}'
);

-- CWV threshold violation
INSERT INTO notifications.alert_rules (rule_name, rule_type, property, conditions, severity, channels)
VALUES (
    'Core Web Vitals Violation',
    'cwv_violation',
    'https://blog.aspose.net',
    '{"lcp_max": 2500, "cls_max": 0.1, "performance_score_min": 90}',
    'medium',
    ARRAY['slack']
);

-- Traffic anomaly detection
INSERT INTO notifications.alert_rules (rule_name, rule_type, conditions, severity, channels)
VALUES (
    'Traffic Anomaly Detected',
    'traffic_anomaly',
    '{"drop_percentage": 20, "detection_method": "ml", "confidence_threshold": 0.8}',
    'critical',
    ARRAY['slack', 'email']
);
*/

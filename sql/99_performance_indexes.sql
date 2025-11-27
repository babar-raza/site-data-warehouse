-- ============================================================================
-- Performance Optimization Indexes
-- ============================================================================
-- This file creates indexes for improved query performance
-- Run after initial schema setup

-- ============================================================================
-- GSC Schema Indexes
-- ============================================================================

-- Query stats - most common queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gsc_query_stats_date_desc
    ON gsc.query_stats(data_date DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gsc_query_stats_property_date
    ON gsc.query_stats(property, data_date DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gsc_query_stats_clicks
    ON gsc.query_stats(clicks DESC) WHERE clicks > 0;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gsc_query_stats_impressions
    ON gsc.query_stats(impressions DESC) WHERE impressions > 0;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gsc_query_stats_position
    ON gsc.query_stats(position) WHERE position <= 20;

-- Text search on queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gsc_query_stats_query_text_trgm
    ON gsc.query_stats USING gin(query_text gin_trgm_ops);

-- Composite index for common filters
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gsc_query_stats_property_page_date
    ON gsc.query_stats(property, page_path, data_date DESC);

-- ============================================================================
-- SERP Schema Indexes
-- ============================================================================

-- Position history - time series queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_serp_position_history_checked_at
    ON serp.position_history(checked_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_serp_position_history_query_checked
    ON serp.position_history(query_id, checked_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_serp_position_history_property_checked
    ON serp.position_history(property, checked_at DESC);

-- Position drops (for alerts)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_serp_position_history_position
    ON serp.position_history(position) WHERE position > 0;

-- Active queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_serp_queries_active
    ON serp.queries(property, is_active) WHERE is_active = true;

-- Query text search
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_serp_queries_text_trgm
    ON serp.queries USING gin(query_text gin_trgm_ops);

-- ============================================================================
-- Performance Schema Indexes
-- ============================================================================

-- CWV metrics - time series
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cwv_metrics_checked_at
    ON performance.cwv_metrics(checked_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cwv_metrics_property_checked
    ON performance.cwv_metrics(property, checked_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cwv_metrics_property_page_device
    ON performance.cwv_metrics(property, page_path, device, checked_at DESC);

-- Poor performance detection
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cwv_metrics_lcp
    ON performance.cwv_metrics(lcp) WHERE lcp > 2500;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cwv_metrics_cls
    ON performance.cwv_metrics(cls) WHERE cls > 0.1;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cwv_metrics_perf_score
    ON performance.cwv_metrics(performance_score) WHERE performance_score < 50;

-- ============================================================================
-- Notifications Schema Indexes
-- ============================================================================

-- Alert history - recent alerts
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alert_history_triggered_at
    ON notifications.alert_history(triggered_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alert_history_property_triggered
    ON notifications.alert_history(property, triggered_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alert_history_rule_triggered
    ON notifications.alert_history(rule_id, triggered_at DESC);

-- Active/open alerts
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alert_history_status
    ON notifications.alert_history(status, triggered_at DESC)
    WHERE status IN ('open', 'acknowledged');

-- Severity filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alert_history_severity
    ON notifications.alert_history(severity, triggered_at DESC)
    WHERE severity IN ('high', 'critical');

-- Notification queue - processing
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notification_queue_status_created
    ON notifications.notification_queue(status, created_at)
    WHERE status = 'pending';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notification_queue_alert
    ON notifications.notification_queue(alert_id, status);

-- Alert rules - active rules
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alert_rules_active
    ON notifications.alert_rules(is_active, property)
    WHERE is_active = true;

-- ============================================================================
-- Orchestration Schema Indexes
-- ============================================================================

-- Workflows - recent and active
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workflows_started_at
    ON orchestration.workflows(started_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workflows_property_started
    ON orchestration.workflows(property, started_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workflows_status
    ON orchestration.workflows(status, started_at DESC)
    WHERE status IN ('running', 'pending');

-- Agent decisions
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_decisions_workflow
    ON orchestration.agent_decisions(workflow_id, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_decisions_agent_created
    ON orchestration.agent_decisions(agent_name, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_decisions_confidence
    ON orchestration.agent_decisions(confidence DESC) WHERE confidence >= 0.8;

-- Workflow steps
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_workflow_steps_workflow
    ON orchestration.workflow_steps(workflow_id, step_order);

-- ============================================================================
-- Anomaly Schema Indexes
-- ============================================================================

-- Anomaly detections - recent and severity
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_anomaly_detections_detected_at
    ON anomaly.detections(detected_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_anomaly_detections_property_detected
    ON anomaly.detections(property, detected_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_anomaly_detections_severity
    ON anomaly.detections(severity, detected_at DESC)
    WHERE severity IN ('high', 'critical');

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_anomaly_detections_status
    ON anomaly.detections(status, detected_at DESC)
    WHERE status = 'open';

-- Detection method filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_anomaly_detections_method
    ON anomaly.detections(detection_method, detected_at DESC);

-- ============================================================================
-- GA4 Schema Indexes
-- ============================================================================

-- Events - time series
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ga4_events_date
    ON ga4.events(event_date DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ga4_events_property_date
    ON ga4.events(property_id, event_date DESC);

-- Page path filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ga4_events_page_path
    ON ga4.events(page_path, event_date DESC);

-- ============================================================================
-- Content Schema Indexes
-- ============================================================================

-- Content analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_content_analysis_analyzed_at
    ON content.content_analysis(analyzed_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_content_analysis_property_analyzed
    ON content.content_analysis(property, analyzed_at DESC);

-- Low readability scores
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_content_analysis_readability
    ON content.content_analysis(readability_score) WHERE readability_score < 60;

-- Embeddings - vector similarity search
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_content_embeddings_property
    ON content.embeddings(property, created_at DESC);

-- ============================================================================
-- Forecasts Schema Indexes
-- ============================================================================

-- Forecasts - recent and property
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_forecasts_created_at
    ON forecasts.forecasts(created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_forecasts_property_created
    ON forecasts.forecasts(property, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_forecasts_property_forecast_date
    ON forecasts.forecasts(property, forecast_date);

-- ============================================================================
-- Analyze All Tables
-- ============================================================================

-- Update statistics for query planner
ANALYZE gsc.query_stats;
ANALYZE serp.position_history;
ANALYZE serp.queries;
ANALYZE performance.cwv_metrics;
ANALYZE notifications.alert_history;
ANALYZE notifications.alert_rules;
ANALYZE notifications.notification_queue;
ANALYZE orchestration.workflows;
ANALYZE orchestration.agent_decisions;
ANALYZE anomaly.detections;
ANALYZE ga4.events;
ANALYZE content.content_analysis;
ANALYZE forecasts.forecasts;

-- ============================================================================
-- Index Summary
-- ============================================================================

DO $$
DECLARE
    idx_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO idx_count
    FROM pg_indexes
    WHERE schemaname NOT IN ('pg_catalog', 'information_schema');

    RAISE NOTICE 'Performance indexes created successfully';
    RAISE NOTICE 'Total indexes in database: %', idx_count;
END $$;

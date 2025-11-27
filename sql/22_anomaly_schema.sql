-- =====================================================
-- Anomaly Detection Schema
-- =====================================================
-- Purpose: Track detected anomalies in SEO metrics
-- Phase: 4
-- Dependencies: uuid-ossp extension
-- =====================================================

-- Create schema
CREATE SCHEMA IF NOT EXISTS anomaly;

-- =====================================================
-- ANOMALY DETECTIONS TABLE
-- =====================================================
CREATE TABLE anomaly.detections (
    anomaly_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- What was detected
    metric_type TEXT NOT NULL, -- serp, cwv, traffic, clicks, impressions
    property TEXT NOT NULL,
    page_path TEXT,
    query_id UUID,

    -- Detection method
    detection_method TEXT NOT NULL, -- statistical, isolation_forest, prophet_forecast
    algorithm TEXT, -- z_score, iqr, isolation_forest, etc.

    -- Severity
    severity TEXT DEFAULT 'medium' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    confidence FLOAT CHECK (confidence BETWEEN 0 AND 1),

    -- Anomaly details
    actual_value FLOAT NOT NULL,
    expected_value FLOAT,
    deviation_score FLOAT, -- How many standard deviations or similar
    threshold_breached TEXT, -- Description of threshold

    -- Context
    metadata JSONB, -- Additional context about the anomaly
    time_window TEXT, -- e.g., "last_7_days", "last_30_days"

    -- Status
    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'investigating', 'resolved', 'false_positive')),
    resolved_at TIMESTAMP,
    resolution_notes TEXT,
    alert_triggered BOOLEAN DEFAULT false, -- Was an alert sent?

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_anomaly_property ON anomaly.detections(property);
CREATE INDEX idx_anomaly_detected ON anomaly.detections(detected_at DESC);
CREATE INDEX idx_anomaly_status ON anomaly.detections(status) WHERE status = 'open';
CREATE INDEX idx_anomaly_metric ON anomaly.detections(metric_type);
CREATE INDEX idx_anomaly_severity ON anomaly.detections(severity);

COMMENT ON TABLE anomaly.detections IS 'Detected anomalies in SEO metrics using ML and statistical methods';


-- =====================================================
-- ANOMALY BASELINES TABLE
-- =====================================================
-- Store baseline statistics for metrics
CREATE TABLE anomaly.baselines (
    baseline_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_type TEXT NOT NULL,
    property TEXT NOT NULL,
    page_path TEXT,
    query_id UUID,

    -- Statistical baselines
    mean_value FLOAT,
    median_value FLOAT,
    std_dev FLOAT,
    percentile_25 FLOAT,
    percentile_75 FLOAT,
    min_value FLOAT,
    max_value FLOAT,

    -- Time-based info
    baseline_start_date DATE NOT NULL,
    baseline_end_date DATE NOT NULL,
    data_points_count INT,

    -- Calculated thresholds
    lower_bound FLOAT, -- Values below this are anomalies
    upper_bound FLOAT, -- Values above this are anomalies

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(metric_type, property, page_path, query_id, baseline_end_date)
);

CREATE INDEX idx_baselines_metric ON anomaly.baselines(metric_type);
CREATE INDEX idx_baselines_property ON anomaly.baselines(property);
CREATE INDEX idx_baselines_dates ON anomaly.baselines(baseline_start_date, baseline_end_date);

COMMENT ON TABLE anomaly.baselines IS 'Statistical baselines for anomaly detection';


-- =====================================================
-- VIEWS
-- =====================================================

-- Recent anomalies
CREATE OR REPLACE VIEW anomaly.vw_recent_anomalies AS
SELECT
    anomaly_id,
    detected_at,
    metric_type,
    property,
    page_path,
    detection_method,
    severity,
    actual_value,
    expected_value,
    deviation_score,
    status,
    alert_triggered
FROM anomaly.detections
WHERE detected_at >= NOW() - INTERVAL '7 days'
ORDER BY detected_at DESC, severity DESC;

COMMENT ON VIEW anomaly.vw_recent_anomalies IS 'Anomalies detected in the last 7 days';


-- Anomaly summary
CREATE OR REPLACE VIEW anomaly.vw_anomaly_summary AS
SELECT
    metric_type,
    property,
    COUNT(*) as total_anomalies,
    COUNT(*) FILTER (WHERE severity = 'critical') as critical_count,
    COUNT(*) FILTER (WHERE severity = 'high') as high_count,
    COUNT(*) FILTER (WHERE status = 'open') as open_count,
    COUNT(*) FILTER (WHERE status = 'false_positive') as false_positives,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE status = 'false_positive') /
        NULLIF(COUNT(*), 0),
        2
    ) as false_positive_rate,
    MAX(detected_at) as last_detection
FROM anomaly.detections
WHERE detected_at >= NOW() - INTERVAL '30 days'
GROUP BY metric_type, property
ORDER BY total_anomalies DESC;

COMMENT ON VIEW anomaly.vw_anomaly_summary IS 'Anomaly statistics by metric and property';


-- =====================================================
-- FUNCTIONS
-- =====================================================

-- Record anomaly detection
CREATE OR REPLACE FUNCTION anomaly.record_detection(
    p_metric_type TEXT,
    p_property TEXT,
    p_actual_value FLOAT,
    p_expected_value FLOAT,
    p_detection_method TEXT,
    p_severity TEXT DEFAULT 'medium',
    p_page_path TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_anomaly_id UUID;
    v_deviation_score FLOAT;
BEGIN
    -- Calculate deviation score
    IF p_expected_value > 0 THEN
        v_deviation_score := ABS(p_actual_value - p_expected_value) / p_expected_value;
    ELSE
        v_deviation_score := ABS(p_actual_value - p_expected_value);
    END IF;

    INSERT INTO anomaly.detections (
        metric_type,
        property,
        page_path,
        actual_value,
        expected_value,
        deviation_score,
        detection_method,
        severity,
        metadata,
        status
    ) VALUES (
        p_metric_type,
        p_property,
        p_page_path,
        p_actual_value,
        p_expected_value,
        v_deviation_score,
        p_detection_method,
        p_severity,
        p_metadata,
        'open'
    ) RETURNING anomaly_id INTO v_anomaly_id;

    RETURN v_anomaly_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION anomaly.record_detection IS 'Record a detected anomaly';


-- Update baseline statistics
CREATE OR REPLACE FUNCTION anomaly.update_baseline(
    p_metric_type TEXT,
    p_property TEXT,
    p_start_date DATE,
    p_end_date DATE,
    p_mean FLOAT,
    p_std_dev FLOAT,
    p_lower_bound FLOAT,
    p_upper_bound FLOAT,
    p_data_points INT
) RETURNS VOID AS $$
BEGIN
    INSERT INTO anomaly.baselines (
        metric_type,
        property,
        baseline_start_date,
        baseline_end_date,
        mean_value,
        std_dev,
        lower_bound,
        upper_bound,
        data_points_count
    ) VALUES (
        p_metric_type,
        p_property,
        p_start_date,
        p_end_date,
        p_mean,
        p_std_dev,
        p_lower_bound,
        p_upper_bound,
        p_data_points
    )
    ON CONFLICT (metric_type, property, page_path, query_id, baseline_end_date)
    DO UPDATE SET
        mean_value = EXCLUDED.mean_value,
        std_dev = EXCLUDED.std_dev,
        lower_bound = EXCLUDED.lower_bound,
        upper_bound = EXCLUDED.upper_bound,
        data_points_count = EXCLUDED.data_points_count,
        updated_at = CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION anomaly.update_baseline IS 'Update or create baseline statistics';


-- =====================================================
-- GRANTS
-- =====================================================

GRANT USAGE ON SCHEMA anomaly TO gsc_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA anomaly TO gsc_user;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA anomaly TO gsc_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA anomaly TO gsc_user;

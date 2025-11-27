-- =============================================
-- INTELLIGENCE SCHEMA - FORECASTS & PREDICTIONS
-- =============================================
-- Purpose: Store ML forecasts and predictions (Prophet, causal analysis)
-- Dependencies: None (standalone schema)
-- Phase: Tier 1, Item #4 (Prophet Forecasting)

-- Create dedicated schema for intelligence/ML outputs
CREATE SCHEMA IF NOT EXISTS intelligence;
SET search_path TO intelligence, gsc, public;

-- =============================================
-- TRAFFIC FORECASTS TABLE
-- =============================================
-- Stores Prophet forecasts for traffic prediction and anomaly detection

CREATE TABLE IF NOT EXISTS intelligence.traffic_forecasts (
    -- Identity
    id BIGSERIAL PRIMARY KEY,
    forecast_id UUID DEFAULT uuid_generate_v4(),

    -- Scope
    property VARCHAR(500) NOT NULL,
    page_path TEXT NOT NULL,
    -- NULL page_path = property-level forecast

    date DATE NOT NULL,
    -- Future date being forecasted

    -- Metric being forecasted
    metric_name VARCHAR(50) NOT NULL,
    -- clicks, impressions, conversions, sessions, etc.

    -- Forecast values
    forecast_value FLOAT NOT NULL,
    -- Point estimate (yhat in Prophet)

    lower_bound FLOAT NOT NULL,
    -- Lower bound of prediction interval (yhat_lower)

    upper_bound FLOAT NOT NULL,
    -- Upper bound of prediction interval (yhat_upper)

    confidence_interval FLOAT DEFAULT 0.95,
    -- Confidence level (0.95 = 95% confidence interval)

    -- Actual value (filled in after date occurs)
    actual_value FLOAT,

    -- Prediction quality
    is_anomaly BOOLEAN DEFAULT false,
    -- True if actual_value falls outside prediction interval

    anomaly_severity VARCHAR(20),
    -- low, medium, high, critical

    anomaly_direction VARCHAR(10),
    -- above (positive anomaly) or below (negative anomaly)

    prediction_error FLOAT,
    -- (actual_value - forecast_value) if actual is known

    absolute_percentage_error FLOAT,
    -- abs((actual - forecast) / actual) * 100

    -- Decomposition (from Prophet)
    trend_component FLOAT,
    -- Long-term trend

    weekly_seasonal FLOAT,
    -- Day-of-week effect

    yearly_seasonal FLOAT,
    -- Time-of-year effect (if applicable)

    -- Model metadata
    model_id VARCHAR(100),
    -- Identifier for the specific model used

    model_params JSONB,
    -- Prophet parameters: {seasonality_mode: 'multiplicative', ...}

    training_period_start DATE,
    training_period_end DATE,
    training_data_points INT,
    -- How many historical points used for training

    model_mae FLOAT,
    -- Mean Absolute Error on validation set

    model_rmse FLOAT,
    -- Root Mean Squared Error on validation set

    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    -- Updated when actual_value is filled in

    -- Constraints
    UNIQUE(property, page_path, date, metric_name, created_at),
    CHECK (lower_bound <= forecast_value),
    CHECK (forecast_value <= upper_bound),
    CHECK (confidence_interval BETWEEN 0 AND 1),
    CHECK (anomaly_severity IS NULL OR anomaly_severity IN ('low', 'medium', 'high', 'critical')),
    CHECK (anomaly_direction IS NULL OR anomaly_direction IN ('above', 'below'))
);

-- =============================================
-- FORECAST MODELS TABLE
-- =============================================
-- Tracks Prophet models and their performance

CREATE TABLE IF NOT EXISTS intelligence.forecast_models (
    -- Identity
    id SERIAL PRIMARY KEY,
    model_id VARCHAR(100) UNIQUE NOT NULL,

    -- Model scope
    property VARCHAR(500) NOT NULL,
    page_path TEXT,
    -- NULL = property-level model

    metric_name VARCHAR(50) NOT NULL,

    -- Model type
    model_type VARCHAR(50) NOT NULL DEFAULT 'prophet',
    -- prophet, arima, lstm, etc. (future extensibility)

    -- Prophet configuration
    seasonality_mode VARCHAR(20),
    -- additive, multiplicative

    growth_mode VARCHAR(20),
    -- linear, logistic

    changepoint_prior_scale FLOAT,
    -- Flexibility of trend

    seasonality_prior_scale FLOAT,
    -- Strength of seasonality

    holidays_prior_scale FLOAT,

    -- Performance metrics
    mae FLOAT,
    -- Mean Absolute Error

    rmse FLOAT,
    -- Root Mean Squared Error

    mape FLOAT,
    -- Mean Absolute Percentage Error

    r2_score FLOAT,
    -- R-squared score

    -- Training info
    training_start_date DATE,
    training_end_date DATE,
    training_data_points INT,
    validation_split FLOAT DEFAULT 0.2,

    -- Model status
    status VARCHAR(50) DEFAULT 'active',
    -- active, deprecated, testing

    is_default BOOLEAN DEFAULT false,
    -- Is this the default model for this scope?

    -- Versioning
    version INT DEFAULT 1,
    parent_model_id VARCHAR(100),
    -- Reference to previous model version

    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,

    notes TEXT,

    -- Constraints
    CHECK (seasonality_mode IN ('additive', 'multiplicative')),
    CHECK (growth_mode IN ('linear', 'logistic')),
    CHECK (status IN ('active', 'deprecated', 'testing')),
    CHECK (validation_split BETWEEN 0 AND 0.5)
);

-- =============================================
-- ANOMALY DETECTION LOG
-- =============================================
-- Logs anomalies detected by Prophet (replaces Z-score method)

CREATE TABLE IF NOT EXISTS intelligence.anomaly_log (
    -- Identity
    id BIGSERIAL PRIMARY KEY,
    anomaly_id UUID DEFAULT uuid_generate_v4(),

    -- Source
    forecast_id UUID REFERENCES intelligence.traffic_forecasts(forecast_id) ON DELETE CASCADE,

    -- Anomaly details
    property VARCHAR(500) NOT NULL,
    page_path TEXT NOT NULL,
    detection_date DATE NOT NULL,
    metric_name VARCHAR(50) NOT NULL,

    -- Values
    actual_value FLOAT NOT NULL,
    expected_value FLOAT NOT NULL,
    -- From forecast

    deviation FLOAT NOT NULL,
    -- (actual - expected)

    deviation_pct FLOAT NOT NULL,
    -- ((actual - expected) / expected) * 100

    -- Classification
    severity VARCHAR(20) NOT NULL,
    -- low, medium, high, critical

    direction VARCHAR(10) NOT NULL,
    -- above, below

    confidence FLOAT NOT NULL,
    -- How confident we are this is a true anomaly (0-1)

    -- Context
    is_weekend BOOLEAN,
    is_holiday BOOLEAN,
    day_of_week INT,
    -- 0 = Monday, 6 = Sunday

    -- Impact
    estimated_impact INT,
    -- Estimated clicks/conversions lost or gained

    -- Investigation
    investigated BOOLEAN DEFAULT false,
    investigation_notes TEXT,
    root_cause VARCHAR(100),
    -- technical_issue, content_change, algorithm_update, seasonal, etc.

    false_positive BOOLEAN DEFAULT false,
    -- Marked true if this was not a real anomaly

    -- Actions
    insight_id VARCHAR(64),
    -- Link to generated insight (if any)

    action_taken VARCHAR(200),

    -- Timestamps
    detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    investigated_at TIMESTAMP,

    -- Constraints
    CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    CHECK (direction IN ('above', 'below')),
    CHECK (confidence BETWEEN 0 AND 1),
    CHECK (day_of_week BETWEEN 0 AND 6),
    UNIQUE(property, page_path, detection_date, metric_name)
);

-- =============================================
-- CAUSAL IMPACT ANALYSIS TABLE
-- =============================================
-- Stores causal impact analysis results (for content changes, campaigns, etc.)

CREATE TABLE IF NOT EXISTS intelligence.causal_impact (
    -- Identity
    id SERIAL PRIMARY KEY,
    analysis_id UUID DEFAULT uuid_generate_v4(),

    -- What was tested
    property VARCHAR(500) NOT NULL,
    page_path TEXT NOT NULL,
    event_name VARCHAR(200) NOT NULL,
    -- e.g., "Content Update", "Meta Description Change", "New Internal Links"

    event_date DATE NOT NULL,
    -- When the change occurred

    -- Analysis period
    pre_period_start DATE NOT NULL,
    pre_period_end DATE NOT NULL,
    post_period_start DATE NOT NULL,
    post_period_end DATE NOT NULL,

    -- Metric analyzed
    metric_name VARCHAR(50) NOT NULL,

    -- Causal Impact results
    relative_effect FLOAT,
    -- % change caused by the event

    absolute_effect FLOAT,
    -- Absolute change in metric

    p_value FLOAT,
    -- Statistical significance (p < 0.05 = significant)

    is_significant BOOLEAN,
    -- True if p_value < 0.05

    confidence_interval_lower FLOAT,
    confidence_interval_upper FLOAT,

    -- Interpretation
    effect_type VARCHAR(20),
    -- positive, negative, neutral

    probability FLOAT,
    -- Probability that effect is real (0-1)

    -- Summary
    summary TEXT,
    -- Human-readable interpretation

    -- Analysis metadata
    method VARCHAR(50) DEFAULT 'causalimpact',
    -- causalimpact, diffinDiff, etc.

    model_params JSONB,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CHECK (p_value BETWEEN 0 AND 1),
    CHECK (probability BETWEEN 0 AND 1),
    CHECK (effect_type IN ('positive', 'negative', 'neutral')),
    UNIQUE(property, page_path, event_name, event_date, metric_name)
);

-- =============================================
-- INDEXES
-- =============================================

-- Traffic forecasts
CREATE INDEX IF NOT EXISTS idx_forecasts_property_page ON intelligence.traffic_forecasts(property, page_path);
CREATE INDEX IF NOT EXISTS idx_forecasts_date ON intelligence.traffic_forecasts(date);
CREATE INDEX IF NOT EXISTS idx_forecasts_metric ON intelligence.traffic_forecasts(metric_name);
CREATE INDEX IF NOT EXISTS idx_forecasts_anomaly ON intelligence.traffic_forecasts(is_anomaly) WHERE is_anomaly = true;
CREATE INDEX IF NOT EXISTS idx_forecasts_property_page_date ON intelligence.traffic_forecasts(property, page_path, date);

-- Forecast models
CREATE INDEX IF NOT EXISTS idx_models_property_page ON intelligence.forecast_models(property, page_path);
CREATE INDEX IF NOT EXISTS idx_models_status ON intelligence.forecast_models(status);
CREATE INDEX IF NOT EXISTS idx_models_default ON intelligence.forecast_models(is_default) WHERE is_default = true;

-- Anomaly log
CREATE INDEX IF NOT EXISTS idx_anomalies_property_page ON intelligence.anomaly_log(property, page_path);
CREATE INDEX IF NOT EXISTS idx_anomalies_date ON intelligence.anomaly_log(detection_date DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_severity ON intelligence.anomaly_log(severity);
CREATE INDEX IF NOT EXISTS idx_anomalies_investigated ON intelligence.anomaly_log(investigated) WHERE investigated = false;

-- Causal impact
CREATE INDEX IF NOT EXISTS idx_causal_property_page ON intelligence.causal_impact(property, page_path);
CREATE INDEX IF NOT EXISTS idx_causal_event_date ON intelligence.causal_impact(event_date);
CREATE INDEX IF NOT EXISTS idx_causal_significant ON intelligence.causal_impact(is_significant) WHERE is_significant = true;

-- =============================================
-- VIEWS
-- =============================================

-- Recent anomalies
CREATE OR REPLACE VIEW intelligence.vw_recent_anomalies AS
SELECT
    a.*,
    f.forecast_value,
    f.lower_bound,
    f.upper_bound
FROM intelligence.anomaly_log a
LEFT JOIN intelligence.traffic_forecasts f ON a.forecast_id = f.forecast_id
WHERE a.detected_at >= CURRENT_DATE - INTERVAL '30 days'
    AND a.false_positive = false
ORDER BY a.detected_at DESC, a.severity DESC;

-- Model performance summary
CREATE OR REPLACE VIEW intelligence.vw_model_performance AS
SELECT
    model_id,
    property,
    page_path,
    metric_name,
    model_type,
    mae,
    rmse,
    mape,
    r2_score,
    training_data_points,
    status,
    version,
    created_at,
    last_used_at,
    CASE
        WHEN mape < 10 THEN 'excellent'
        WHEN mape < 20 THEN 'good'
        WHEN mape < 30 THEN 'fair'
        ELSE 'poor'
    END AS performance_rating
FROM intelligence.forecast_models
ORDER BY status, mape ASC;

-- Forecast accuracy
CREATE OR REPLACE VIEW intelligence.vw_forecast_accuracy AS
SELECT
    property,
    page_path,
    metric_name,
    DATE_TRUNC('month', date) AS month,
    COUNT(*) AS forecast_count,
    COUNT(*) FILTER (WHERE actual_value IS NOT NULL) AS actual_count,
    AVG(absolute_percentage_error) AS avg_mape,
    AVG(prediction_error) AS avg_error,
    COUNT(*) FILTER (WHERE is_anomaly = true) AS anomaly_count
FROM intelligence.traffic_forecasts
WHERE actual_value IS NOT NULL
GROUP BY property, page_path, metric_name, DATE_TRUNC('month', date)
ORDER BY month DESC, property, page_path;

-- =============================================
-- FUNCTIONS
-- =============================================

-- Mark anomalies based on prediction intervals
CREATE OR REPLACE FUNCTION intelligence.detect_anomalies_from_forecasts()
RETURNS INT AS $$
DECLARE
    anomalies_found INT := 0;
BEGIN
    -- Update forecasts where actual falls outside prediction interval
    UPDATE intelligence.traffic_forecasts
    SET
        is_anomaly = true,
        anomaly_direction = CASE
            WHEN actual_value > upper_bound THEN 'above'
            WHEN actual_value < lower_bound THEN 'below'
        END,
        anomaly_severity = CASE
            WHEN ABS(actual_value - forecast_value) > 2 * ABS(upper_bound - forecast_value) THEN 'critical'
            WHEN ABS(actual_value - forecast_value) > 1.5 * ABS(upper_bound - forecast_value) THEN 'high'
            WHEN ABS(actual_value - forecast_value) > ABS(upper_bound - forecast_value) THEN 'medium'
            ELSE 'low'
        END,
        prediction_error = actual_value - forecast_value,
        absolute_percentage_error = ABS((actual_value - forecast_value) / NULLIF(actual_value, 0)) * 100,
        updated_at = CURRENT_TIMESTAMP
    WHERE actual_value IS NOT NULL
        AND (actual_value > upper_bound OR actual_value < lower_bound)
        AND is_anomaly = false;

    GET DIAGNOSTICS anomalies_found = ROW_COUNT;

    RETURN anomalies_found;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION intelligence.detect_anomalies_from_forecasts IS 'Detect anomalies by comparing actual values to forecast intervals';

-- =============================================
-- COMMENTS
-- =============================================
COMMENT ON SCHEMA intelligence IS 'ML-powered forecasts, predictions, and causal analysis';
COMMENT ON TABLE intelligence.traffic_forecasts IS 'Prophet forecasts for traffic prediction and anomaly detection';
COMMENT ON TABLE intelligence.forecast_models IS 'Trained Prophet models and their performance metrics';
COMMENT ON TABLE intelligence.anomaly_log IS 'Anomalies detected by comparing actuals to forecasts';
COMMENT ON TABLE intelligence.causal_impact IS 'Causal impact analysis for content changes and events';

-- =============================================
-- VERIFICATION
-- =============================================
DO $$
BEGIN
    RAISE NOTICE 'Intelligence schema created successfully ✓';
    RAISE NOTICE 'Schema: intelligence';
    RAISE NOTICE 'Tables: traffic_forecasts, forecast_models, anomaly_log, causal_impact';
    RAISE NOTICE 'Views: vw_recent_anomalies, vw_model_performance, vw_forecast_accuracy';
    RAISE NOTICE 'Functions: detect_anomalies_from_forecasts()';
END $$;

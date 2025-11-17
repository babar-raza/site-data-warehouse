-- Unified Performance View
-- Combines GSC, GA4, and Content Metadata with rolling averages and time-series comparisons

SET search_path TO gsc, public;

-- Drop existing view if exists
DROP VIEW IF EXISTS gsc.vw_unified_page_performance CASCADE;

-- Create unified performance view with pre-calculated time-series metrics
CREATE VIEW gsc.vw_unified_page_performance AS
WITH 
-- Aggregate GSC data by page and date (rollup device/country/query)
gsc_daily AS (
    SELECT 
        date,
        property,
        url as page_path,
        SUM(clicks) as gsc_clicks,
        SUM(impressions) as gsc_impressions,
        CASE 
            WHEN SUM(impressions) > 0 THEN SUM(clicks)::NUMERIC / SUM(impressions)
            ELSE 0 
        END as gsc_ctr,
        AVG(position) as gsc_avg_position
    FROM gsc.fact_gsc_daily
    GROUP BY date, property, url
),
-- Calculate 7-day rolling averages and changes
gsc_with_windows AS (
    SELECT 
        *,
        AVG(gsc_clicks) OVER (
            PARTITION BY property, page_path 
            ORDER BY date 
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) as gsc_clicks_7d_avg,
        AVG(gsc_impressions) OVER (
            PARTITION BY property, page_path 
            ORDER BY date 
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) as gsc_impressions_7d_avg,
        AVG(gsc_avg_position) OVER (
            PARTITION BY property, page_path 
            ORDER BY date 
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) as gsc_position_7d_avg,
        AVG(gsc_clicks) OVER (
            PARTITION BY property, page_path 
            ORDER BY date 
            ROWS BETWEEN 27 PRECEDING AND CURRENT ROW
        ) as gsc_clicks_28d_avg,
        LAG(gsc_clicks, 7) OVER (
            PARTITION BY property, page_path 
            ORDER BY date
        ) as gsc_clicks_7d_ago,
        LAG(gsc_impressions, 7) OVER (
            PARTITION BY property, page_path 
            ORDER BY date
        ) as gsc_impressions_7d_ago,
        LAG(gsc_avg_position, 7) OVER (
            PARTITION BY property, page_path 
            ORDER BY date
        ) as gsc_position_7d_ago
    FROM gsc_daily
),
-- Calculate percentage changes
gsc_with_changes AS (
    SELECT 
        *,
        CASE 
            WHEN gsc_clicks_7d_ago > 0 THEN 
                ((gsc_clicks - gsc_clicks_7d_ago)::NUMERIC / gsc_clicks_7d_ago) * 100
            ELSE NULL 
        END as gsc_clicks_change_wow,
        CASE 
            WHEN gsc_impressions_7d_ago > 0 THEN 
                ((gsc_impressions - gsc_impressions_7d_ago)::NUMERIC / gsc_impressions_7d_ago) * 100
            ELSE NULL 
        END as gsc_impressions_change_wow,
        CASE 
            WHEN gsc_position_7d_ago > 0 THEN 
                ((gsc_avg_position - gsc_position_7d_ago)::NUMERIC / gsc_position_7d_ago) * 100
            ELSE NULL 
        END as gsc_position_change_wow
    FROM gsc_with_windows
),
-- Aggregate GA4 data by page and date
ga4_daily AS (
    SELECT 
        date,
        page_path,
        SUM(ga_sessions) as ga_sessions,
        SUM(ga_engaged_sessions) as ga_engaged_sessions,
        CASE 
            WHEN SUM(ga_sessions) > 0 THEN 
                SUM(ga_engaged_sessions)::NUMERIC / SUM(ga_sessions)
            ELSE 0 
        END as ga_engagement_rate,
        SUM(ga_conversions) as ga_conversions,
        AVG(ga_bounce_rate) as ga_bounce_rate,
        AVG(ga_avg_session_duration) as ga_avg_session_duration
    FROM gsc.ga4_daily_behavior
    GROUP BY date, page_path
),
-- Calculate GA4 windows and changes
ga4_with_changes AS (
    SELECT 
        *,
        AVG(ga_conversions) OVER (
            PARTITION BY page_path 
            ORDER BY date 
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) as ga_conversions_7d_avg,
        LAG(ga_conversions, 7) OVER (
            PARTITION BY page_path 
            ORDER BY date
        ) as ga_conversions_7d_ago,
        LAG(ga_engagement_rate, 7) OVER (
            PARTITION BY page_path 
            ORDER BY date
        ) as ga_engagement_rate_7d_ago,
        CASE 
            WHEN LAG(ga_conversions, 7) OVER (PARTITION BY page_path ORDER BY date) > 0 THEN 
                ((ga_conversions - LAG(ga_conversions, 7) OVER (PARTITION BY page_path ORDER BY date))::NUMERIC 
                / LAG(ga_conversions, 7) OVER (PARTITION BY page_path ORDER BY date)) * 100
            ELSE NULL 
        END as ga_conversions_change_wow
    FROM ga4_daily
)
-- Final join
SELECT 
    gsc.date,
    gsc.property,
    gsc.page_path,
    -- GSC metrics
    gsc.gsc_clicks,
    gsc.gsc_impressions,
    gsc.gsc_ctr,
    gsc.gsc_avg_position,
    gsc.gsc_clicks_7d_avg,
    gsc.gsc_impressions_7d_avg,
    gsc.gsc_position_7d_avg,
    gsc.gsc_clicks_28d_avg,
    gsc.gsc_clicks_change_wow,
    gsc.gsc_impressions_change_wow,
    gsc.gsc_position_change_wow,
    -- GA4 metrics
    ga4.ga_sessions,
    ga4.ga_engaged_sessions,
    ga4.ga_engagement_rate,
    ga4.ga_conversions,
    ga4.ga_bounce_rate,
    ga4.ga_avg_session_duration,
    ga4.ga_conversions_7d_avg,
    ga4.ga_conversions_change_wow,
    ga4.ga_engagement_rate_7d_ago,
    -- Content metadata
    cm.last_modified_date,
    cm.publish_date,
    cm.author,
    cm.word_count,
    cm.semantic_topic,
    cm.content_type,
    -- Helper calculations
    CASE 
        WHEN gsc.gsc_avg_position BETWEEN 11 AND 20 THEN TRUE 
        ELSE FALSE 
    END as is_striking_distance,
    CASE 
        WHEN cm.last_modified_date IS NOT NULL 
        AND ABS(EXTRACT(EPOCH FROM (gsc.date - cm.last_modified_date::date))/3600) <= 48 
        THEN TRUE 
        ELSE FALSE 
    END as modified_within_48h
FROM gsc_with_changes gsc
LEFT JOIN ga4_with_changes ga4 
    ON gsc.date = ga4.date 
    AND gsc.page_path = ga4.page_path
LEFT JOIN gsc.content_metadata cm 
    ON gsc.page_path = cm.page_path
    AND gsc.property = cm.property
ORDER BY gsc.date DESC, gsc.property, gsc.page_path;

-- Create indexes on the underlying tables to optimize view performance
CREATE INDEX IF NOT EXISTS idx_fact_gsc_url_date ON gsc.fact_gsc_daily(url, date DESC);
CREATE INDEX IF NOT EXISTS idx_ga4_page_date ON gsc.ga4_daily_behavior(page_path, date DESC);

-- Grant select permission
GRANT SELECT ON gsc.vw_unified_page_performance TO gsc_user;

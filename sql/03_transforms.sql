-- =============================================
-- PHASE 4: TRANSFORMS & SEMANTIC VIEWS
-- =============================================
-- Creates analytical views for agents and LLM consumption
-- All views are created in the gsc schema

SET search_path TO gsc, public;

-- =============================================
-- VIEW 1: Page Health (28 days)
-- =============================================
-- Analyzes page performance over the last 28 days
-- Includes traffic trends, CTR health, and position changes

DROP VIEW IF EXISTS gsc.vw_page_health_28d CASCADE;

CREATE VIEW gsc.vw_page_health_28d AS
WITH date_range AS (
    SELECT 
        CURRENT_DATE - INTERVAL '28 days' AS start_date,
        CURRENT_DATE - INTERVAL '1 day' AS end_date
),
page_metrics AS (
    SELECT 
        f.property,
        f.url,
        SUM(f.clicks) AS total_clicks,
        SUM(f.impressions) AS total_impressions,
        CASE 
            WHEN SUM(f.impressions) > 0 
            THEN SUM(f.clicks)::NUMERIC / SUM(f.impressions)::NUMERIC 
            ELSE 0 
        END AS avg_ctr,
        CASE 
            WHEN SUM(f.impressions) > 0 
            THEN SUM(f.position * f.impressions)::NUMERIC / SUM(f.impressions)::NUMERIC 
            ELSE 0 
        END AS weighted_avg_position,
        COUNT(DISTINCT f.date) AS days_with_data,
        COUNT(DISTINCT f.query) AS unique_queries,
        MAX(f.date) AS last_seen_date
    FROM gsc.fact_gsc_daily f
    CROSS JOIN date_range dr
    WHERE f.date BETWEEN dr.start_date AND dr.end_date
    GROUP BY f.property, f.url
),
trend_analysis AS (
    SELECT 
        f.property,
        f.url,
        -- Week over week comparison
        SUM(CASE WHEN f.date >= CURRENT_DATE - INTERVAL '7 days' THEN f.clicks ELSE 0 END) AS clicks_last_7d,
        SUM(CASE WHEN f.date BETWEEN CURRENT_DATE - INTERVAL '14 days' AND CURRENT_DATE - INTERVAL '8 days' THEN f.clicks ELSE 0 END) AS clicks_prev_7d,
        SUM(CASE WHEN f.date >= CURRENT_DATE - INTERVAL '7 days' THEN f.impressions ELSE 0 END) AS impressions_last_7d,
        SUM(CASE WHEN f.date BETWEEN CURRENT_DATE - INTERVAL '14 days' AND CURRENT_DATE - INTERVAL '8 days' THEN f.impressions ELSE 0 END) AS impressions_prev_7d
    FROM gsc.fact_gsc_daily f
    WHERE f.date >= CURRENT_DATE - INTERVAL '28 days'
    GROUP BY f.property, f.url
)
SELECT 
    pm.property,
    pm.url,
    pm.total_clicks,
    pm.total_impressions,
    ROUND(pm.avg_ctr * 100, 2) AS ctr_percentage,
    ROUND(pm.weighted_avg_position, 1) AS avg_position,
    pm.days_with_data,
    pm.unique_queries,
    pm.last_seen_date,
    ta.clicks_last_7d,
    ta.clicks_prev_7d,
    CASE 
        WHEN ta.clicks_prev_7d > 0 
        THEN ROUND(((ta.clicks_last_7d - ta.clicks_prev_7d)::NUMERIC / ta.clicks_prev_7d) * 100, 1)
        ELSE NULL
    END AS clicks_wow_change_pct,
    ta.impressions_last_7d,
    ta.impressions_prev_7d,
    CASE 
        WHEN ta.impressions_prev_7d > 0 
        THEN ROUND(((ta.impressions_last_7d - ta.impressions_prev_7d)::NUMERIC / ta.impressions_prev_7d) * 100, 1)
        ELSE NULL
    END AS impressions_wow_change_pct,
    -- Health score (0-100)
    CASE
        WHEN pm.total_impressions = 0 THEN 0
        WHEN pm.avg_ctr >= 0.10 AND pm.weighted_avg_position <= 3 THEN 100
        WHEN pm.avg_ctr >= 0.05 AND pm.weighted_avg_position <= 5 THEN 80
        WHEN pm.avg_ctr >= 0.02 AND pm.weighted_avg_position <= 10 THEN 60
        WHEN pm.avg_ctr >= 0.01 AND pm.weighted_avg_position <= 20 THEN 40
        ELSE 20
    END AS health_score,
    -- Health status
    CASE
        WHEN pm.total_impressions = 0 THEN 'NO_DATA'
        WHEN ta.clicks_last_7d > ta.clicks_prev_7d * 1.2 THEN 'IMPROVING'
        WHEN ta.clicks_last_7d < ta.clicks_prev_7d * 0.8 THEN 'DECLINING'
        ELSE 'STABLE'
    END AS trend_status
FROM page_metrics pm
LEFT JOIN trend_analysis ta ON pm.property = ta.property AND pm.url = ta.url
WHERE pm.total_impressions > 0;

-- Create index for better query performance
CREATE INDEX IF NOT EXISTS idx_vw_page_health_property_url ON gsc.fact_gsc_daily(property, url, date);

-- =============================================
-- VIEW 2: Query Winners & Losers (28d vs Previous 28d)
-- =============================================
-- Identifies queries with significant changes in performance

DROP VIEW IF EXISTS gsc.vw_query_winners_losers_28d_vs_prev CASCADE;

CREATE VIEW gsc.vw_query_winners_losers_28d_vs_prev AS
WITH current_period AS (
    SELECT 
        property,
        query,
        SUM(clicks) AS clicks,
        SUM(impressions) AS impressions,
        AVG(position) AS avg_position,
        CASE 
            WHEN SUM(impressions) > 0 
            THEN SUM(clicks)::NUMERIC / SUM(impressions)::NUMERIC 
            ELSE 0 
        END AS ctr
    FROM gsc.fact_gsc_daily
    WHERE date BETWEEN CURRENT_DATE - INTERVAL '28 days' AND CURRENT_DATE - INTERVAL '1 day'
    GROUP BY property, query
),
previous_period AS (
    SELECT 
        property,
        query,
        SUM(clicks) AS clicks,
        SUM(impressions) AS impressions,
        AVG(position) AS avg_position,
        CASE 
            WHEN SUM(impressions) > 0 
            THEN SUM(clicks)::NUMERIC / SUM(impressions)::NUMERIC 
            ELSE 0 
        END AS ctr
    FROM gsc.fact_gsc_daily
    WHERE date BETWEEN CURRENT_DATE - INTERVAL '56 days' AND CURRENT_DATE - INTERVAL '29 days'
    GROUP BY property, query
),
comparison AS (
    SELECT 
        COALESCE(c.property, p.property) AS property,
        COALESCE(c.query, p.query) AS query,
        COALESCE(c.clicks, 0) AS current_clicks,
        COALESCE(p.clicks, 0) AS previous_clicks,
        COALESCE(c.impressions, 0) AS current_impressions,
        COALESCE(p.impressions, 0) AS previous_impressions,
        c.avg_position AS current_position,
        p.avg_position AS previous_position,
        c.ctr AS current_ctr,
        p.ctr AS previous_ctr,
        COALESCE(c.clicks, 0) - COALESCE(p.clicks, 0) AS clicks_change,
        COALESCE(c.impressions, 0) - COALESCE(p.impressions, 0) AS impressions_change,
        COALESCE(p.avg_position, 100) - COALESCE(c.avg_position, 100) AS position_improvement
    FROM current_period c
    FULL OUTER JOIN previous_period p 
        ON c.property = p.property AND c.query = p.query
)
SELECT 
    property,
    query,
    current_clicks,
    previous_clicks,
    clicks_change,
    CASE 
        WHEN previous_clicks > 0 
        THEN ROUND((clicks_change::NUMERIC / previous_clicks) * 100, 1)
        WHEN current_clicks > 0 THEN 100
        ELSE 0
    END AS clicks_change_pct,
    current_impressions,
    previous_impressions,
    impressions_change,
    CASE 
        WHEN previous_impressions > 0 
        THEN ROUND((impressions_change::NUMERIC / previous_impressions) * 100, 1)
        WHEN current_impressions > 0 THEN 100
        ELSE 0
    END AS impressions_change_pct,
    ROUND(current_position, 1) AS current_position,
    ROUND(previous_position, 1) AS previous_position,
    ROUND(position_improvement, 1) AS position_improvement,
    ROUND(current_ctr * 100, 2) AS current_ctr_pct,
    ROUND(previous_ctr * 100, 2) AS previous_ctr_pct,
    -- Classification
    CASE
        WHEN clicks_change > 10 AND position_improvement > 2 THEN 'BIG_WINNER'
        WHEN clicks_change > 5 OR position_improvement > 3 THEN 'WINNER'
        WHEN clicks_change < -10 AND position_improvement < -2 THEN 'BIG_LOSER'
        WHEN clicks_change < -5 OR position_improvement < -3 THEN 'LOSER'
        WHEN current_clicks = 0 AND previous_clicks > 5 THEN 'LOST'
        WHEN previous_clicks = 0 AND current_clicks > 5 THEN 'NEW_OPPORTUNITY'
        ELSE 'STABLE'
    END AS performance_category,
    -- Opportunity score (prioritization)
    CASE
        WHEN current_impressions > 100 AND current_position BETWEEN 4 AND 10 THEN 100
        WHEN current_impressions > 50 AND current_position BETWEEN 11 AND 20 THEN 80
        WHEN current_impressions > 20 AND current_position BETWEEN 21 AND 50 THEN 60
        ELSE 40
    END AS opportunity_score
FROM comparison
WHERE current_impressions > 0 OR previous_impressions > 0
ORDER BY ABS(clicks_change) DESC;

-- =============================================
-- VIEW 3: Directory Trends
-- =============================================
-- Analyzes performance by URL directory/section

DROP VIEW IF EXISTS gsc.vw_directory_trends CASCADE;

CREATE VIEW gsc.vw_directory_trends AS
WITH url_directories AS (
    SELECT 
        property,
        date,
        -- Extract directory from URL (everything before the last /)
        CASE 
            WHEN url LIKE '%//%' THEN
                CASE
                    WHEN SUBSTRING(url FROM POSITION('//' IN url) + 2) LIKE '%/%' THEN
                        SUBSTRING(url FROM 1 FOR 
                            LENGTH(url) - LENGTH(
                                REVERSE(SPLIT_PART(REVERSE(url), '/', 1))
                            ) - 1
                        )
                    ELSE url
                END
            ELSE url
        END AS directory,
        url,
        query,
        country,
        device,
        clicks,
        impressions,
        ctr,
        position
    FROM gsc.fact_gsc_daily
),
directory_metrics AS (
    SELECT 
        property,
        directory,
        -- Extract the path part for categorization
        CASE 
            WHEN directory LIKE '%/blog/%' THEN 'blog'
            WHEN directory LIKE '%/products/%' OR directory LIKE '%/product/%' THEN 'products'
            WHEN directory LIKE '%/categories/%' OR directory LIKE '%/category/%' THEN 'categories'
            WHEN directory LIKE '%/docs/%' OR directory LIKE '%/documentation/%' THEN 'documentation'
            WHEN directory LIKE '%/help/%' OR directory LIKE '%/support/%' THEN 'support'
            WHEN directory LIKE '%/about%' OR directory LIKE '%/team%' THEN 'about'
            WHEN directory = property OR directory = property || '/' THEN 'homepage'
            ELSE 'other'
        END AS section,
        date,
        SUM(clicks) AS daily_clicks,
        SUM(impressions) AS daily_impressions,
        COUNT(DISTINCT url) AS unique_pages,
        COUNT(DISTINCT query) AS unique_queries,
        AVG(position) AS avg_position
    FROM url_directories
    GROUP BY property, directory, date
)
SELECT 
    property,
    directory,
    section,
    -- 28-day metrics
    SUM(CASE WHEN date >= CURRENT_DATE - INTERVAL '28 days' THEN daily_clicks ELSE 0 END) AS clicks_28d,
    SUM(CASE WHEN date >= CURRENT_DATE - INTERVAL '28 days' THEN daily_impressions ELSE 0 END) AS impressions_28d,
    -- 7-day metrics
    SUM(CASE WHEN date >= CURRENT_DATE - INTERVAL '7 days' THEN daily_clicks ELSE 0 END) AS clicks_7d,
    SUM(CASE WHEN date >= CURRENT_DATE - INTERVAL '7 days' THEN daily_impressions ELSE 0 END) AS impressions_7d,
    -- Previous 7-day metrics for comparison
    SUM(CASE WHEN date BETWEEN CURRENT_DATE - INTERVAL '14 days' AND CURRENT_DATE - INTERVAL '8 days' THEN daily_clicks ELSE 0 END) AS clicks_prev_7d,
    -- Aggregated metrics
    MAX(unique_pages) AS max_unique_pages,
    MAX(unique_queries) AS max_unique_queries,
    AVG(CASE WHEN date >= CURRENT_DATE - INTERVAL '28 days' THEN avg_position END) AS avg_position_28d,
    -- Trend
    CASE
        WHEN SUM(CASE WHEN date >= CURRENT_DATE - INTERVAL '7 days' THEN daily_clicks ELSE 0 END) > 
             SUM(CASE WHEN date BETWEEN CURRENT_DATE - INTERVAL '14 days' AND CURRENT_DATE - INTERVAL '8 days' THEN daily_clicks ELSE 0 END) * 1.1 
        THEN 'GROWING'
        WHEN SUM(CASE WHEN date >= CURRENT_DATE - INTERVAL '7 days' THEN daily_clicks ELSE 0 END) < 
             SUM(CASE WHEN date BETWEEN CURRENT_DATE - INTERVAL '14 days' AND CURRENT_DATE - INTERVAL '8 days' THEN daily_clicks ELSE 0 END) * 0.9 
        THEN 'DECLINING'
        ELSE 'STABLE'
    END AS trend_direction,
    -- CTR for 28 days
    CASE 
        WHEN SUM(CASE WHEN date >= CURRENT_DATE - INTERVAL '28 days' THEN daily_impressions ELSE 0 END) > 0
        THEN ROUND(
            SUM(CASE WHEN date >= CURRENT_DATE - INTERVAL '28 days' THEN daily_clicks ELSE 0 END)::NUMERIC / 
            SUM(CASE WHEN date >= CURRENT_DATE - INTERVAL '28 days' THEN daily_impressions ELSE 0 END) * 100, 2
        )
        ELSE 0
    END AS ctr_28d_pct
FROM directory_metrics
WHERE date >= CURRENT_DATE - INTERVAL '56 days'
GROUP BY property, directory, section
HAVING SUM(CASE WHEN date >= CURRENT_DATE - INTERVAL '28 days' THEN daily_impressions ELSE 0 END) > 0
ORDER BY clicks_28d DESC;

-- =============================================
-- VIEW 4: Brand vs Non-Brand Split
-- =============================================
-- Separates branded and non-branded search performance

DROP VIEW IF EXISTS gsc.vw_brand_nonbrand_split CASCADE;

CREATE VIEW gsc.vw_brand_nonbrand_split AS
WITH brand_classification AS (
    SELECT 
        f.*,
        -- Classify queries as brand or non-brand
        -- Note: In production, replace these patterns with actual brand terms
        CASE 
            WHEN LOWER(f.query) ~ '(example|exmpl|exampl)' THEN TRUE
            WHEN LOWER(f.query) ~ '(your.?brand|your.?company)' THEN TRUE
            WHEN f.property LIKE '%example.com%' AND LOWER(f.query) ~ 'example' THEN TRUE
            ELSE FALSE
        END AS is_brand_query
    FROM gsc.fact_gsc_daily f
    WHERE f.date >= CURRENT_DATE - INTERVAL '28 days'
),
aggregated_metrics AS (
    SELECT 
        property,
        is_brand_query,
        COUNT(DISTINCT query) AS unique_queries,
        COUNT(DISTINCT url) AS unique_pages,
        SUM(clicks) AS total_clicks,
        SUM(impressions) AS total_impressions,
        AVG(position) AS avg_position,
        -- Weekly breakdown
        SUM(CASE WHEN date >= CURRENT_DATE - INTERVAL '7 days' THEN clicks ELSE 0 END) AS clicks_last_7d,
        SUM(CASE WHEN date BETWEEN CURRENT_DATE - INTERVAL '14 days' AND CURRENT_DATE - INTERVAL '8 days' THEN clicks ELSE 0 END) AS clicks_prev_7d,
        -- Device breakdown
        SUM(CASE WHEN device = 'MOBILE' THEN clicks ELSE 0 END) AS mobile_clicks,
        SUM(CASE WHEN device = 'DESKTOP' THEN clicks ELSE 0 END) AS desktop_clicks,
        SUM(CASE WHEN device = 'TABLET' THEN clicks ELSE 0 END) AS tablet_clicks
    FROM brand_classification
    GROUP BY property, is_brand_query
),
property_totals AS (
    SELECT 
        property,
        SUM(total_clicks) AS property_total_clicks,
        SUM(total_impressions) AS property_total_impressions
    FROM aggregated_metrics
    GROUP BY property
)
SELECT 
    am.property,
    CASE 
        WHEN am.is_brand_query THEN 'BRAND'
        ELSE 'NON_BRAND'
    END AS query_type,
    am.unique_queries,
    am.unique_pages,
    am.total_clicks,
    am.total_impressions,
    -- Calculate share of total
    ROUND(am.total_clicks::NUMERIC / NULLIF(pt.property_total_clicks, 0) * 100, 1) AS clicks_share_pct,
    ROUND(am.total_impressions::NUMERIC / NULLIF(pt.property_total_impressions, 0) * 100, 1) AS impressions_share_pct,
    -- CTR
    ROUND(
        CASE 
            WHEN am.total_impressions > 0 
            THEN am.total_clicks::NUMERIC / am.total_impressions * 100
            ELSE 0
        END, 2
    ) AS ctr_pct,
    ROUND(am.avg_position, 1) AS avg_position,
    -- Week over week change
    am.clicks_last_7d,
    am.clicks_prev_7d,
    CASE 
        WHEN am.clicks_prev_7d > 0 
        THEN ROUND((am.clicks_last_7d - am.clicks_prev_7d)::NUMERIC / am.clicks_prev_7d * 100, 1)
        ELSE NULL
    END AS wow_change_pct,
    -- Device split
    am.mobile_clicks,
    am.desktop_clicks,
    am.tablet_clicks,
    ROUND(am.mobile_clicks::NUMERIC / NULLIF(am.total_clicks, 0) * 100, 1) AS mobile_share_pct,
    ROUND(am.desktop_clicks::NUMERIC / NULLIF(am.total_clicks, 0) * 100, 1) AS desktop_share_pct,
    ROUND(am.tablet_clicks::NUMERIC / NULLIF(am.total_clicks, 0) * 100, 1) AS tablet_share_pct
FROM aggregated_metrics am
JOIN property_totals pt ON am.property = pt.property
ORDER BY am.property, am.is_brand_query DESC;

-- =============================================
-- DELTA SQL EXAMPLE (28d vs prev 28d)
-- =============================================
-- This is a template for calculating deltas between two periods

DROP VIEW IF EXISTS gsc.vw_delta_example CASCADE;

CREATE VIEW gsc.vw_delta_example AS
WITH current_28d AS (
    SELECT 
        property,
        url,
        SUM(clicks) AS clicks,
        SUM(impressions) AS impressions,
        AVG(position) AS avg_position,
        COUNT(DISTINCT query) AS unique_queries
    FROM gsc.fact_gsc_daily
    WHERE date BETWEEN CURRENT_DATE - INTERVAL '28 days' AND CURRENT_DATE - INTERVAL '1 day'
    GROUP BY property, url
),
previous_28d AS (
    SELECT 
        property,
        url,
        SUM(clicks) AS clicks,
        SUM(impressions) AS impressions,
        AVG(position) AS avg_position,
        COUNT(DISTINCT query) AS unique_queries
    FROM gsc.fact_gsc_daily
    WHERE date BETWEEN CURRENT_DATE - INTERVAL '56 days' AND CURRENT_DATE - INTERVAL '29 days'
    GROUP BY property, url
)
SELECT 
    COALESCE(c.property, p.property) AS property,
    COALESCE(c.url, p.url) AS url,
    c.clicks AS current_clicks,
    p.clicks AS previous_clicks,
    c.clicks - COALESCE(p.clicks, 0) AS clicks_delta,
    CASE 
        WHEN p.clicks > 0 
        THEN ROUND(((c.clicks - p.clicks)::NUMERIC / p.clicks) * 100, 1)
        ELSE NULL
    END AS clicks_delta_pct,
    c.impressions AS current_impressions,
    p.impressions AS previous_impressions,
    c.impressions - COALESCE(p.impressions, 0) AS impressions_delta,
    ROUND(c.avg_position, 1) AS current_position,
    ROUND(p.avg_position, 1) AS previous_position,
    ROUND(COALESCE(p.avg_position, 100) - COALESCE(c.avg_position, 100), 1) AS position_improvement
FROM current_28d c
FULL OUTER JOIN previous_28d p ON c.property = p.property AND c.url = p.url
WHERE c.impressions > 0 OR p.impressions > 0
ORDER BY ABS(COALESCE(c.clicks, 0) - COALESCE(p.clicks, 0)) DESC
LIMIT 100;

-- =============================================
-- CANNIBALIZATION DETECTION VIEW
-- =============================================
-- Identifies potential keyword cannibalization issues

DROP VIEW IF EXISTS gsc.vw_cannibalization_detection CASCADE;

CREATE VIEW gsc.vw_cannibalization_detection AS
WITH query_url_stats AS (
    SELECT 
        property,
        query,
        url,
        SUM(impressions) AS url_impressions,
        SUM(clicks) AS url_clicks,
        AVG(position) AS avg_position,
        -- Calculate share of impressions for this URL on this query
        SUM(impressions)::NUMERIC / SUM(SUM(impressions)) OVER (PARTITION BY property, query) AS impression_share,
        -- Count URLs ranking for this query
        COUNT(*) OVER (PARTITION BY property, query) AS urls_ranking,
        -- Rank URLs by impressions for each query
        ROW_NUMBER() OVER (PARTITION BY property, query ORDER BY SUM(impressions) DESC) AS url_rank
    FROM gsc.fact_gsc_daily
    WHERE date >= CURRENT_DATE - INTERVAL '28 days'
    GROUP BY property, query, url
    HAVING SUM(impressions) > 10  -- Filter out very low volume
),
cannibalization_candidates AS (
    SELECT 
        property,
        query,
        urls_ranking,
        -- Get the top 2 URLs for comparison
        MAX(CASE WHEN url_rank = 1 THEN url END) AS top_url_1,
        MAX(CASE WHEN url_rank = 1 THEN url_impressions END) AS top_url_1_impressions,
        MAX(CASE WHEN url_rank = 1 THEN avg_position END) AS top_url_1_position,
        MAX(CASE WHEN url_rank = 1 THEN impression_share END) AS top_url_1_share,
        MAX(CASE WHEN url_rank = 2 THEN url END) AS top_url_2,
        MAX(CASE WHEN url_rank = 2 THEN url_impressions END) AS top_url_2_impressions,
        MAX(CASE WHEN url_rank = 2 THEN avg_position END) AS top_url_2_position,
        MAX(CASE WHEN url_rank = 2 THEN impression_share END) AS top_url_2_share,
        SUM(url_impressions) AS total_query_impressions,
        AVG(avg_position) AS avg_query_position
    FROM query_url_stats
    WHERE urls_ranking > 1  -- Only queries with multiple URLs
    GROUP BY property, query, urls_ranking
)
SELECT 
    property,
    query,
    urls_ranking AS competing_urls_count,
    top_url_1,
    ROUND(top_url_1_impressions, 0) AS url_1_impressions,
    ROUND(top_url_1_position, 1) AS url_1_position,
    ROUND(top_url_1_share * 100, 1) AS url_1_share_pct,
    top_url_2,
    ROUND(top_url_2_impressions, 0) AS url_2_impressions,
    ROUND(top_url_2_position, 1) AS url_2_position,
    ROUND(top_url_2_share * 100, 1) AS url_2_share_pct,
    ROUND(total_query_impressions, 0) AS total_impressions,
    ROUND(avg_query_position, 1) AS avg_position,
    -- Cannibalization severity score
    CASE
        WHEN top_url_1_share < 0.6 AND top_url_2_share > 0.25 
             AND ABS(top_url_1_position - top_url_2_position) < 5 THEN 'HIGH'
        WHEN top_url_1_share < 0.7 AND top_url_2_share > 0.15 
             AND ABS(top_url_1_position - top_url_2_position) < 10 THEN 'MEDIUM'
        WHEN urls_ranking > 2 THEN 'LOW'
        ELSE 'MINIMAL'
    END AS cannibalization_severity,
    -- Recommended action
    CASE
        WHEN top_url_1_share < 0.6 AND top_url_2_share > 0.25 THEN 'CONSOLIDATE_CONTENT'
        WHEN ABS(top_url_1_position - top_url_2_position) < 3 THEN 'DIFFERENTIATE_CONTENT'
        WHEN urls_ranking > 3 THEN 'REVIEW_SITE_STRUCTURE'
        ELSE 'MONITOR'
    END AS recommended_action
FROM cannibalization_candidates
WHERE total_query_impressions > 100  -- Focus on queries with meaningful volume
ORDER BY total_query_impressions DESC, cannibalization_severity;

-- =============================================
-- MATERIALIZED VIEW FOR PERFORMANCE (Optional)
-- =============================================
-- For better performance on large datasets, consider materializing heavy views

-- Example: Materialize the page health view
-- CREATE MATERIALIZED VIEW gsc.mv_page_health_28d AS
-- SELECT * FROM gsc.vw_page_health_28d;
-- 
-- CREATE UNIQUE INDEX ON gsc.mv_page_health_28d (property, url);
-- 
-- -- Refresh periodically (could be scheduled)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY gsc.mv_page_health_28d;

-- =============================================
-- HELPER FUNCTIONS FOR TRANSFORMS
-- =============================================

-- Function to calculate period-over-period change
CREATE OR REPLACE FUNCTION gsc.calculate_period_change(
    current_value NUMERIC,
    previous_value NUMERIC
) RETURNS NUMERIC AS $$
BEGIN
    IF previous_value IS NULL OR previous_value = 0 THEN
        IF current_value > 0 THEN
            RETURN 100; -- 100% increase from 0
        ELSE
            RETURN 0;
        END IF;
    END IF;
    RETURN ROUND(((current_value - previous_value) / previous_value) * 100, 2);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to classify trend
CREATE OR REPLACE FUNCTION gsc.classify_trend(
    change_pct NUMERIC
) RETURNS TEXT AS $$
BEGIN
    IF change_pct > 20 THEN
        RETURN 'STRONG_GROWTH';
    ELSIF change_pct > 5 THEN
        RETURN 'GROWTH';
    ELSIF change_pct > -5 THEN
        RETURN 'STABLE';
    ELSIF change_pct > -20 THEN
        RETURN 'DECLINE';
    ELSE
        RETURN 'STRONG_DECLINE';
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =============================================
-- SUMMARY STATISTICS TABLE (For monitoring)
-- =============================================

DROP TABLE IF EXISTS gsc.transform_summary CASCADE;

CREATE TABLE gsc.transform_summary (
    summary_date DATE DEFAULT CURRENT_DATE,
    view_name VARCHAR(100),
    row_count INTEGER,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (summary_date, view_name)
);

-- Populate summary (would be scheduled)
INSERT INTO gsc.transform_summary (view_name, row_count)
SELECT 'vw_page_health_28d', COUNT(*) FROM gsc.vw_page_health_28d
ON CONFLICT (summary_date, view_name) DO UPDATE SET 
    row_count = EXCLUDED.row_count,
    last_updated = CURRENT_TIMESTAMP;

INSERT INTO gsc.transform_summary (view_name, row_count)
SELECT 'vw_query_winners_losers_28d_vs_prev', COUNT(*) FROM gsc.vw_query_winners_losers_28d_vs_prev
ON CONFLICT (summary_date, view_name) DO UPDATE SET 
    row_count = EXCLUDED.row_count,
    last_updated = CURRENT_TIMESTAMP;

INSERT INTO gsc.transform_summary (view_name, row_count)
SELECT 'vw_directory_trends', COUNT(*) FROM gsc.vw_directory_trends
ON CONFLICT (summary_date, view_name) DO UPDATE SET 
    row_count = EXCLUDED.row_count,
    last_updated = CURRENT_TIMESTAMP;

INSERT INTO gsc.transform_summary (view_name, row_count)
SELECT 'vw_brand_nonbrand_split', COUNT(*) FROM gsc.vw_brand_nonbrand_split
ON CONFLICT (summary_date, view_name) DO UPDATE SET 
    row_count = EXCLUDED.row_count,
    last_updated = CURRENT_TIMESTAMP;

-- Grant permissions
GRANT SELECT ON ALL TABLES IN SCHEMA gsc TO gsc_user;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA gsc TO gsc_user;

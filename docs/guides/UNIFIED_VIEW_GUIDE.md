# Unified View Guide
## Understanding vw_unified_page_performance

---

## Overview

The `vw_unified_page_performance` view is the **heart of the Hybrid Plan**. It solves the data silo problem by joining GSC and GA4 metrics into a single queryable view.

### Why "Unified"?

**Before (Siloed Approach):**
```
┌──────────────┐         ┌──────────────┐
│ GSC only     │         │ GA4 only     │
│ • Can't see  │   ✗     │ • Can't see  │
│   conversions│         │   rankings   │
└──────────────┘         └──────────────┘
     Can detect:             Can detect:
     • Traffic drops          • Conv. drops
     ✗ Can't correlate ✗
```

**After (Hybrid Approach):**
```
┌─────────────────────────────────────┐
│    vw_unified_page_performance      │
│                                     │
│  GSC Metrics  ⊕  GA4 Metrics        │
│  • Clicks         • Sessions        │
│  • Impressions    • Conversions     │
│  • Position       • Engagement      │
│                                     │
│  ✓ Correlated insights possible     │
└─────────────────────────────────────┘
```

---

## Schema

### Core Fields

```sql
SELECT 
    -- Identification
    date,
    property,
    page_path,
    
    -- GSC Metrics (Current)
    gsc_clicks,
    gsc_impressions,
    gsc_ctr,
    gsc_position,
    
    -- GA4 Metrics (Current)
    ga_sessions,
    ga_engagement_rate,
    ga_bounce_rate,
    ga_conversions,
    ga_avg_session_duration,
    ga_page_views,
    
    -- Historical Values (7 days ago)
    gsc_clicks_7d_ago,
    gsc_impressions_7d_ago,
    gsc_position_7d_ago,
    ga_conversions_7d_ago,
    
    -- Historical Values (28 days ago)
    gsc_clicks_28d_ago,
    gsc_impressions_28d_ago,
    ga_conversions_28d_ago,
    
    -- Rolling Averages
    gsc_clicks_7d_avg,
    gsc_clicks_28d_avg,
    ga_conversions_7d_avg,
    ga_conversions_28d_avg,
    
    -- Week-over-Week Changes (%)
    gsc_clicks_change_wow,
    gsc_impressions_change_wow,
    gsc_position_change_wow,
    ga_conversions_change_wow,
    ga_engagement_rate_change_wow,
    
    -- Month-over-Month Changes (%)
    gsc_clicks_change_mom,
    gsc_impressions_change_mom,
    ga_conversions_change_mom,
    
    -- Derived Metrics
    opportunity_index,        -- (impressions - clicks) / impressions
    conversion_efficiency,    -- conversions per 100 clicks
    quality_score            -- position × engagement weighted

FROM gsc.vw_unified_page_performance;
```

---

## Construction Logic

### Step 1: Aggregate GSC Data
```sql
-- Rollup device/country/query dimensions to page level
gsc_aggregated AS (
    SELECT 
        date,
        property,
        url as page_path,
        SUM(clicks) as clicks,
        SUM(impressions) as impressions,
        AVG(position) as avg_position,
        CTR = clicks / impressions
    FROM gsc.fact_gsc_daily
    GROUP BY date, property, url
)
```

**Why aggregate?** GSC stores data at query×page×device×country granularity. We need page-level for GA4 join.

### Step 2: Join GSC and GA4
```sql
unified_base AS (
    SELECT 
        COALESCE(g.date, ga.date) as date,
        COALESCE(g.property, ga.property) as property,
        COALESCE(g.page_path, ga.page_path) as page_path,
        -- GSC metrics
        COALESCE(g.clicks, 0) as gsc_clicks,
        COALESCE(g.impressions, 0) as gsc_impressions,
        -- GA4 metrics
        COALESCE(ga.sessions, 0) as ga_sessions,
        COALESCE(ga.conversions, 0) as ga_conversions
    FROM gsc_aggregated g
    FULL OUTER JOIN gsc.fact_ga4_daily ga 
        ON g.date = ga.date 
        AND g.property = ga.property 
        AND g.page_path = ga.page_path
)
```

**Key decision: FULL OUTER JOIN**
- Handles missing GA4 data (fills with 0)
- Handles pages not in GSC but in GA4
- Zero data loss

### Step 3: Time-Series Calculations
```sql
time_series_calcs AS (
    SELECT 
        *,
        -- Historical values (LAG function)
        LAG(gsc_clicks, 7) OVER w_page as gsc_clicks_7d_ago,
        LAG(gsc_clicks, 28) OVER w_page as gsc_clicks_28d_ago,
        
        -- Rolling averages (AVG function)
        AVG(gsc_clicks) OVER w_page_7d as gsc_clicks_7d_avg,
        AVG(gsc_clicks) OVER w_page_28d as gsc_clicks_28d_avg
        
    FROM unified_base
    WINDOW 
        w_page AS (PARTITION BY property, page_path ORDER BY date),
        w_page_7d AS (PARTITION BY property, page_path ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),
        w_page_28d AS (PARTITION BY property, page_path ORDER BY date ROWS BETWEEN 27 PRECEDING AND CURRENT ROW)
)
```

### Step 4: Percentage Changes
```sql
SELECT 
    *,
    -- Week-over-Week change
    CASE 
        WHEN gsc_clicks_7d_ago > 0 THEN 
            ((gsc_clicks - gsc_clicks_7d_ago)::NUMERIC / gsc_clicks_7d_ago) * 100
        ELSE NULL
    END as gsc_clicks_change_wow
    
FROM time_series_calcs;
```

**Why NULL for first 7 days?** Need historical data for comparison.

---

## Query Examples

### Example 1: Correlated Drops (High Severity Risks)
```sql
-- Find pages where BOTH clicks and conversions dropped >20%
SELECT 
    page_path,
    gsc_clicks,
    gsc_clicks_change_wow,
    ga_conversions,
    ga_conversions_change_wow
FROM gsc.vw_unified_page_performance
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
    AND gsc_clicks_change_wow < -20
    AND ga_conversions_change_wow < -20
ORDER BY gsc_clicks_change_wow;
```

**Output:**
```
page_path          | gsc_clicks | change_wow | ga_conversions | change_wow
/product/abc       | 450        | -35.2%     | 12            | -41.7%
/guide/xyz         | 820        | -28.1%     | 25            | -32.0%
```

**Insight:** These pages need immediate attention — losing both traffic AND conversions.

---

### Example 2: Intent Mismatches (Opportunities)
```sql
-- High impressions but low CTR and conversions
SELECT 
    page_path,
    gsc_impressions,
    gsc_ctr,
    ga_conversions,
    conversion_efficiency,
    opportunity_index
FROM gsc.vw_unified_page_performance
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
    AND gsc_impressions > 1000
    AND gsc_ctr < 2.0
    AND conversion_efficiency < 1.0
ORDER BY opportunity_index DESC;
```

**Output:**
```
page_path     | impressions | ctr  | conversions | conv_eff | opp_index
/blog/seo     | 15,000      | 1.2% | 3          | 0.17%    | 98.8
/tools/free   | 8,500       | 1.8% | 5          | 0.33%    | 98.2
```

**Insight:** High visibility, but poor engagement. Optimize title/meta descriptions for better CTR, then landing page for conversions.

---

### Example 3: Impression Spikes (Capture Opportunities)
```sql
-- Pages with sudden visibility increase
SELECT 
    page_path,
    gsc_impressions,
    gsc_impressions_change_wow,
    gsc_ctr,
    gsc_position
FROM gsc.vw_unified_page_performance
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
    AND gsc_impressions_change_wow > 50
ORDER BY gsc_impressions_change_wow DESC;
```

**Output:**
```
page_path          | impressions | change_wow | ctr  | position
/guide/new-feature | 12,000      | +185.3%    | 1.5% | 8.2
/blog/trending     | 5,400       | +92.7%     | 2.1% | 12.5
```

**Insight:** Google increased visibility. Optimize CTR now to capture traffic surge.

---

## Performance Considerations

### Query Optimization

**Slow query warning:**
```sql
-- ❌ BAD: Scans full table
SELECT * FROM gsc.vw_unified_page_performance
WHERE page_path LIKE '%product%';
```

**Fast query:**
```sql
-- ✅ GOOD: Uses indexes
SELECT * FROM gsc.vw_unified_page_performance
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
    AND property = 'sc-domain:example.com';
```

### Indexes
```sql
-- Underlying table indexes
CREATE INDEX idx_fact_gsc_date_property_url 
    ON gsc.fact_gsc_daily(date DESC, property, url);

CREATE INDEX idx_fact_ga4_date_property_page 
    ON gsc.fact_ga4_daily(date DESC, property, page_path);
```

### Materialized Views
For very large datasets (>1M rows), consider materialized views:
```sql
CREATE MATERIALIZED VIEW gsc.mv_unified_page_performance AS
SELECT * FROM gsc.vw_unified_page_performance;

-- Refresh daily
REFRESH MATERIALIZED VIEW CONCURRENTLY gsc.mv_unified_page_performance;
```

---

## Data Quality Validation

### Run Built-in Validation
```sql
SELECT * FROM gsc.validate_unified_view_time_series();
```

**Expected checks:**
- ✅ Total rows > 0
- ✅ WoW calculations populated (after 7 days)
- ✅ Recent data (last 7 days exists)
- ✅ Historical depth (30+ days for full WoW/MoM)
- ✅ No extreme outliers (>1000% changes)
- ℹ️ Anomalies detectable count
- ℹ️ Opportunities detectable count

### Manual Checks
```sql
-- Check for NULL handling
SELECT 
    COUNT(*) as total_rows,
    COUNT(*) FILTER (WHERE gsc_clicks IS NULL) as gsc_nulls,
    COUNT(*) FILTER (WHERE ga_conversions IS NULL) as ga4_nulls,
    COUNT(*) FILTER (WHERE gsc_clicks_change_wow IS NULL) as wow_nulls
FROM gsc.vw_unified_page_performance
WHERE date >= CURRENT_DATE - INTERVAL '7 days';
```

**Expected:**
- `gsc_nulls = 0` (COALESCE fills with 0)
- `ga4_nulls = 0` (COALESCE fills with 0)
- `wow_nulls > 0` for first 7 days (expected)

---

## Troubleshooting

### Issue: View returns no data
**Check:**
```sql
SELECT COUNT(*) FROM gsc.fact_gsc_daily;
SELECT COUNT(*) FROM gsc.fact_ga4_daily;
```

**Solution:** Ingest data first
```bash
python ingestors/api/gsc_api_ingestor.py --date-start 2024-11-01
```

---

### Issue: WoW calculations are NULL
**Reason:** Need 7+ days of data

**Check:**
```sql
SELECT COUNT(DISTINCT date) FROM gsc.fact_gsc_daily;
```

**Solution:** Backfill historical data
```bash
python scripts/backfill_historical.py --days 30
```

---

### Issue: Slow queries
**Check execution plan:**
```sql
EXPLAIN ANALYZE
SELECT * FROM gsc.vw_unified_page_performance
WHERE date >= CURRENT_DATE - INTERVAL '7 days';
```

**Solution:** Ensure indexes exist
```sql
-- Run index creation
\i sql/05_unified_view.sql
```

---

## Best Practices

### 1. Always filter by date
```sql
-- ✅ GOOD
WHERE date >= CURRENT_DATE - INTERVAL '30 days'

-- ❌ BAD (scans everything)
WHERE TRUE
```

### 2. Use helper views for common queries
```sql
-- Latest values only (faster)
SELECT * FROM gsc.vw_unified_page_performance_latest
WHERE property = 'sc-domain:example.com';

-- Pre-filtered anomalies (faster)
SELECT * FROM gsc.vw_unified_anomalies
WHERE anomaly_severity = 'high';
```

### 3. Detectors should read from unified view
```python
# ✅ CORRECT (Hybrid Plan)
query = "SELECT * FROM gsc.vw_unified_page_performance WHERE ..."

# ❌ WRONG (GSC-only, breaks hybrid architecture)
query = "SELECT * FROM gsc.fact_gsc_daily WHERE ..."
```

---

## Advanced: Extending the View

### Adding Custom Metrics
```sql
-- Example: Add "Search Intent Score"
CREATE OR REPLACE VIEW gsc.vw_unified_page_performance_extended AS
SELECT 
    *,
    -- Custom metric
    CASE 
        WHEN gsc_position <= 3 AND ga_engagement_rate > 70 THEN 'high_intent'
        WHEN gsc_position <= 10 AND ga_engagement_rate > 50 THEN 'medium_intent'
        ELSE 'low_intent'
    END as search_intent_score
FROM gsc.vw_unified_page_performance;
```

### Integration with CMS Data
```sql
-- Join with content metadata
CREATE VIEW gsc.vw_unified_with_content AS
SELECT 
    u.*,
    c.content_type,
    c.author,
    c.last_modified,
    c.word_count
FROM gsc.vw_unified_page_performance u
LEFT JOIN cms.content_metadata c 
    ON u.page_path = c.page_path;
```

---

## Summary

### The Unified View enables:
✅ **Correlated insights** (clicks + conversions)  
✅ **Intent mismatch detection** (high impressions, low conversions)  
✅ **Trend analysis** (WoW, MoM changes)  
✅ **Root cause analysis** (with CMS metadata)  
✅ **Zero data loss** (FULL OUTER JOIN)  

### Key Takeaways:
- Always query from `vw_unified_page_performance`, not raw tables
- Use date filters for performance
- Expect NULLs in first 7 days (WoW) and 28 days (MoM)
- Validate with `gsc.validate_unified_view_time_series()`

---

**Next Steps:**
- [Write custom detectors](DETECTOR_GUIDE.md) using the unified view
- [Understand insight engine](../docs/ARCHITECTURE.md#insight-engine)
- [Deploy to production](../deployment/PRODUCTION_GUIDE.md)

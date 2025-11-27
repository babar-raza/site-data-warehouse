# Grafana Dashboard Guide

**Version:** 1.0
**Last Updated:** 2025
**Audience:** All Users

---

## Table of Contents

1. [Dashboard Overview](#dashboard-overview)
2. [GSC Data - Overview Dashboard](#gsc-data---overview-dashboard)
3. [GA4 Analytics - Overview Dashboard](#ga4-analytics---overview-dashboard)
4. [Hybrid Analytics - GSC + GA4 Unified Dashboard](#hybrid-analytics---gsc--ga4-unified-dashboard)
5. [Common Metrics Glossary](#common-metrics-glossary)
6. [Using Dashboards Effectively](#using-dashboards-effectively)
7. [Troubleshooting](#troubleshooting)

---

## Dashboard Overview

The system provides three complementary dashboards:

### 1. GSC Data - Overview (`gsc-overview`)
**Purpose**: Monitor organic search performance
**Data Source**: Google Search Console only
**Best For**: SEO teams tracking visibility, rankings, and click-through rates
**Refresh Rate**: 5 minutes

### 2. GA4 Analytics - Overview (`ga4-overview`)
**Purpose**: Monitor user behavior and conversions
**Data Source**: Google Analytics 4 only
**Best For**: Marketing teams tracking sessions, engagement, and conversions
**Refresh Rate**: 5 minutes

### 3. Hybrid Analytics - GSC + GA4 Unified (`hybrid-overview`)
**Purpose**: Complete funnel analysis from search impression to conversion
**Data Source**: GSC + GA4 unified view
**Best For**: Cross-functional teams needing holistic performance insights
**Refresh Rate**: 5 minutes

---

## GSC Data - Overview Dashboard

**Access**: [http://localhost:3000](http://localhost:3000) → GSC Data - Overview
**Time Range**: Last 90 days (configurable)
**UID**: `gsc-overview`

### Dashboard Layout

```
┌──────────────────────────────────────────────────────┐
│  Total Clicks │Total Impr. │ Avg CTR  │ Avg Position│
│   (30d KPI)   │  (30d KPI) │ (30d KPI) │  (30d KPI)  │
├──────────────────────────────────────────────────────┤
│            Clicks Over Time (Line Chart)             │
├──────────────────────────────────────────────────────┤
│  Top Performing Pages  │     Top Queries             │
│     (Table)            │      (Table)                │
├──────────────────────────────────────────────────────┤
│           Recent Insights (Last 10)                  │
│                 (Table)                              │
├──────────────────────────────────────────────────────┤
│ Impressions Over Time  │    CTR Trend                │
│    (Line Chart)        │   (Line Chart)              │
└──────────────────────────────────────────────────────┘
```

### Panels Detailed

#### Panel 1: Total Clicks (Last 30 Days)
**Type**: Stat (KPI)
**Position**: Top-left
**Grid**: 6 columns × 4 rows

**What It Shows**:
Total number of clicks from Google Search in the last 30 days

**Query**:
```sql
SELECT SUM(clicks)::bigint as "Total Clicks"
FROM gsc.fact_gsc_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
```

**Thresholds**:
- 🟢 Green: ≥100,000 clicks
- 🟡 Yellow: 10,000-99,999 clicks
- 🔴 Red: <10,000 clicks

**Interpretation**:
- **Increasing**: Good, organic visibility growing
- **Stable**: Normal, consistent performance
- **Decreasing**: Investigate ranking drops or technical issues

**Related Metrics**:
- Compare to Total Impressions (are impressions growing but clicks not? = CTR problem)
- Check Top Performing Pages to see traffic distribution

---

#### Panel 2: Total Impressions (Last 30 Days)
**Type**: Stat (KPI)
**Position**: Top-center
**Grid**: 6 columns × 4 rows

**What It Shows**:
Total number of times pages appeared in Google Search results (regardless of clicks)

**Query**:
```sql
SELECT SUM(impressions)::bigint as "Total Impressions"
FROM gsc.fact_gsc_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
```

**Thresholds**:
- 🔵 Blue: Any value (informational)

**Interpretation**:
- **High Impressions + Low CTR**: Opportunity to improve meta descriptions and titles
- **Low Impressions**: Need more content or better SEO targeting
- **Spikes**: New content indexed or ranking boost

**Relationship to Clicks**:
Impressions ÷ Clicks = CTR
Example: 100,000 impressions, 5,000 clicks = 5% CTR

---

#### Panel 3: Average CTR (Last 30 Days)
**Type**: Stat (KPI)
**Position**: Top-center-right
**Grid**: 6 columns × 4 rows
**Unit**: Percentage

**What It Shows**:
Average click-through rate: what percentage of impressions result in clicks

**Query**:
```sql
SELECT ROUND(AVG(ctr)::numeric, 4) as "CTR"
FROM gsc.fact_gsc_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days' AND ctr > 0
```

**Thresholds**:
- 🟢 Green: ≥5% (excellent)
- 🟡 Yellow: 2-4.9% (good)
- 🔴 Red: <2% (needs improvement)

**Interpretation**:
- **High CTR (>5%)**: Compelling titles and descriptions, good ranking positions
- **Medium CTR (2-5%)**: Normal, room for optimization
- **Low CTR (<2%)**: Poor meta tags, low ranking positions, or brand awareness issues

**Optimization Strategies**:
- CTR <2%: Rewrite meta titles and descriptions
- CTR good but position low: Focus on improving rankings
- CTR declining over time: Check for SERP feature changes

---

#### Panel 4: Average Position (Last 30 Days)
**Type**: Stat (KPI)
**Position**: Top-right
**Grid**: 6 columns × 4 rows

**What It Shows**:
Average ranking position in Google Search results (1 = top, 10 = bottom of page 1, 20 = page 2, etc.)

**Query**:
```sql
SELECT ROUND(AVG(position)::numeric, 1) as "Position"
FROM gsc.fact_gsc_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days' AND position > 0
```

**Thresholds**:
- 🟢 Green: ≤10 (page 1)
- 🟡 Yellow: 10-20 (page 1-2)
- 🔴 Red: >20 (page 2+)

**Interpretation**:
- **Position 1-3**: Premium spots, high visibility
- **Position 4-10**: Good, page 1 visibility
- **Position 11-20**: Page 2, some visibility
- **Position 21+**: Low visibility, needs SEO work

**Important Note**:
Position is weighted by impressions, so high-impression keywords affect this more than low-impression ones.

---

#### Panel 5: Clicks Over Time
**Type**: Time Series (Line Chart)
**Position**: Second row
**Grid**: Full width (24 columns) × 8 rows

**What It Shows**:
Daily trend of total clicks over the selected time range

**Query**:
```sql
SELECT date AS time, SUM(clicks) AS value
FROM gsc.fact_gsc_daily
WHERE $__timeFilter(date)
GROUP BY date
ORDER BY date
```

**Features**:
- Smooth line interpolation
- Fill opacity: 10%
- Interactive hover tooltips
- Zoom and pan enabled

**Analysis Patterns**:

**Pattern 1: Weekly Seasonality**
```
Mon  Tue  Wed  Thu  Fri  Sat  Sun
 ▲    ▲    ▲    ▲    ▲    ▼    ▼
```
- **Normal**: B2B sites typically see weekday peaks, weekend drops
- **Action**: None needed, just be aware of the pattern

**Pattern 2: Sudden Drop**
```
────────────┐
            └───────
```
- **Causes**: Algorithm update, technical issue, de-indexing
- **Action**: Check Recent Insights panel, investigate recent changes

**Pattern 3: Gradual Decline**
```
────┐
    └──┐
       └───
```
- **Causes**: Increased competition, content aging, ranking slippage
- **Action**: Review top pages losing traffic, refresh content

**Pattern 4: Spike**
```
        ▲
       ╱ ╲
──────    ────
```
- **Causes**: Viral content, news mention, seasonal event
- **Action**: Identify which pages spiked, create more similar content

---

#### Panel 6: Top Performing Pages (Last 30 Days)
**Type**: Table
**Position**: Third row, left half
**Grid**: 12 columns × 8 rows
**Rows**: Top 50 pages

**What It Shows**:
Pages ranked by total clicks with all key metrics

**Query**:
```sql
SELECT
    url as full_url,
    SUM(clicks) as clicks,
    SUM(impressions) as impressions,
    ROUND((SUM(clicks)::numeric / NULLIF(SUM(impressions), 0)), 4) as ctr,
    ROUND(AVG(position)::numeric, 1) as avg_position
FROM gsc.fact_gsc_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days' AND clicks > 0
GROUP BY url
ORDER BY clicks DESC
LIMIT 50
```

**Columns**:

1. **full_url**
   - Full page URL
   - Clickable (opens in new tab)

2. **clicks**
   - Total clicks for this page
   - Color-coded background (heat map)

3. **impressions**
   - Total impressions for this page
   - Color-coded background

4. **ctr**
   - CTR percentage (clicks/impressions × 100)
   - Unit: percentunit (shows as %)
   - Color-coded background

5. **avg_position**
   - Average ranking position
   - 1 decimal place

**How to Use**:

**Find Traffic Drivers**:
Top 3-5 pages typically drive 50%+ of traffic. Focus optimization here.

**Identify Optimization Opportunities**:
- High impressions + Low CTR → Improve meta tags
- High position + Low CTR → Check SERP features stealing clicks
- Low position + High CTR → Small ranking boost = big traffic gain

**Monitor Content Performance**:
Track if your best pages stay at the top or if rankings shift.

**Example Analysis**:
```
Page: /blog/python-tutorial
Clicks: 5,234
Impressions: 123,456
CTR: 4.24%
Position: 3.2

Analysis:
✅ Good position (page 1)
✅ Strong CTR (>4%)
💡 Opportunity: Position 3.2 → if we improve to position 1-2,
   could gain 30-50% more clicks
```

---

#### Panel 7: Top Queries (Last 30 Days)
**Type**: Table
**Position**: Third row, right half
**Grid**: 12 columns × 8 rows
**Rows**: Top 50 queries

**What It Shows**:
Search terms that drive traffic to your site

**Query**:
```sql
SELECT
    query,
    SUM(clicks) as clicks,
    SUM(impressions) as impressions,
    ROUND((SUM(clicks)::numeric / NULLIF(SUM(impressions), 0)), 4) as ctr,
    ROUND(AVG(position)::numeric, 1) as avg_position
FROM gsc.fact_gsc_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
  AND query IS NOT NULL
  AND query != ''
  AND clicks > 0
GROUP BY query
ORDER BY clicks DESC
LIMIT 50
```

**Columns**: Same as Top Performing Pages

**How to Use**:

**Keyword Strategy**:
- Identify your best-performing keywords
- Find keyword patterns (e.g., "how to X", "X tutorial")
- Create more content around similar queries

**Content Gaps**:
- Queries with high impressions but low clicks → create dedicated pages
- Queries with good CTR but low impressions → need more content

**Example Analysis**:
```
Query: "python pandas tutorial"
Clicks: 1,234
Impressions: 45,678
CTR: 2.7%
Position: 8.5

Analysis:
📊 High search volume (45K impressions)
⚠️ Page 1 but low position (8.5)
💡 Opportunity: Improve from position 8.5 to position 3-5
   → Could 2-3x clicks to 2,500-3,000/month
💡 CTR is decent (2.7%), focus on rankings not meta tags
```

---

#### Panel 8: Recent Insights (Last 10)
**Type**: Table
**Position**: Fourth row
**Grid**: Full width (24 columns) × 8 rows
**Rows**: 10 most recent insights

**What It Shows**:
Automatically detected insights (anomalies, opportunities, risks) from the Insight Engine

**Query**:
```sql
SELECT
    entity_id as page,
    category,
    severity,
    title,
    description,
    generated_at
FROM gsc.insights
ORDER BY generated_at DESC
LIMIT 10
```

**Columns**:

1. **page**: Which page/entity the insight relates to
2. **category**: risk, opportunity, diagnosis, trend
3. **severity**: low, medium, high
4. **title**: Short summary
5. **description**: Detailed explanation
6. **generated_at**: When insight was detected

**Insight Categories**:

**🔴 Risk** (Problems):
- Traffic drops
- Ranking losses
- Conversion decreases

**🟢 Opportunity** (Growth):
- Impression surges
- High-potential pages
- Low-hanging fruit optimizations

**🔵 Diagnosis** (Root Cause):
- Why did X happen?
- Correlation analysis
- Technical issue identification

**🟡 Trend** (Patterns):
- Long-term changes
- Seasonal patterns
- Emerging topics

**How to Use**:

1. **Daily Review**: Check this panel every morning
2. **Prioritize**: High severity risks first, then opportunities
3. **Click Through**: Use page column to investigate affected pages
4. **Track Status**: Insights move through workflow (new → investigating → resolved)

**Example Insight**:
```
Page: /products/widget-pro
Category: risk
Severity: high
Title: "Traffic & Conversion Drop"
Description: "Page experiencing significant decline in both traffic
             and conversions. Clicks down 45.2%, conversions down 32.1%
             week-over-week."
Generated: 2024-11-20 08:23:15

Action:
1. Check Recent Insights for diagnosis
2. Review page for technical issues
3. Check competitors for new content
4. Consider updating content
```

---

#### Panel 9: Impressions Over Time
**Type**: Time Series (Line Chart)
**Position**: Fifth row, left half
**Grid**: 12 columns × 8 rows

**What It Shows**:
Daily trend of total impressions

**Query**:
```sql
SELECT date AS time, SUM(impressions) AS value
FROM gsc.fact_gsc_daily
WHERE $__timeFilter(date)
GROUP BY date
ORDER BY date
```

**Usage**:
- Track visibility trends
- Identify indexing issues (sudden drops to zero)
- Monitor content publishing impact

---

#### Panel 10: CTR Trend
**Type**: Time Series (Line Chart)
**Position**: Fifth row, right half
**Grid**: 12 columns × 8 rows
**Unit**: Percentage

**What It Shows**:
Daily trend of average CTR

**Query**:
```sql
SELECT date AS time, AVG(ctr) AS value
FROM gsc.fact_gsc_daily
WHERE $__timeFilter(date) AND ctr > 0
GROUP BY date
ORDER BY date
```

**Usage**:
- Monitor impact of meta tag changes
- Identify SERP feature impacts
- Track seasonal CTR variations

**Normal Ranges**:
- 2-5% CTR: Normal for most sites
- >5% CTR: Excellent
- <2% CTR: Needs optimization

---

## GA4 Analytics - Overview Dashboard

**Access**: [http://localhost:3000](http://localhost:3000) → GA4 Analytics - Overview
**Time Range**: Last 30 days (configurable)
**UID**: `ga4-overview`

### Dashboard Layout

```
┌──────────────────────────────────────────────────────┐
│Total Sessions│Total Conv. │Avg Engage. │Avg Bounce   │
│   (30d KPI)  │  (30d KPI) │  (30d KPI) │ (30d KPI)   │
├──────────────────────────────────────────────────────┤
│Sessions Over Time    │  GSC Clicks vs GA4 Sessions   │
│   (Line Chart)       │       (Comparison Chart)      │
├──────────────────────────────────────────────────────┤
│      Top Converting Pages (Last 30 Days)             │
│                  (Table)                             │
└──────────────────────────────────────────────────────┘
```

### Panels Detailed

#### Panel 1: Total Sessions (Last 30 Days)
**Type**: Stat (KPI)

**What It Shows**:
Total number of user sessions (visits) to your site

**Query**:
```sql
SELECT SUM(sessions)::bigint as "Total Sessions"
FROM gsc.fact_ga4_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
```

**Thresholds**:
- 🟢 Green: ≥10,000 sessions
- 🟡 Yellow: 5,000-9,999 sessions
- 🟠 Orange: <5,000 sessions

**What Is a Session**:
A session is a period of user activity on your site. It includes all pageviews, events, and interactions within a time window (default: 30 minutes of inactivity ends a session).

**Interpretation**:
- One user can have multiple sessions
- Higher sessions = more traffic
- Compare to GSC clicks to see click-to-session conversion rate

---

#### Panel 2: Total Conversions (Last 30 Days)
**Type**: Stat (KPI)

**What It Shows**:
Total number of conversion events (goals achieved)

**Query**:
```sql
SELECT SUM(conversions)::bigint as "Total Conversions"
FROM gsc.fact_ga4_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
```

**Thresholds**:
- 🟢 Green: ≥100 conversions
- 🔵 Blue: Any value (informational)

**What Is a Conversion**:
A conversion is a completed user action that matters to your business:
- Purchase completed
- Form submitted
- Newsletter signup
- File downloaded
- Video watched (>X%)

**Interpretation**:
- More conversions = better business outcomes
- Low conversions despite high traffic → funnel problem
- Track conversion rate (conversions/sessions) to measure efficiency

---

#### Panel 3: Average Engagement Rate
**Type**: Stat (KPI)
**Unit**: Percentage

**What It Shows**:
Percentage of sessions that were "engaged"

**Query**:
```sql
SELECT ROUND(AVG(engagement_rate)::numeric, 4) as "Engagement Rate"
FROM gsc.fact_ga4_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days' AND sessions > 0
```

**Thresholds**:
- 🟢 Green: ≥30% (good)
- 🟡 Yellow: 10-29% (average)
- 🔴 Red: <10% (poor)

**What Is an Engaged Session**:
GA4 considers a session engaged if:
- Lasted ≥10 seconds, OR
- Had ≥2 pageviews, OR
- Triggered a conversion event

**Interpretation**:
- High engagement (>30%): Users finding value, good content
- Medium engagement (10-30%): Normal, room for improvement
- Low engagement (<10%): Content quality issues, slow site, or targeting problems

**Improvement Strategies**:
- <10%: Check page load speed, improve content quality
- 10-20%: Add internal links, related content
- >30%: Focus on conversion optimization

---

#### Panel 4: Average Bounce Rate
**Type**: Stat (KPI)
**Unit**: Percentage

**What It Shows**:
Percentage of sessions that were NOT engaged

**Query**:
```sql
SELECT ROUND(AVG(bounce_rate)::numeric, 4) as "Bounce Rate"
FROM gsc.fact_ga4_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days' AND sessions > 0
```

**Thresholds**:
- 🟢 Green: ≤50% (good)
- 🟡 Yellow: 50-70% (average)
- 🔴 Red: >70% (poor)

**What Is Bounce Rate** (GA4 definition):
Bounce Rate = 1 - Engagement Rate
A "bounce" is a session that was NOT engaged (per GA4 definition above).

**Interpretation**:
- Low bounce rate (<50%): Users engaging with content
- Medium bounce rate (50-70%): Normal for blogs/content sites
- High bounce rate (>70%): Content not meeting user expectations

**Important**: Not all bounces are bad
- Blog post that fully answers question → user leaves satisfied → high bounce but good UX
- Landing page → user gets info → bounces → mission accomplished

---

#### Panel 5: Sessions Over Time
**Type**: Time Series (Line Chart)

**What It Shows**:
Daily trend of total sessions and engaged sessions

**Query**:
```sql
SELECT
    date as time,
    SUM(sessions) as sessions,
    SUM(engaged_sessions) as engaged_sessions
FROM gsc.fact_ga4_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY date
ORDER BY date
```

**Features**:
- Two series: Total sessions (blue) and Engaged sessions (green)
- Shows engagement quality over time
- Identify days with low engagement rates

---

#### Panel 6: GSC Clicks vs GA4 Sessions (Separate Tracking)
**Type**: Time Series (Line Chart with two series)

**What It Shows**:
Comparison of GSC clicks (blue) and GA4 sessions (orange) over time

**Query** (Two queries combined):
```sql
-- Query A: GSC Clicks
SELECT date as time, SUM(clicks) as "GSC Clicks"
FROM gsc.fact_gsc_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY date
ORDER BY date

-- Query B: GA4 Sessions
SELECT date as time, SUM(sessions) as "GA4 Sessions"
FROM gsc.fact_ga4_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY date
ORDER BY date
```

**How to Read**:

**Normal Pattern**: Sessions ≈ 70-90% of clicks
- Some clicks don't result in sessions (ad blockers, bounce before load, etc.)
- Some sessions are from non-search sources (direct, referral, etc.)

**Warning Patterns**:
1. **Sessions << Clicks** (e.g., 50% of clicks)
   - Possible issue with GA4 tracking
   - Very slow page load (users leave before GA4 loads)
   - Ad blocker usage high

2. **Sessions >> Clicks** (e.g., 150% of clicks)
   - Site has significant non-search traffic
   - Normal for sites with strong direct/social traffic

---

#### Panel 7: Top Converting Pages (Last 30 Days)
**Type**: Table

**What It Shows**:
Pages ranked by total conversions with full metrics

**Query**:
```sql
SELECT
    RTRIM(property, '/') || page_path as full_url,
    SUM(sessions) as sessions,
    SUM(conversions) as conversions,
    ROUND(AVG(conversion_rate)::numeric, 4) as avg_conversion_rate,
    ROUND(AVG(engagement_rate)::numeric, 4) as avg_engagement_rate,
    ROUND(AVG(bounce_rate)::numeric, 4) as avg_bounce_rate
FROM gsc.fact_ga4_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days' AND sessions > 0
GROUP BY property, page_path
ORDER BY conversions DESC, sessions DESC
LIMIT 50
```

**Columns**:

1. **full_url**: Full page URL
2. **sessions**: Total sessions
3. **conversions**: Total conversions (color-coded)
4. **avg_conversion_rate**: Conversions/sessions (percentage)
5. **avg_engagement_rate**: Engaged sessions/total sessions (percentage)
6. **avg_bounce_rate**: Non-engaged sessions/total sessions (percentage)

**How to Use**:

**Find Conversion Champions**:
Pages with high conversion rates are your most valuable content.

**Identify Optimization Targets**:
- High sessions + Low conversions → CTA/funnel problem
- High engagement + Low conversions → Offer/targeting problem
- High bounce + Low conversions → Content mismatch

**Example Analysis**:
```
Page: /pricing
Sessions: 2,345
Conversions: 234
Conversion Rate: 10.0%
Engagement Rate: 45.2%
Bounce Rate: 54.8%

Analysis:
✅ Excellent conversion rate (10%)
✅ Good engagement (45%)
💡 Opportunity: If we increase sessions 2x → 468 conversions/month
💡 Action: Drive more traffic to this page via SEO/ads
```

---

## Hybrid Analytics - GSC + GA4 Unified Dashboard

**Access**: [http://localhost:3000](http://localhost:3000) → Hybrid Analytics
**Time Range**: Last 30 days
**UID**: `hybrid-overview`
**Data Source**: `vw_unified_page_performance` view

### Dashboard Purpose

This is the **most powerful dashboard** because it shows the complete user journey:
```
Search Impression → Click → Session → Engagement → Conversion
```

### Dashboard Layout

```
┌───────────────────────────────────────────────────────┐
│Search Impr.│Search Clicks│ GA4 Sessions │Conversions  │
│  (30d KPI) │   (30d KPI) │   (30d KPI)  │ (30d KPI)   │
├───────────────────────────────────────────────────────┤
│Search CTR  │Click→Session│ Conversion   │Impr→Conv    │
│  (30d KPI) │Rate (30d)   │ Rate (30d)   │Rate (30d)   │
├───────────────────────────────────────────────────────┤
│         Complete Funnel Over Time                     │
│    (Line Chart: Impressions→Clicks→Sessions→Conv)     │
├───────────────────────────────────────────────────────┤
│ High-Value Opportunity  │ SEO Opportunity Pages       │
│       Pages             │  (High Conv, Low Visibility)│
├───────────────────────────────────────────────────────┤
│          Traffic Source Effectiveness Matrix          │
├───────────────────────────────────────────────────────┤
│  Top Performing Content │  Pages Needing Attention    │
│ (Composite Score)       │  (Issues Detected)          │
└───────────────────────────────────────────────────────┘
```

### Key Panels

#### Panel 1-4: Funnel KPIs
**Shows**: Complete funnel from search impression to conversion

**Metrics**:
1. **Search Impressions**: How many times pages appeared in search
2. **Search Clicks**: How many users clicked from search
3. **GA4 Sessions**: How many sessions resulted
4. **Conversions**: How many conversions occurred

**Funnel Math**:
```
1,000,000 Impressions
    ↓ (3% CTR)
30,000 Clicks
    ↓ (80% arrive = Click-to-Session Rate)
24,000 Sessions
    ↓ (2% Conversion Rate)
480 Conversions

End-to-End Rate: 480/1,000,000 = 0.048%
```

#### Panel 5-8: Conversion Metrics

**Search CTR**: Clicks / Impressions
- Industry average: 2-5%
- Your target: ≥3%

**Click-to-Session Rate**: Sessions / Clicks
- Normal range: 70-90%
- Below 70%: Tracking or performance issues

**Conversion Rate**: Conversions / Sessions
- Varies by industry (0.5% - 10%)
- E-commerce: 1-3%
- SaaS: 2-5%
- Lead gen: 5-15%

**End-to-End Rate**: Conversions / Impressions
- Measures complete funnel efficiency
- Useful for ROI calculations

---

#### Panel 9: Complete Funnel Over Time
**Type**: Multi-series time series chart

**What It Shows**:
All four funnel stages on one chart over time

**Series**:
1. Impressions ÷ 100 (scaled down for visibility)
2. Clicks (actual)
3. Sessions (actual)
4. Conversions × 10 (scaled up for visibility)

**How to Read**:

**Normal Pattern**: All lines moving together
- Impressions and clicks correlated
- Sessions tracks clicks
- Conversions tracks sessions

**Warning Patterns**:

**Pattern 1: Impressions up, Clicks flat**
```
Impressions: ▲▲▲
Clicks:      ───
```
→ CTR declining, need meta tag optimization

**Pattern 2: Clicks up, Sessions flat**
```
Clicks:   ▲▲▲
Sessions: ───
```
→ Click-to-session rate declining, check page speed

**Pattern 3: Sessions up, Conversions flat**
```
Sessions:     ▲▲▲
Conversions:  ───
```
→ Conversion rate declining, check funnel/offer

---

#### Panel 10: High-Value Opportunity Pages
**Type**: Table

**What It Shows**:
Pages with high traffic but performance issues

**Query Logic**:
```sql
-- Pages with issues:
-- 1. High traffic (>50 clicks) but low engagement (<30%)
-- 2. High traffic but high bounce (>70%)
-- 3. High impressions but low CTR (<2%)
```

**Columns**:
- full_url
- GSC metrics (clicks, impressions, CTR, position)
- GA4 metrics (sessions, engagement, bounce, conversions)
- **opportunity**: Issue type detected

**Opportunity Types**:

1. **"Low Engagement - UX Issue"**
   - High clicks but engagement <20%
   - Action: Improve content quality, add media, fix layout

2. **"High Bounce - Content Issue"**
   - High clicks but bounce >80%
   - Action: Improve content relevance, match search intent

3. **"Low CTR - Title/Meta Issue"**
   - High impressions, good position (<5), but CTR <2%
   - Action: Rewrite meta title and description

4. **"No Conversions - CTA Issue"**
   - High sessions but zero conversions
   - Action: Add/improve call-to-action

---

#### Panel 11: SEO Opportunity Pages
**Type**: Table

**What It Shows**:
Pages with high conversion rates but low search visibility

**Query Logic**:
```sql
-- Pages with:
-- 1. High conversion rate (>5%)
-- 2. Low search position (>10) OR low impressions (<1000)
```

**Opportunity Types**:

1. **"SEO Opportunity"**
   - Converting well (>5% rate) but position >10
   - Action: Improve rankings → massive traffic gain

2. **"Low Visibility"**
   - Good sessions but very few clicks from search
   - Action: Create SEO content to drive more search traffic

3. **"Hidden Gem"**
   - High conversions but low impressions
   - Action: Expand keyword targeting, build more content

**Example**:
```
Page: /products/premium-widget
Sessions: 500
Conversions: 75
Conv Rate: 15% (excellent!)
GSC Clicks: 45
GSC Position: 18.5

Analysis:
✅ Amazing 15% conversion rate
⚠️ Only getting 45 clicks/month from search (position 18)
💡 Opportunity: Improve position 18 → position 5
   → Could get 500+ clicks/month
   → At 15% conversion = 75 extra conversions/month!
💡 This is a HIGH-VALUE SEO opportunity
```

---

#### Panel 12: Traffic Source Effectiveness Matrix
**Type**: Table

**What It Shows**:
Segmentation of pages by traffic level and engagement quality

**Segments**:
```
                High Engagement  |  Low Engagement
                (>50%)           |  (<30%)
─────────────────────────────────┼─────────────────
High Traffic    Quality Traffic  |  Volume Problem
(>200 clicks)   (scale up)       |  (fix engagement)
─────────────────────────────────┼─────────────────
Medium Traffic  Promising        |  Needs Work
(50-200 clicks) (grow & optimize)|  (fix or deprecate)
─────────────────────────────────┼─────────────────
Low Traffic     Gems             |  Low Priority
(<50 clicks)    (worth growing)  |  (consider removing)
```

**How to Use**:

1. **Focus on "Quality Traffic" segment**: These are winners, scale them up
2. **Fix "Volume Problem" segment**: High traffic but low engagement = content issues
3. **Grow "Promising" segment**: Good engagement, just need more traffic
4. **Evaluate "Needs Work"**: Fix or consider removing

---

#### Panel 13: Top Performing Content (Composite Score)
**Type**: Table

**What It Shows**:
Pages ranked by a composite performance score combining all metrics

**Scoring Formula**:
```
Performance Score =
  (clicks / max_clicks) × 0.20 +                  // 20% weight
  (1 - position/100) × 0.20 +                     // 20% weight (lower is better)
  (sessions / max_sessions) × 0.30 +              // 30% weight
  engagement_rate × 0.15 +                        // 15% weight
  (conversions / max_conversions) × 0.15          // 15% weight

Score range: 0.0 to 1.0 (higher is better)
```

**How to Read**:

- **Score 0.8-1.0**: Elite performers, your best content
- **Score 0.6-0.79**: Strong performers
- **Score 0.4-0.59**: Average performers
- **Score <0.4**: Underperformers

**Usage**:
1. Analyze what makes top scorers successful
2. Replicate winning patterns
3. Use as benchmark for new content

---

#### Panel 14: Pages Needing Attention (Issues Detected)
**Type**: Table

**What It Shows**:
Pages with detected issues requiring attention

**Detection Rules**:

1. **"High Bounce - Content Issue"**
   - Clicks >100 AND Bounce >80%
   - Root cause: Content doesn't match search intent

2. **"Low Engagement - UX Issue"**
   - Clicks >100 AND Engagement <20%
   - Root cause: Poor UX, slow site, or low-quality content

3. **"Low CTR - Title/Meta Issue"**
   - Position <10 AND CTR <2%
   - Root cause: Unappealing title/description

4. **"No Conversions - CTA Issue"**
   - Sessions >50 AND Conversions = 0
   - Root cause: Missing or weak call-to-action

5. **"SEO Opportunity"**
   - Position >20 AND Conversions >0
   - Root cause: Good content buried in search results

**Priority Order**:
Issues are sorted by traffic volume (clicks DESC), so you see high-impact problems first.

---

## Common Metrics Glossary

### GSC Metrics

**Impressions**
How many times a URL appeared in search results
- Counted per search query
- User doesn't need to scroll to see it
- Can be very high for broad topics

**Clicks**
How many times users clicked your URL from search results
- Always ≤ Impressions
- Measures actual traffic acquisition

**CTR (Click-Through Rate)**
Clicks ÷ Impressions × 100
- Measures how compelling your listing is
- Affected by title, description, URL, position

**Position**
Average ranking position in search results
- 1 = top of page 1
- 10 = bottom of page 1
- Weighted by impressions

**URL**
The specific page that appeared in search
- Can be normalized (www vs non-www)
- Includes full path and domain

**Query**
The search term the user typed
- Can be hundreds of variants per page
- Some queries hidden for privacy

---

### GA4 Metrics

**Sessions**
A period of user interaction with your site
- Ends after 30 minutes of inactivity (default)
- New campaign = new session
- One user can have multiple sessions

**Engaged Sessions**
Sessions that meet ANY of these criteria:
- Duration ≥10 seconds
- ≥2 pageviews
- ≥1 conversion event

**Engagement Rate**
Engaged Sessions ÷ Total Sessions × 100
- Measures quality of traffic
- Replaces "Pages/Session" from Universal Analytics

**Bounce Rate** (GA4 definition)
(Total Sessions - Engaged Sessions) ÷ Total Sessions × 100
- Opposite of engagement rate
- Different from UA bounce rate!

**Conversions**
Count of key events (goals) completed
- Configured in GA4 admin
- Can be multiple per session
- Examples: purchases, signups, downloads

**Conversion Rate**
Conversions ÷ Sessions × 100
- Measures funnel efficiency
- Varies widely by industry

**Average Session Duration**
Total duration ÷ Total sessions
- Measured in seconds
- Includes only engaged time (not idle)

**Page Views**
Total number of pages viewed
- Includes repeat views
- Can be multiple per session

---

### Hybrid Metrics (Calculated)

**Search-to-Conversion Rate**
Conversions ÷ GSC Clicks × 100
- Measures complete funnel from search click
- Accounts for users who clicked but didn't start session

**Session Conversion Rate**
Conversions ÷ GA4 Sessions × 100
- Traditional conversion rate
- Most comparable to other analytics platforms

**Click-to-Session Rate**
GA4 Sessions ÷ GSC Clicks × 100
- Should be 70-90%
- Lower = tracking issues or slow site

**End-to-End Rate**
Conversions ÷ GSC Impressions × 100
- Full funnel from search visibility to conversion
- Useful for ROI calculations

**Performance Score**
Composite score combining:
- SEO performance (position, CTR)
- Traffic volume (clicks, sessions)
- Engagement quality (engagement rate)
- Business value (conversions)

**Opportunity Index**
For pages with high impressions but low CTR:
```
Opportunity Index = Impressions × (Target_CTR - Current_CTR) / 100
```
Estimates potential traffic gain from CTR optimization

**Quality Score**
```
Quality Score = Position_Factor × Engagement_Rate
Where Position_Factor = 1.0 if position ≤10, else 0.5
```
Measures combined search quality and user satisfaction

---

## Using Dashboards Effectively

### Daily Monitoring Routine

**1. Morning Check (5 minutes)**
- Open Hybrid dashboard
- Check funnel KPIs for anomalies
- Review Recent Insights panel
- Note any high-severity issues

**2. Weekly Deep Dive (30 minutes)**
- GSC Dashboard: Review top pages and queries
- GA4 Dashboard: Check conversion trends
- Hybrid Dashboard: Analyze opportunity pages
- Create action items for optimization

**3. Monthly Analysis (2 hours)**
- Full funnel analysis over 90 days
- Identify content gaps
- Competitive analysis (position changes)
- ROI calculation from conversions

### Reading Time Series Charts

**Identify Patterns**:
1. **Trend**: Overall direction (up, down, flat)
2. **Seasonality**: Weekly or monthly patterns
3. **Anomalies**: Sudden spikes or drops
4. **Volatility**: How much variation day-to-day

**Take Action**:
1. **Sudden drops**: Investigate immediately (technical issues?)
2. **Gradual declines**: Plan content refresh or SEO campaign
3. **Spikes**: Analyze what worked, replicate
4. **Stable trends**: Monitor, no immediate action needed

### Combining Multiple Dashboards

**Use Case 1: Diagnosing Traffic Drop**
1. GSC Dashboard: Did clicks drop?
2. GSC Dashboard: Did impressions also drop? (visibility issue)
3. GSC Dashboard: Did position drop? (ranking issue)
4. GA4 Dashboard: Did conversions drop more than sessions? (quality issue)
5. Hybrid Dashboard: Check "Pages Needing Attention" for root cause

**Use Case 2: Finding Growth Opportunities**
1. Hybrid Dashboard: Check "SEO Opportunity Pages"
2. GSC Dashboard: See current position and CTR
3. GA4 Dashboard: Verify conversion rate is good
4. Prioritize: High conversion rate + Low position = highest ROI

**Use Case 3: Content Performance Audit**
1. GSC Dashboard: Top Pages by clicks
2. GA4 Dashboard: Same pages, check conversions
3. Hybrid Dashboard: Composite Performance Score
4. Categorize: Keep, Optimize, or Retire each page

---

## Troubleshooting

### Dashboard Shows No Data

**Possible Causes**:
1. Data collection not running
2. Wrong time range selected
3. PostgreSQL service down
4. Grafana datasource misconfigured

**Solutions**:
```bash
# Check data exists
docker compose exec warehouse psql -U gsc_user -d gsc_db \
  -c "SELECT COUNT(*) FROM gsc.fact_gsc_daily;"

# Check Grafana datasource
# Go to Configuration → Data Sources → postgres-gsc
# Click "Test" button

# Check time range
# Ensure dashboard time range is set to include data
```

### Metrics Don't Match Google Tools

**Expected Differences**:
1. **Timing**: Our data is 1-2 days delayed
2. **Timezone**: We use UTC, Google may use account timezone
3. **Rounding**: Slight differences in averages due to aggregation
4. **Filtering**: Our queries may filter differently

**Acceptable Variance**: ±5%
**Investigate If**: >10% difference

### Performance Issues (Slow Dashboards)

**Immediate Fixes**:
1. Reduce time range (try last 30 days instead of 90)
2. Add property filter to queries
3. Limit table rows (change LIMIT 50 to LIMIT 20)

**Long-term Solutions**:
1. Create materialized views
2. Add more indexes
3. Enable PostgreSQL query caching

### Missing Recent Data

**Expected Delay**: 24-48 hours
- GSC API has ~2 day delay for complete data
- GA4 processing takes 24-48 hours

**Check Collection Status**:
```bash
# View scheduler logs
docker compose logs scheduler | tail -50

# Check last ingestion time
docker compose exec warehouse psql -U gsc_user -d gsc_db \
  -c "SELECT MAX(date) as last_date, MAX(ingested_at) as last_ingested
      FROM gsc.fact_gsc_daily;"
```

---

## Dashboard Customization

### Adding Filters

**Property Filter**:
1. Dashboard Settings → Variables → Add Variable
2. Name: `property`
3. Type: Query
4. Query: `SELECT DISTINCT property FROM gsc.fact_gsc_daily`
5. Update all panel queries to include `WHERE property = '$property'`

**Date Range Shortcuts**:
- Last 7 days: Good for monitoring
- Last 30 days: Monthly reporting
- Last 90 days: Trend analysis
- Year to date: Annual performance

### Creating Custom Panels

**Example: Top Declining Pages**

```sql
WITH latest AS (
  SELECT
    page_path,
    date,
    gsc_clicks,
    gsc_clicks_change_wow
  FROM gsc.vw_unified_page_performance
  WHERE date = CURRENT_DATE - INTERVAL '1 day'
)
SELECT
  page_path,
  gsc_clicks,
  gsc_clicks_change_wow
FROM latest
WHERE gsc_clicks_change_wow < -20
ORDER BY gsc_clicks_change_wow ASC
LIMIT 10
```

---

**Document Version**: 1.0
**Last Updated**: 2025
**Feedback**: Report issues or suggestions via GitHub Issues

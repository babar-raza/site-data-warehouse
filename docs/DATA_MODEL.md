# Data Model Reference

**Complete schema documentation for the site-data-warehouse**

---

## Overview

The site-data-warehouse uses PostgreSQL 14+ with **10 schemas** containing **44+ tables** and **30+ views**. This document provides a complete reference for the canonical data model.

### Schema Organization

| Schema | Purpose | Tables | Key Feature |
|--------|---------|--------|-------------|
| `gsc` | Core GSC/GA4 data and insights | 12+ | Main fact tables, unified views |
| `content` | Content intelligence | 6 | Semantic search, quality scoring |
| `forecasts` | ML predictions | 2 | Prophet forecasts, accuracy tracking |
| `serp` | SERP position tracking | 3 | Dual-source (GSC + API) |
| `performance` | Core Web Vitals | 2 | PageSpeed metrics, monitored pages |
| `trends` | Google Trends data | 3 | Keyword interest tracking |
| `hugo` | Hugo CMS integration | 1 | Content file metadata |
| `notifications` | Alerting system | 3 | Alert rules, delivery tracking |
| `orchestration` | Multi-agent system | 4 | Agent state, workflow execution |
| `anomaly` | Anomaly detection | 1 | ML-detected anomalies |

---

## GSC Schema (Primary Data)

### `gsc.fact_gsc_daily`

**Purpose:** Daily search performance metrics from Google Search Console

**Grain:** One row per (date, property, url, query, country, device)

**Key Columns:**
```sql
date                DATE NOT NULL
property            VARCHAR(500) NOT NULL
url                 TEXT NOT NULL
query               TEXT NOT NULL
country             VARCHAR(3) NOT NULL         -- ISO country code
device              VARCHAR(20) NOT NULL        -- desktop, mobile, tablet
clicks              INTEGER NOT NULL DEFAULT 0
impressions         INTEGER NOT NULL DEFAULT 0
ctr                 NUMERIC(10,6)               -- Click-through rate
position            NUMERIC(10,2)               -- Average SERP position
```

**Primary Key:** `(date, property, url, query, country, device)`

**Indexes:**
- `idx_fact_gsc_date_property_url` on `(date DESC, property, url)`
- `idx_fact_gsc_query` on `(query)`
- `idx_fact_gsc_covering` covering index for aggregations

**Volume:** High (millions of rows typical for active sites)

**Example Query:**
```sql
-- Top queries by clicks for a specific page
SELECT
    query,
    SUM(clicks) as total_clicks,
    AVG(position) as avg_position,
    SUM(impressions) as total_impressions
FROM gsc.fact_gsc_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
    AND property = 'sc-domain:example.com'
    AND url LIKE '%/blog/post%'
GROUP BY query
ORDER BY total_clicks DESC
LIMIT 20;
```

---

### `gsc.fact_ga4_daily`

**Purpose:** Daily user behavior metrics from Google Analytics 4

**Grain:** One row per (date, property, page_path)

**Key Columns:**
```sql
date                    DATE NOT NULL
property                VARCHAR(255) NOT NULL
page_path               TEXT NOT NULL
sessions                INTEGER DEFAULT 0
engaged_sessions        INTEGER DEFAULT 0
engagement_rate         NUMERIC(5,4)            -- 0.0 to 1.0
bounce_rate             NUMERIC(5,4)            -- 0.0 to 1.0
conversions             INTEGER DEFAULT 0
conversion_rate         NUMERIC(5,4)
avg_session_duration    NUMERIC(10,2)           -- Seconds
page_views              INTEGER DEFAULT 0
avg_time_on_page        NUMERIC(10,2)           -- Seconds
exits                   INTEGER DEFAULT 0
exit_rate               NUMERIC(5,4)
```

**Primary Key:** `(date, property, page_path)`

**Indexes:**
- `idx_fact_ga4_date_property_page` on `(date DESC, property, page_path)`

**Integration:** Joins with GSC via `page_path` in unified views

**Example Query:**
```sql
-- Conversion funnel by page
SELECT
    page_path,
    SUM(sessions) as total_sessions,
    SUM(engaged_sessions) as engaged,
    AVG(engagement_rate) as avg_engagement,
    SUM(conversions) as total_conversions,
    ROUND(SUM(conversions)::NUMERIC / NULLIF(SUM(sessions), 0) * 100, 2) as conv_rate
FROM gsc.fact_ga4_daily
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
    AND property = 'https://example.com'
GROUP BY page_path
HAVING SUM(sessions) > 100
ORDER BY total_conversions DESC;
```

---

### `gsc.insights`

**Purpose:** Canonical insights storage from all detectors

**Grain:** One row per unique insight (deterministic hash prevents duplicates)

**Key Columns:**
```sql
id                  VARCHAR(64) PRIMARY KEY     -- SHA256 hash
generated_at        TIMESTAMP NOT NULL
property            VARCHAR(500) NOT NULL
entity_type         VARCHAR(50) NOT NULL        -- page, query, directory, property
entity_id           TEXT NOT NULL               -- URL, query text, etc.
category            VARCHAR(50) NOT NULL        -- risk, opportunity, trend, diagnosis
title               VARCHAR(200) NOT NULL
description         TEXT NOT NULL
severity            VARCHAR(20)                 -- low, medium, high
confidence          NUMERIC(3,2)                -- 0.0 to 1.0
metrics             JSONB                       -- Flexible metrics snapshot
window_days         INTEGER NOT NULL            -- Lookback period (1-365)
source              VARCHAR(100) NOT NULL       -- Detector name
status              VARCHAR(50)                 -- new, investigating, diagnosed, actioned, resolved
linked_insight_id   VARCHAR(64)                 -- FK to related insight
```

**Hash Formula:**
```sql
SHA256(property || '|' || entity_type || '|' || entity_id || '|' ||
       category || '|' || source || '|' || window_days)
```

**Indexes:** 11 indexes for query optimization:
- `idx_insights_property_status` on `(property, status)`
- `idx_insights_category_severity` on `(category, severity)`
- `idx_insights_entity` on `(entity_type, entity_id)`
- Plus composite indexes for common patterns

**Example Query:**
```sql
-- High-severity risks needing attention
SELECT
    entity_id as page_path,
    title,
    description,
    severity,
    confidence,
    metrics->>'gsc_clicks_change' as click_change_pct,
    metrics->>'ga_conversions_change' as conv_change_pct,
    generated_at
FROM gsc.insights
WHERE property = 'https://example.com'
    AND category = 'risk'
    AND severity = 'high'
    AND status IN ('new', 'investigating')
ORDER BY generated_at DESC;
```

---

### `gsc.actions`

**Purpose:** Actionable tasks derived from insights with full SDLC tracking

**Grain:** One row per action

**Key Columns:**
```sql
action_id           UUID PRIMARY KEY
insight_id          VARCHAR(64)                 -- FK to gsc.insights
action_type         VARCHAR(100) NOT NULL       -- rewrite_meta, improve_content, fix_technical
category            VARCHAR(50)                 -- content, technical, ux, performance, strategy
title               VARCHAR(200) NOT NULL
description         TEXT NOT NULL
page_path           TEXT
property            VARCHAR(500) NOT NULL
priority_score      DECIMAL(5,2)                -- Calculated: (impact/10) * (10/effort) * urgency * 100
impact_score        INTEGER CHECK (1-10)        -- Business value
effort_score        INTEGER CHECK (1-10)        -- Implementation complexity
urgency             VARCHAR(20)                 -- low, medium, high, critical
estimated_hours     DECIMAL(5,1)
status              VARCHAR(50)                 -- pending, in_progress, blocked, completed, cancelled
owner               VARCHAR(100)
assigned_at         TIMESTAMP
started_at          TIMESTAMP
completed_at        TIMESTAMP
due_date            TIMESTAMP
implementation_notes TEXT
outcome             VARCHAR(50)                 -- improved, no_change, worsened, unknown
metrics_before      JSONB                       -- Baseline metrics
metrics_after       JSONB                       -- Post-implementation metrics
lift_pct            DECIMAL(6,2)                -- % change in primary metric
```

**Priority Score Formula:**
```python
priority_score = (impact / 10) * (10 / effort) * urgency_multiplier * 100
# urgency_multipliers: critical=3.0, high=2.0, medium=1.5, low=1.0
```

**Triggers:**
- Auto-calculates `priority_score` on INSERT/UPDATE
- Auto-sets timestamps on status changes

**Example Query:**
```sql
-- Top priority pending actions
SELECT
    action_id,
    title,
    category,
    priority_score,
    impact_score,
    effort_score,
    urgency,
    estimated_hours,
    due_date,
    CASE
        WHEN priority_score >= 75 THEN 'critical'
        WHEN priority_score >= 50 THEN 'high'
        WHEN priority_score >= 25 THEN 'medium'
        ELSE 'low'
    END as priority_label
FROM gsc.actions
WHERE status IN ('pending', 'in_progress')
    AND property = 'https://example.com'
ORDER BY priority_score DESC, created_at ASC
LIMIT 20;
```

---

### `gsc.vw_unified_page_performance` ⭐

**Purpose:** Central analytical view combining GSC + GA4 with time-series calculations

**Construction:** FULL OUTER JOIN of GSC and GA4 fact tables + window functions

**Grain:** One row per (date, property, page_path)

**Key Fields:**
```sql
-- Identification
date, property, page_path

-- Current Metrics (GSC)
gsc_clicks, gsc_impressions, gsc_ctr, gsc_position

-- Current Metrics (GA4)
ga_sessions, ga_engagement_rate, ga_bounce_rate, ga_conversions,
ga_avg_session_duration, ga_page_views

-- Historical Values (for comparison)
gsc_clicks_7d_ago, gsc_clicks_28d_ago
gsc_impressions_7d_ago, gsc_impressions_28d_ago
ga_conversions_7d_ago, ga_conversions_28d_ago

-- Rolling Averages
gsc_clicks_7d_avg, gsc_clicks_28d_avg
gsc_impressions_7d_avg, gsc_impressions_28d_avg
ga_conversions_7d_avg, ga_conversions_28d_avg

-- Week-over-Week Changes (%)
gsc_clicks_change_wow, gsc_impressions_change_wow
ga_conversions_change_wow, ga_engagement_rate_change_wow
gsc_position_change_wow  -- Absolute change, not %

-- Month-over-Month Changes (%)
gsc_clicks_change_mom, gsc_impressions_change_mom
ga_conversions_change_mom

-- Composite Metrics
search_to_conversion_rate, session_conversion_rate,
performance_score, opportunity_index, conversion_efficiency, quality_score
```

**Data Requirements:**
- 7+ days for WoW calculations
- 28+ days for MoM calculations
- NULL handling for insufficient data (expected)

**See Also:** [Unified View Guide](guides/UNIFIED_VIEW_GUIDE.md) for complete documentation

---

## Content Schema (Content Intelligence)

### `content.page_snapshots`

**Purpose:** Content version storage with semantic embeddings for change detection and search

**Grain:** One row per (property, page_path, snapshot_date)

**Key Columns:**
```sql
id                      BIGSERIAL PRIMARY KEY
snapshot_id             UUID UNIQUE NOT NULL
property                VARCHAR(500) NOT NULL
page_path               TEXT NOT NULL
snapshot_date           TIMESTAMP NOT NULL
url                     TEXT NOT NULL

-- Raw Content
html_content            TEXT                    -- Full HTML
text_content            TEXT                    -- Extracted plain text
content_hash            VARCHAR(64)             -- SHA256 for change detection

-- Metadata
title                   TEXT
meta_description        TEXT
meta_keywords           TEXT
canonical_url           TEXT
h1_tags                 TEXT[]
h2_tags                 TEXT[]
h3_tags                 TEXT[]
image_count             INTEGER
link_count              INTEGER
internal_link_count     INTEGER
external_link_count     INTEGER

-- Content Metrics
word_count              INTEGER
character_count         INTEGER
paragraph_count         INTEGER
sentence_count          INTEGER
flesch_reading_ease     DECIMAL(5,2)            -- 0-100 (higher = easier)
flesch_kincaid_grade    DECIMAL(5,2)            -- Grade level

-- Semantic Embeddings (pgvector)
content_embedding       vector(768)             -- Full content embedding
title_embedding         vector(768)             -- Title-only embedding
embedding_model         VARCHAR(100)            -- e.g., 'all-MiniLM-L6-v2', 'nomic-embed-text'

analyzed_at             TIMESTAMP
analysis_version        TEXT
```

**Indexes:**
- HNSW index on `content_embedding` for fast vector similarity search
- B-tree indexes on property, page_path, snapshot_date

**Usage:**
```sql
-- Semantic search: Find similar content
SELECT
    page_path,
    title,
    word_count,
    1 - (content_embedding <=> query_embedding) as similarity
FROM content.page_snapshots
WHERE property = 'https://example.com'
    AND content_embedding IS NOT NULL
ORDER BY content_embedding <=> query_embedding
LIMIT 10;
```

---

### `content.topics`

**Purpose:** Hierarchical topic organization with centroids

**Key Columns:**
```sql
id                  SERIAL PRIMARY KEY
topic_id            UUID UNIQUE NOT NULL
name                VARCHAR(200) UNIQUE NOT NULL
slug                VARCHAR(200) UNIQUE NOT NULL
description         TEXT
parent_topic_id     INTEGER                     -- FK to self for hierarchy
level               INTEGER DEFAULT 0           -- 0=top-level, 1+=nested
topic_embedding     vector(768)                 -- Centroid of all pages in topic
page_count          INTEGER DEFAULT 0           -- Cached count
avg_performance     DECIMAL(6,2)
is_active           BOOLEAN DEFAULT TRUE
```

**Example Query:**
```sql
-- Topic hierarchy with performance
WITH RECURSIVE topic_tree AS (
    -- Root topics
    SELECT id, name, parent_topic_id, level, page_count, avg_performance,
           ARRAY[name] as path
    FROM content.topics
    WHERE parent_topic_id IS NULL

    UNION ALL

    -- Child topics
    SELECT t.id, t.name, t.parent_topic_id, t.level, t.page_count, t.avg_performance,
           tt.path || t.name
    FROM content.topics t
    JOIN topic_tree tt ON t.parent_topic_id = tt.id
)
SELECT
    REPEAT('  ', level) || name as topic_hierarchy,
    page_count,
    ROUND(avg_performance, 2) as performance
FROM topic_tree
ORDER BY path;
```

---

### `content.page_topics`

**Purpose:** Many-to-many mapping between pages and topics

**Key Columns:**
```sql
page_path               TEXT NOT NULL
property                VARCHAR(500) NOT NULL
topic_id                INTEGER NOT NULL        -- FK to content.topics
relevance_score         FLOAT                   -- 0.0 to 1.0
assignment_method       VARCHAR(50)             -- auto, manual, suggested, verified
assigned_at             TIMESTAMP
assigned_by             VARCHAR(100)
```

**Primary Key:** `(page_path, property, topic_id)`

---

### `content.quality_scores`

**Purpose:** AI-generated content quality assessments

**Key Columns:**
```sql
id                      BIGSERIAL PRIMARY KEY
property                VARCHAR(500) NOT NULL
page_path               TEXT NOT NULL
snapshot_id             UUID                    -- FK to page_snapshots

-- Overall Score
overall_score           DECIMAL(4,2)            -- 0-100

-- Dimension Scores
readability_score       DECIMAL(4,2)
relevance_score         DECIMAL(4,2)
depth_score             DECIMAL(4,2)
uniqueness_score        DECIMAL(4,2)
optimization_score      DECIMAL(4,2)

-- LLM Analysis
content_summary         TEXT                    -- Generated summary
key_topics              TEXT[]
sentiment               VARCHAR(20)             -- positive, neutral, negative
target_audience         VARCHAR(100)
improvement_suggestions TEXT[]
missing_elements        TEXT[]

-- Metadata
analyzed_by             VARCHAR(100)            -- ollama, openai, manual
model_version           VARCHAR(100)
confidence              DECIMAL(3,2)
created_at              TIMESTAMP
```

---

### `content.cannibalization_pairs`

**Purpose:** Detect pages competing for the same keywords

**Key Columns:**
```sql
id                      SERIAL PRIMARY KEY
property                VARCHAR(500) NOT NULL
page_a                  TEXT NOT NULL
page_b                  TEXT NOT NULL           -- WHERE page_a < page_b
similarity_score        FLOAT                   -- 0.0 to 1.0 from embeddings
shared_queries          TEXT[]                  -- Queries both pages rank for
conflict_severity       VARCHAR(20)             -- low, medium, high, critical
estimated_traffic_loss  INTEGER
status                  VARCHAR(50)             -- active, investigating, resolved, ignored
resolution_action       VARCHAR(100)            -- consolidate, differentiate, redirect, keep_both
resolution_notes        TEXT
resolved_at             TIMESTAMP
resolved_by             VARCHAR(100)
detected_at             TIMESTAMP NOT NULL
last_checked            TIMESTAMP
```

**Example Query:**
```sql
-- Active high-severity cannibalization issues
SELECT
    page_a,
    page_b,
    similarity_score,
    array_length(shared_queries, 1) as num_shared_queries,
    conflict_severity,
    estimated_traffic_loss
FROM content.cannibalization_pairs
WHERE property = 'https://example.com'
    AND status = 'active'
    AND conflict_severity IN ('high', 'critical')
ORDER BY estimated_traffic_loss DESC;
```

---

### `content.content_changes`

**Purpose:** Track significant content changes and their SEO impact

**Key Columns:**
```sql
id                      BIGSERIAL PRIMARY KEY
property                VARCHAR(500) NOT NULL
page_path               TEXT NOT NULL
change_date             TIMESTAMP NOT NULL
change_type             VARCHAR(50)             -- created, updated, deleted, major_update, minor_update
before_snapshot_id      UUID                    -- FK to page_snapshots
after_snapshot_id       UUID                    -- FK to page_snapshots
word_count_delta        INTEGER
content_similarity      FLOAT                   -- 0.0 to 1.0
changes_summary         TEXT
changed_sections        TEXT[]                  -- title, meta, h1, body, etc.
traffic_before          JSONB                   -- GSC metrics snapshot
traffic_after           JSONB                   -- GSC metrics snapshot
impact_measured_at      TIMESTAMP
traffic_impact_pct      DECIMAL(6,2)
changed_by              VARCHAR(100)
change_reason           TEXT
```

---

## SERP Schema (Position Tracking)

### `serp.queries`

**Purpose:** Target keywords to track in search engines

**Key Columns:**
```sql
query_id                UUID PRIMARY KEY
query_text              TEXT NOT NULL
property                TEXT NOT NULL
target_page_path        TEXT                    -- Expected ranking page
location                TEXT DEFAULT 'United States'
language                TEXT DEFAULT 'en'
device                  TEXT DEFAULT 'desktop'  -- desktop, mobile
search_engine           TEXT DEFAULT 'google'
is_active               BOOLEAN DEFAULT TRUE
check_frequency         TEXT DEFAULT 'daily'    -- daily, weekly, monthly
data_source             TEXT NOT NULL           -- manual, gsc, serpstack, valueserp, serpapi
created_at              TIMESTAMP
```

**Uniqueness:** `(property, query_text, target_page_path, device, location)`

**Dual-Source Support:**
- `data_source='gsc'` - Free, extracted from GSC data
- `data_source='valueserp'` or `'serpapi'` - Paid API tracking

---

### `serp.position_history`

**Purpose:** Time-series position data for tracked queries

**Key Columns:**
```sql
position_id             UUID PRIMARY KEY
query_id                UUID NOT NULL           -- FK to serp.queries
check_date              DATE NOT NULL
check_timestamp         TIMESTAMP NOT NULL
position                INTEGER                 -- NULL if not in top 100
url                     TEXT
domain                  TEXT
title                   TEXT
description             TEXT
total_results           BIGINT
competitors             JSONB                   -- Top 10: [{position, domain, url, title}]
serp_features           JSONB                   -- {featured_snippet: true, people_also_ask: true}
api_source              TEXT                    -- valueserp, serpapi, scrapy, gsc
raw_response            JSONB                   -- Full API response
```

**Uniqueness:** `(query_id, check_date, check_timestamp)`

**Views:**
- `vw_current_positions` - Latest position per query with WoW change
- `vw_position_trends` - 7-day and 30-day moving averages
- `vw_position_changes` - Week-over-week gainers/losers
- `vw_top_positions` - Distribution across ranking buckets

---

### `serp.serp_features`

**Purpose:** Track ownership of SERP features

**Key Columns:**
```sql
feature_id              UUID PRIMARY KEY
query_id                UUID NOT NULL
check_date              DATE NOT NULL
feature_type            TEXT NOT NULL           -- featured_snippet, people_also_ask, video, image
owner_domain            TEXT
owner_url               TEXT
content                 JSONB                   -- Feature-specific data
position                INTEGER                 -- Position in SERP
```

---

## Performance Schema (Core Web Vitals)

### `performance.core_web_vitals`

**Purpose:** Core Web Vitals metrics from PageSpeed Insights

**Key Columns:**
```sql
cwv_id                  UUID PRIMARY KEY
property                TEXT NOT NULL
page_path               TEXT NOT NULL
check_date              DATE NOT NULL
strategy                TEXT NOT NULL           -- mobile, desktop

-- Core Web Vitals
lcp                     FLOAT                   -- Largest Contentful Paint (ms) - Good: <2500
fid                     FLOAT                   -- First Input Delay (ms) - Good: <100
cls                     FLOAT                   -- Cumulative Layout Shift - Good: <0.1
fcp                     FLOAT                   -- First Contentful Paint (ms)
inp                     FLOAT                   -- Interaction to Next Paint (ms)
ttfb                    FLOAT                   -- Time to First Byte (ms)

-- Lab Metrics
tti                     FLOAT                   -- Time to Interactive
tbt                     FLOAT                   -- Total Blocking Time
speed_index             FLOAT

-- Lighthouse Scores (0-100)
performance_score       INTEGER
accessibility_score     INTEGER
best_practices_score    INTEGER
seo_score               INTEGER
pwa_score               INTEGER

cwv_assessment          TEXT                    -- pass, needs_improvement, fail
opportunities           JSONB
diagnostics             JSONB
audits                  JSONB
lighthouse_version      TEXT
user_agent              TEXT
raw_response            JSONB
```

**Uniqueness:** `(property, page_path, check_date, strategy)`

**Views:**
- `vw_cwv_current` - Latest CWV with change tracking
- `vw_poor_cwv` - Pages failing thresholds
- `vw_cwv_trends` - 90-day trends with moving averages

---

### `performance.monitored_pages`

**Purpose:** URL discovery and prioritization for CWV collection

**Key Columns:**
```sql
page_id                 UUID PRIMARY KEY
property                TEXT NOT NULL
page_path               TEXT NOT NULL
page_name               TEXT
check_mobile            BOOLEAN DEFAULT TRUE
check_desktop           BOOLEAN DEFAULT FALSE
is_active               BOOLEAN DEFAULT TRUE
discovery_source        TEXT                    -- gsc, ga4, manual, gsc+ga4
first_discovered_at     TIMESTAMP
last_seen_at            TIMESTAMP
total_clicks            INTEGER DEFAULT 0       -- Cumulative
total_sessions          INTEGER DEFAULT 0       -- Cumulative
avg_position            NUMERIC(10,2)
priority_score          FLOAT                   -- Calculated: clicks(40%) + sessions(25%) + position(20%) + recency(15%)
```

**Priority Score Formula:**
```python
clicks_score = min(total_clicks / 1000, 1.0) * 0.40
sessions_score = min(total_sessions / 500, 1.0) * 0.25
position_score = max(0, (20 - avg_position) / 20) * 0.20
recency_score = max(0, 1 - (days_since_last_seen / 90)) * 0.15
priority_score = (clicks_score + sessions_score + position_score + recency_score) * 100
```

**Auto-Discovery:** URLs synced from `gsc.fact_gsc_daily` and `gsc.fact_ga4_daily`

**See Also:** [URL Discovery Guide](guides/URL_DISCOVERY_GUIDE.md)

---

## Trends Schema (Google Trends)

### `trends.keyword_interest`

**Purpose:** Daily interest scores from Google Trends

**Key Columns:**
```sql
id                      SERIAL PRIMARY KEY
property                VARCHAR(255) NOT NULL
keyword                 VARCHAR(500) NOT NULL
date                    DATE NOT NULL
interest_score          INTEGER                 -- 0-100 scale
is_partial              BOOLEAN DEFAULT FALSE   -- True for incomplete/current week
collected_at            TIMESTAMP
```

**Uniqueness:** `(property, keyword, date)`

---

### `trends.related_queries`

**Purpose:** Rising and top related queries for opportunity discovery

**Key Columns:**
```sql
id                      SERIAL PRIMARY KEY
property                VARCHAR(255) NOT NULL
keyword                 VARCHAR(500) NOT NULL
related_query           VARCHAR(500) NOT NULL
query_type              VARCHAR(50)             -- 'rising' or 'top'
score                   INTEGER                 -- Relative score/percentage
collected_at            TIMESTAMP
```

---

### `trends.collection_runs`

**Purpose:** Track trends collection runs for monitoring

**Key Columns:**
```sql
id                      SERIAL PRIMARY KEY
property                VARCHAR(255) NOT NULL
keywords_collected      INTEGER DEFAULT 0
keywords_failed         INTEGER DEFAULT 0
related_queries_collected INTEGER DEFAULT 0
started_at              TIMESTAMP
completed_at            TIMESTAMP
status                  VARCHAR(50)             -- running, completed, failed
error_message           TEXT
```

---

## Hugo Schema (CMS Integration)

### `hugo.content_files`

**Purpose:** Hugo markdown file metadata for CMS integration

**Key Columns:**
```sql
file_id                 UUID PRIMARY KEY
file_path               TEXT NOT NULL           -- Relative path from content root
property                TEXT NOT NULL
page_path               TEXT                    -- Mapped URL path
locale                  TEXT                    -- Language code (en, es, fr, etc.)

-- Frontmatter Fields
title                   TEXT
description             TEXT
date                    TIMESTAMP
publishDate             TIMESTAMP
lastmod                 TIMESTAMP
author                  TEXT
tags                    TEXT[]
categories              TEXT[]
draft                   BOOLEAN DEFAULT FALSE

-- Change Detection
content_hash            VARCHAR(64)             -- SHA256
synced_at               TIMESTAMP
```

**Localization Support:**
- File-based: `index.en.md`, `index.es.md`
- Folder-based: `/en/index.md`, `/es/index.md`

---

## Notifications Schema (Alerting)

### `notifications.alert_rules`

**Purpose:** Define conditions for automated alerts

**Key Columns:**
```sql
rule_id                 UUID PRIMARY KEY
rule_name               VARCHAR(200) NOT NULL
property                TEXT NOT NULL
metric_name             TEXT NOT NULL           -- clicks, conversions, position, etc.
condition_type          TEXT NOT NULL           -- threshold, percentage_change, etc.
threshold_value         FLOAT
lookback_days           INTEGER DEFAULT 7
severity                VARCHAR(20)             -- low, medium, high, critical
channels                TEXT[]                  -- slack, email, webhook
is_active               BOOLEAN DEFAULT TRUE
created_at              TIMESTAMP
updated_at              TIMESTAMP
```

---

### `notifications.alert_history`

**Purpose:** Track which alerts were sent and delivery status

**Key Columns:**
```sql
alert_id                UUID PRIMARY KEY
rule_id                 UUID                    -- FK to alert_rules
triggered_at            TIMESTAMP NOT NULL
property                TEXT NOT NULL
entity_id               TEXT                    -- Page path, query, etc.
severity                VARCHAR(20)
message                 TEXT
metrics                 JSONB
channels_sent           TEXT[]
delivery_status         JSONB                   -- Per-channel delivery results
acknowledged_at         TIMESTAMP
acknowledged_by         TEXT
```

---

## Orchestration Schema (Multi-Agent System)

### `orchestration.agent_executions`

**Purpose:** Track multi-agent workflow executions

**Key Columns:**
```sql
execution_id            UUID PRIMARY KEY
workflow_type           TEXT NOT NULL           -- emergency_response, routine_analysis, etc.
agent_name              TEXT NOT NULL           -- SupervisorAgent, WatcherAgent, etc.
started_at              TIMESTAMP NOT NULL
completed_at            TIMESTAMP
status                  VARCHAR(50)             -- pending, running, completed, failed
input_data              JSONB
output_data             JSONB
error_message           TEXT
```

---

## Anomaly Schema

### `anomaly.detected_anomalies`

**Purpose:** Store anomalies detected by various methods

**Key Columns:**
```sql
anomaly_id              UUID PRIMARY KEY
property                TEXT NOT NULL
page_path               TEXT
detection_date          DATE NOT NULL
metric_name             TEXT NOT NULL
actual_value            FLOAT
expected_value          FLOAT
deviation_pct           FLOAT
detection_method        TEXT                    -- statistical, ml, forecasting
severity                VARCHAR(20)
confidence              FLOAT
created_at              TIMESTAMP
```

---

## Forecasts Schema (Prophet ML)

### `forecasts.traffic_forecasts`

**Purpose:** Store ML-generated traffic predictions

**Key Columns:**
```sql
forecast_id             UUID PRIMARY KEY
property                TEXT NOT NULL
page_path               TEXT
forecast_date           DATE NOT NULL           -- Date being forecasted
forecast_run_id         UUID                    -- Group forecasts from same run
metric_name             TEXT                    -- clicks, impressions, sessions, etc.
predicted_value         FLOAT
lower_bound             FLOAT                   -- Confidence interval
upper_bound             FLOAT                   -- Confidence interval
confidence_level        FLOAT DEFAULT 0.95
created_at              TIMESTAMP
model_version           TEXT
model_params            JSONB
```

---

### `forecasts.accuracy_tracking`

**Purpose:** Track forecast accuracy vs. actuals

**Key Columns:**
```sql
accuracy_id             UUID PRIMARY KEY
forecast_id             UUID NOT NULL           -- FK to traffic_forecasts
actual_value            FLOAT
predicted_value         FLOAT
error_pct               FLOAT                   -- (actual - predicted) / actual * 100
absolute_error          FLOAT
squared_error           FLOAT
measured_at             TIMESTAMP
```

---

## Appendix: Complete Table List

### GSC Schema (12 tables)
1. `fact_gsc_daily` - GSC metrics
2. `fact_ga4_daily` - GA4 metrics
3. `insights` - Canonical insights
4. `actions` - Actionable tasks
5. `dim_property` - Property dimension
6. `dim_page` - Page dimension
7. `dim_query` - Query dimension
8. `ingest_watermarks` - Ingestion tracking
9. `audit_log` - Change audit trail
10. `agent_findings` - Agent discoveries
11. `agent_diagnoses` - Agent diagnoses
12. `agent_recommendations` - Agent recommendations

### Content Schema (6 tables)
1. `page_snapshots` - Content versions with embeddings
2. `topics` - Topic hierarchy
3. `page_topics` - Page-topic mapping
4. `quality_scores` - AI quality assessments
5. `cannibalization_pairs` - Content conflicts
6. `content_changes` - Change tracking

### SERP Schema (3 tables)
1. `queries` - Tracked keywords
2. `position_history` - Position time-series
3. `serp_features` - SERP feature tracking

### Performance Schema (2 tables)
1. `core_web_vitals` - CWV metrics
2. `monitored_pages` - URL discovery and prioritization

### Trends Schema (3 tables)
1. `keyword_interest` - Interest scores
2. `related_queries` - Related/rising queries
3. `collection_runs` - Collection monitoring

### Hugo Schema (1 table)
1. `content_files` - Hugo file metadata

### Notifications Schema (3 tables)
1. `alert_rules` - Alert definitions
2. `alert_history` - Alert delivery log
3. `notification_queue` - Pending notifications

### Orchestration Schema (4 tables)
1. `agent_executions` - Agent workflow tracking
2. `workflow_steps` - Step-level tracking
3. `agent_state` - Agent state persistence
4. `workflow_definitions` - Workflow templates

### Forecasts Schema (2 tables)
1. `traffic_forecasts` - Prophet predictions
2. `accuracy_tracking` - Forecast accuracy

### Anomaly Schema (1 table)
1. `detected_anomalies` - ML-detected anomalies

**Total: 44+ Tables**

---

## Views Reference

### Primary Views
- `gsc.vw_unified_page_performance` - **Main analytical view** (GSC + GA4 + time-series)
- `gsc.vw_unified_page_performance_latest` - Latest snapshot per page
- `gsc.vw_unified_anomalies` - Pre-filtered anomalies

### SERP Views
- `serp.vw_current_positions` - Latest positions with WoW change
- `serp.vw_position_trends` - Moving averages
- `serp.vw_position_changes` - Week-over-week gainers/losers
- `serp.vw_top_positions` - Ranking distribution

### Performance Views
- `performance.vw_cwv_current` - Latest CWV with change tracking
- `performance.vw_poor_cwv` - Failing pages
- `performance.vw_cwv_trends` - 90-day trends
- `performance.vw_pages_for_cwv` - Prioritized collection queue

### Insight Views
- `gsc.vw_insights_actionable` - Pending insights
- `gsc.vw_insights_stats` - Insight distribution
- `gsc.vw_top_priority_actions` - High-priority actions
- `gsc.vw_action_performance` - Completed actions with outcomes

### Trends Views
- `trends.vw_keyword_trends_30d` - 30-day aggregations
- `trends.vw_rising_opportunities` - Recent rising queries
- `trends.vw_collection_health` - Collection monitoring

**Total: 30+ Views**

---

## Related Documentation

- **[Unified View Guide](guides/UNIFIED_VIEW_GUIDE.md)** - Deep dive into vw_unified_page_performance
- **[URL Discovery Guide](guides/URL_DISCOVERY_GUIDE.md)** - Auto-discovery system
- **[Content Intelligence Guide](guides/CONTENT_INTELLIGENCE_GUIDE.md)** - Semantic search and quality scoring
- **[SERP Tracking Guide](SERP_TRACKING_GUIDE.md)** - Position monitoring
- **[Actions Command Center](guides/ACTIONS_COMMAND_CENTER.md)** - Task management

---

**Last Updated:** 2025-11-28
**Schema Version:** 2.0

# URL Discovery & Auto-Monitoring Guide

**Automatic URL discovery and prioritization for Core Web Vitals monitoring**

---

## Overview

The **URL Discovery System** (`insights_core/url_discovery_sync.py`) automatically discovers URLs from your GSC and GA4 data and populates the `performance.monitored_pages` table for Core Web Vitals monitoring. This eliminates manual URL management and ensures you're always monitoring your most important pages.

### Key Benefits

- ✅ **Zero manual configuration** - URLs discovered automatically from traffic
- ✅ **Smart prioritization** - High-traffic, high-visibility pages monitored first
- ✅ **Auto-deactivation** - Stale pages (90+ days inactive) automatically removed
- ✅ **Multi-source** - Combines GSC + GA4 data for complete coverage
- ✅ **Configurable** - Control limits, priorities, and sync frequency

---

## How It Works

### 1. Discovery Process

```
┌─────────────────────────────────────────────────────────┐
│             URL Discovery Flow                           │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  gsc.fact_gsc_daily     gsc.fact_ga4_daily              │
│        ↓                        ↓                         │
│   Extract unique URLs     Extract unique page_paths      │
│        ↓                        ↓                         │
│   ┌─────────────────────────────┐                        │
│   │  Aggregate Metrics:         │                        │
│   │  - Total clicks             │                        │
│   │  - Total sessions           │                        │
│   │  - Avg position             │                        │
│   │  - Last seen date           │                        │
│   └───────────┬─────────────────┘                        │
│               ↓                                           │
│   ┌─────────────────────────────┐                        │
│   │  Calculate Priority Score   │                        │
│   │  (see formula below)        │                        │
│   └───────────┬─────────────────┘                        │
│               ↓                                           │
│   ┌─────────────────────────────┐                        │
│   │  Upsert to                  │                        │
│   │  performance.monitored_pages│                        │
│   └─────────────────────────────┘                        │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### 2. Priority Scoring Algorithm

URLs are prioritized using a weighted formula:

```python
# Component scores (each 0.0 to 1.0)
clicks_score = min(total_clicks / 1000, 1.0) * 0.40      # 40% weight
sessions_score = min(total_sessions / 500, 1.0) * 0.25   # 25% weight
position_score = max(0, (20 - avg_position) / 20) * 0.20 # 20% weight
recency_score = max(0, 1 - (days_since_last_seen / 90)) * 0.15  # 15% weight

# Final priority (0-100)
priority_score = (clicks_score + sessions_score + position_score + recency_score) * 100
```

**Interpretation:**
- **90-100**: Critical pages (homepage, top converters)
- **70-89**: High priority (popular content)
- **50-69**: Medium priority (steady traffic)
- **< 50**: Low priority (niche content)

**Example Calculations:**

| Page | Clicks | Sessions | Avg Pos | Days Ago | Priority |
|------|--------|----------|---------|----------|----------|
| Homepage | 5000 | 2000 | 1.2 | 1 | 98.3 |
| Top Blog Post | 800 | 300 | 3.5 | 2 | 86.7 |
| Product Page | 400 | 150 | 8.2 | 5 | 68.5 |
| Old Article | 50 | 20 | 15.0 | 60 | 22.1 |

### 3. Discovery Sources

URLs are discovered from three sources:

**Source: `gsc`**
- Extracted from `gsc.fact_gsc_daily`
- Any URL with clicks or impressions in lookback window
- Captures search-focused pages

**Source: `ga4`**
- Extracted from `gsc.fact_ga4_daily`
- Any page_path with sessions
- Captures all visited pages (including direct traffic, social, etc.)

**Source: `gsc+ga4`**
- URL appears in both datasets
- Highest confidence (both search and engagement data)
- Often highest priority

---

## Configuration

### Environment Variables

```bash
# URL Discovery Settings (in .env)
URL_DISCOVERY_ENABLED=true              # Enable auto-discovery
URL_DISCOVERY_LOOKBACK_DAYS=30          # How far back to analyze
URL_DISCOVERY_MIN_CLICKS=10             # Min clicks to consider
URL_DISCOVERY_MIN_SESSIONS=5            # Min sessions to consider
URL_DISCOVERY_MAX_NEW_URLS=500          # Max new URLs per sync run
URL_DISCOVERY_STALE_DAYS=90             # Deactivate if not seen in X days
```

### Sync Configuration

Default sync is part of the daily pipeline. To customize:

**File:** `config/scheduler_config.yaml`

```yaml
daily_pipeline:
  tasks:
    - name: url_discovery_sync
      enabled: true
      config:
        lookback_days: 30
        min_clicks: 10
        min_sessions: 5
        max_new_urls_per_run: 500
        stale_days_threshold: 90
```

---

## Usage

### Manual Sync

```bash
# Sync all properties
python -c "
from insights_core.url_discovery_sync import URLDiscoverySync
import asyncio

async def sync():
    syncer = URLDiscoverySync()
    results = await syncer.sync_all_properties(
        lookback_days=30,
        min_clicks=10,
        min_sessions=5
    )
    for result in results:
        print(f'{result.property}: {result.urls_discovered} discovered, '
              f'{result.urls_new} new, {result.urls_deactivated} deactivated')

asyncio.run(sync())
"
```

### Query Monitored Pages

```sql
-- Top priority pages for CWV monitoring
SELECT
    page_path,
    discovery_source,
    priority_score,
    total_clicks,
    total_sessions,
    ROUND(avg_position, 1) as avg_pos,
    last_seen_at,
    is_active
FROM performance.monitored_pages
WHERE property = 'https://example.com'
    AND is_active = TRUE
ORDER BY priority_score DESC
LIMIT 50;
```

### View Sync Statistics

```sql
-- Recent sync runs
SELECT
    property,
    COUNT(*) FILTER (WHERE discovery_source = 'gsc') as from_gsc,
    COUNT(*) FILTER (WHERE discovery_source = 'ga4') as from_ga4,
    COUNT(*) FILTER (WHERE discovery_source = 'gsc+ga4') as from_both,
    COUNT(*) FILTER (WHERE is_active = TRUE) as active,
    MAX(last_seen_at) as latest_data
FROM performance.monitored_pages
GROUP BY property;
```

---

## Integration with CWV Collection

Once URLs are in `performance.monitored_pages`, they're automatically queued for CWV collection:

### View: `performance.vw_pages_for_cwv`

```sql
CREATE VIEW performance.vw_pages_for_cwv AS
SELECT
    mp.page_id,
    mp.property,
    mp.page_path,
    mp.priority_score,
    mp.check_mobile,
    mp.check_desktop,
    cwv.last_check_date,
    cwv.performance_score
FROM performance.monitored_pages mp
LEFT JOIN (
    SELECT property, page_path, strategy,
           MAX(check_date) as last_check_date,
           (array_agg(performance_score ORDER BY check_date DESC))[1] as performance_score
    FROM performance.core_web_vitals
    GROUP BY property, page_path, strategy
) cwv ON mp.property = cwv.property AND mp.page_path = cwv.page_path
WHERE mp.is_active = TRUE
ORDER BY mp.priority_score DESC, cwv.last_check_date ASC NULLS FIRST;
```

**CWV Collection Script** (`scripts/collect_cwv_data.py`) uses this view to:
1. Prioritize unchecked pages first
2. Re-check high-priority pages more frequently
3. Skip low-priority pages when rate-limited

---

## Stale Page Deactivation

URLs not seen in `URL_DISCOVERY_STALE_DAYS` (default: 90) are automatically deactivated.

**Why?**
- Page deleted or redirected
- Content moved to new URL
- Seasonal content (reactivates when traffic returns)
- Saves CWV API quota for active pages

**Behavior:**
- `is_active` set to `FALSE`
- Page data retained for historical analysis
- Automatically reactivates if traffic returns

**Query Stale Pages:**

```sql
SELECT
    page_path,
    last_seen_at,
    CURRENT_DATE - last_seen_at::date as days_stale,
    total_clicks,
    total_sessions
FROM performance.monitored_pages
WHERE property = 'https://example.com'
    AND is_active = FALSE
    AND last_seen_at > CURRENT_DATE - INTERVAL '180 days'
ORDER BY last_seen_at DESC;
```

---

## Monitoring & Troubleshooting

### Check Sync Health

```sql
-- Last sync stats per property
SELECT
    property,
    COUNT(*) as total_monitored,
    COUNT(*) FILTER (WHERE is_active = TRUE) as active,
    MAX(last_seen_at) as latest_data,
    AVG(priority_score) as avg_priority,
    MIN(priority_score) as min_priority,
    MAX(priority_score) as max_priority
FROM performance.monitored_pages
GROUP BY property;
```

### Logs

Check scheduler logs for sync results:

```bash
docker logs gsc_scheduler | grep "URL Discovery"
```

Expected output:
```
INFO - URL Discovery: example.com - 1,234 discovered, 45 new, 12 updated, 8 deactivated
```

### Common Issues

**Issue: No URLs discovered**

Check:
1. GSC/GA4 data ingested? `SELECT COUNT(*) FROM gsc.fact_gsc_daily;`
2. Lookback window has data? Try increasing `lookback_days`
3. Thresholds too high? Lower `min_clicks` and `min_sessions`

**Issue: Too many low-priority URLs**

Increase thresholds:
```bash
URL_DISCOVERY_MIN_CLICKS=50
URL_DISCOVERY_MIN_SESSIONS=20
```

**Issue: Important page not discovered**

Manually add:
```sql
INSERT INTO performance.monitored_pages (
    page_id, property, page_path, discovery_source,
    is_active, check_mobile, check_desktop, priority_score
) VALUES (
    gen_random_uuid(),
    'https://example.com',
    '/important-page',
    'manual',
    TRUE,
    TRUE,
    TRUE,
    95.0  -- High priority
) ON CONFLICT (property, page_path) DO UPDATE
SET is_active = TRUE, discovery_source = 'manual';
```

---

## Best Practices

### 1. Start Conservative

Initial setup:
```bash
URL_DISCOVERY_MAX_NEW_URLS=100  # Start small
URL_DISCOVERY_MIN_CLICKS=50     # Higher threshold
```

After stabilization, expand:
```bash
URL_DISCOVERY_MAX_NEW_URLS=500
URL_DISCOVERY_MIN_CLICKS=10
```

### 2. Monitor Priority Distribution

Aim for:
- 5-10% critical (90-100)
- 15-25% high (70-89)
- 30-40% medium (50-69)
- 30-50% low (< 50)

### 3. Adjust for Site Size

**Small site (< 100 pages):**
```bash
URL_DISCOVERY_MIN_CLICKS=5
URL_DISCOVERY_MAX_NEW_URLS=100
```

**Large site (1000+ pages):**
```bash
URL_DISCOVERY_MIN_CLICKS=100
URL_DISCOVERY_MAX_NEW_URLS=1000
```

### 4. Segment by Template

Different page types need different thresholds:

```sql
-- Product pages (high priority)
UPDATE performance.monitored_pages
SET priority_score = priority_score * 1.2
WHERE page_path LIKE '/product/%'
    AND priority_score < 90;

-- Blog posts (lower priority)
UPDATE performance.monitored_pages
SET priority_score = priority_score * 0.8
WHERE page_path LIKE '/blog/%'
    AND priority_score > 50;
```

---

## API Reference

### Class: `URLDiscoverySync`

**File:** `insights_core/url_discovery_sync.py`

#### Methods

**`sync_all_properties()`**

```python
async def sync_all_properties(
    self,
    lookback_days: int = 30,
    min_clicks: int = 10,
    min_sessions: int = 5,
    max_new_urls_per_run: int = 500,
    stale_days_threshold: int = 90
) -> List[SyncResult]:
    """
    Discover URLs from all properties in warehouse.

    Returns:
        List of SyncResult with stats per property
    """
```

**`sync_property()`**

```python
async def sync_property(
    self,
    property_url: str,
    lookback_days: int = 30,
    min_clicks: int = 10,
    min_sessions: int = 5
) -> SyncResult:
    """
    Discover URLs for a single property.

    Returns:
        SyncResult with discovered/new/updated/deactivated counts
    """
```

#### Return Types

```python
@dataclass
class SyncResult:
    property: str
    urls_discovered: int    # Total unique URLs found
    urls_new: int           # Newly added to monitored_pages
    urls_updated: int       # Existing URLs with updated metrics
    urls_deactivated: int   # Stale URLs deactivated
    success: bool
    error_message: Optional[str] = None
```

---

## Related Documentation

- **[DATA_MODEL.md](../DATA_MODEL.md)** - `performance.monitored_pages` schema
- **[CWV Collection Script](../../scripts/collect_cwv_data.py)** - How discovered URLs are monitored
- **[ARCHITECTURE.md](../ARCHITECTURE.md)** - System overview

---

**Last Updated:** 2025-11-28

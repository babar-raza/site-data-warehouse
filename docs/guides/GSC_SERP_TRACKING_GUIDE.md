# GSC-Based SERP Position Tracking

## Overview

**SERP position tracking WITHOUT any API costs!**

Instead of paying for SERP APIs (ValueSERP, SerpAPI, etc.), you can use your existing Google Search Console data for position tracking. This gives you:

✅ **Completely FREE** - No API keys needed
✅ **Unlimited tracking** - No monthly query limits
✅ **Official Google data** - Direct from Search Console
✅ **Already integrated** - Uses existing GSC data collection

---

## How It Works

The platform automatically:

1. Extracts position data from your GSC `query_stats` table
2. Populates SERP tracking tables (`serp.queries`, `serp.position_history`)
3. Enables all SERP dashboards and alerts
4. Runs daily position change detection

---

## Quick Start

### Step 1: Ensure GSC Data Collection is Working

```bash
# Check if you have GSC data
psql -U postgres -d seo_warehouse -c "SELECT COUNT(*) FROM gsc.query_stats"

# Should show a count > 0
```

If you don't have GSC data yet:
```bash
celery -A services.tasks call collect_gsc_data --args='["https://yourdomain.com"]'
```

### Step 2: Run One-Time Sync

```bash
# Sync GSC data to SERP tables
python scripts/sync_gsc_to_serp.py
```

This will:
- Auto-discover keywords you're ranking for
- Create entries in `serp.queries` table
- Populate 30 days of position history
- Show you top keywords and opportunities

**Output Example:**
```
Queries Synced:    247
Positions Synced:  1,850

Top 10 Ranking Keywords:
1. Position #1.2: your brand name
   523 clicks, 1,234 impressions

2. Position #3.5: main product keyword
   184 clicks, 892 impressions
```

### Step 3: Verify in Grafana

Open the SERP Position Tracking dashboard:
```
http://localhost:3000/d/serp-tracking
```

You should now see:
- Position trends over time
- Top ranking keywords
- Position changes (drops/gains)
- Keywords by position range

---

## Features

### 1. Position Tracking

Automatically tracks positions for all queries with significant impressions (default: 10+).

**View Current Positions:**
```sql
SELECT
    query_text,
    AVG(position) as avg_position,
    SUM(impressions) as total_impressions,
    SUM(clicks) as total_clicks
FROM gsc.query_stats
WHERE property = 'https://yourdomain.com'
    AND data_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY query_text
ORDER BY SUM(impressions) DESC
LIMIT 20;
```

### 2. Position Change Detection

Automatically detects position changes and triggers alerts:

```bash
# Manual check for position changes
celery -A services.tasks call detect_position_changes_gsc --args='["https://yourdomain.com", 7]'
```

**Significant changes** (3+ positions, 100+ impressions) trigger alerts via Slack/Email.

### 3. Keyword Opportunities

Identifies easy-win keywords (ranking 11-20):

```bash
# Analyze opportunities
celery -A services.tasks call analyze_keyword_opportunities_gsc --args='["https://yourdomain.com"]'
```

Returns keywords with:
- Current position 11-20
- High impression volume
- Estimated traffic gain if improved

### 4. Automated Daily Sync

Position data syncs automatically every day at 9 AM (configured in Celery Beat).

**Manual sync:**
```bash
celery -A services.tasks call sync_serp_from_gsc --args='["https://yourdomain.com"]'

# Or sync all properties
celery -A services.tasks call sync_serp_from_gsc --args='["all"]'
```

---

## Configuration

### Environment Variables

```bash
# In .env file

# No SERP API keys needed!
# Just ensure GSC is configured:
GSC_PROPERTIES=https://yourdomain.com
GSC_CREDENTIALS_PATH=/path/to/gsc_credentials.json
```

### Minimum Impressions Filter

By default, only tracks queries with 10+ impressions to reduce noise.

**Adjust threshold:**
```python
# In scripts/sync_gsc_to_serp.py or Celery tasks
min_impressions = 20  # Higher = fewer keywords tracked
```

### Days of History

Default: 30 days of position history

**Adjust:**
```python
days_back = 60  # Track more history
```

---

## Limitations vs. SERP APIs

### ✅ What GSC-Based Tracking CAN Do

- Track positions for keywords you already rank for
- Detect position changes over time
- Identify ranking opportunities (11-20 positions)
- Trigger alerts for position drops
- Show historical position trends
- 100% FREE, unlimited

### ❌ What It CANNOT Do

- Track keywords you don't rank for (yet)
- Real-time position checks (48-hour GSC delay)
- Competitor position tracking
- Track positions beyond what GSC shows (usually top 100)
- Country/device-specific targeting (limited by GSC data structure)

---

## Comparison

| Feature | GSC-Based | ValueSERP | SerpAPI |
|---------|-----------|-----------|---------|
| **Cost** | $0 | $50/mo | $50/mo |
| **Monthly Limit** | Unlimited | 5,000 | 5,000 |
| **Free Tier** | ∞ | 100 | 100 |
| **Data Delay** | 48 hours | Real-time | Real-time |
| **Official Data** | ✅ Yes | ❌ No | ❌ No |
| **Competitor Tracking** | ❌ No | ✅ Yes | ✅ Yes |
| **Setup Required** | None | API Key | API Key |

---

## Hybrid Mode (Best of Both Worlds)

You can combine GSC + API tracking:

```python
# In your code
from insights_core.serp_tracker import SerpTracker

tracker = SerpTracker(
    use_gsc_data=True,       # Primary: Use GSC
    gsc_fallback=True,       # Fallback: Use GSC if API fails
    api_provider='valueserp', # Optional: Use API for specific cases
    api_key='your_key'       # Only needed for API calls
)
```

**Strategy:**
- Use GSC for 90% of keywords (free)
- Use API only for:
  - Keywords you don't rank for yet
  - Competitor analysis
  - Weekly deep-dive checks

---

## Dashboards & Alerts

### Available Dashboards

1. **SERP Position Tracking** (`/d/serp-tracking`)
   - Position trends
   - Top keywords
   - Position changes
   - Ranking distribution

2. **Keyword Opportunities** (custom query)
```sql
-- Keywords ranking 11-20 (quick wins)
SELECT
    query_text,
    AVG(position) as position,
    SUM(impressions) as impressions,
    SUM(clicks) as clicks
FROM gsc.query_stats
WHERE property = 'https://yourdomain.com'
    AND data_date >= CURRENT_DATE - INTERVAL '30 days'
    AND position BETWEEN 11 AND 20
GROUP BY query_text
HAVING SUM(impressions) > 100
ORDER BY SUM(impressions) DESC;
```

### Alert Configuration

Position drop alerts are automatically configured during seeding:

```python
# From scripts/setup/seed_data.py

alert_rules = [
    {
        'name': 'SERP Position Drop - High Priority',
        'type': 'serp_drop',
        'conditions': {'position_drop': 3},
        'severity': 'high',
        'channels': ['slack', 'email']
    }
]
```

---

## Troubleshooting

### No Data Showing Up

**Check if GSC data exists:**
```bash
psql -U postgres -d seo_warehouse -c "
    SELECT COUNT(*), MAX(data_date)
    FROM gsc.query_stats
    WHERE property = 'https://yourdomain.com'
"
```

**If count is 0:**
```bash
# Collect GSC data first
celery -A services.tasks call collect_gsc_data --args='["https://yourdomain.com"]'
```

### Queries Not Appearing in SERP Tables

**Check minimum impressions threshold:**
```sql
-- See queries below threshold
SELECT query_text, SUM(impressions) as total_imp
FROM gsc.query_stats
WHERE property = 'https://yourdomain.com'
    AND data_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY query_text
HAVING SUM(impressions) < 10
ORDER BY SUM(impressions) DESC;
```

**Lower the threshold:**
```bash
# Sync with lower threshold
python scripts/sync_gsc_to_serp.py
# Enter 5 when prompted for minimum impressions
```

### Position Changes Not Detected

GSC data has a 48-hour delay, so very recent changes won't appear immediately.

**Check data freshness:**
```sql
SELECT MAX(data_date) FROM gsc.query_stats;
```

---

## Advanced Usage

### Custom Analysis Queries

**Top Gainers (last 7 days):**
```sql
WITH current AS (
    SELECT query_text, AVG(position) as pos
    FROM gsc.query_stats
    WHERE property = 'https://yourdomain.com'
        AND data_date >= CURRENT_DATE - INTERVAL '3 days'
    GROUP BY query_text
),
previous AS (
    SELECT query_text, AVG(position) as pos
    FROM gsc.query_stats
    WHERE property = 'https://yourdomain.com'
        AND data_date BETWEEN CURRENT_DATE - INTERVAL '10 days' AND CURRENT_DATE - INTERVAL '4 days'
    GROUP BY query_text
)
SELECT
    c.query_text,
    p.pos as old_position,
    c.pos as new_position,
    (p.pos - c.pos) as improvement
FROM current c
JOIN previous p ON c.query_text = p.query_text
WHERE (p.pos - c.pos) > 3
ORDER BY improvement DESC
LIMIT 20;
```

### Python API

```python
from insights_core.gsc_serp_tracker import GSCBasedSerpTracker

tracker = GSCBasedSerpTracker()

# Get position changes
changes = await tracker.get_position_changes('https://yourdomain.com', days=7)

# Get top keywords
top = await tracker.get_top_ranking_keywords('https://yourdomain.com', position_max=10)

# Get opportunities
opps = await tracker.get_opportunity_keywords('https://yourdomain.com')
```

---

## Summary

✅ **Zero setup required** - Works with existing GSC data
✅ **Completely free** - No API keys or monthly costs
✅ **Automated** - Daily syncs, change detection, alerts
✅ **Production-ready** - Powers dashboards and notifications

**Next:** Add optional SERP API for competitor tracking or real-time checks if needed.

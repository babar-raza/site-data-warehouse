# SERP Position Tracking - Complete Guide

## Overview

This system supports **hybrid SERP tracking** that combines:
- **Primary**: Google Search Console data (FREE, unlimited)
- **Backup**: SerpStack API (100 requests/month)

This approach maximizes your free tier while providing flexibility for edge cases.

---

## Current Status

### ✅ What's Working NOW

**GSC-Based Tracking** - Fully operational and FREE:
- Position tracking for all ranked keywords
- Automated daily sync
- Position change detection
- Opportunity analysis (keywords ranking 11-20)
- No API costs, no rate limits

### ⚠️ SerpStack API Issue

The provided API key (`be4e441555...5b285a378a`) failed validation:
```
Error 101: Invalid access key
```

**Possible Causes**:
1. API key needs activation (check email for activation link)
2. Key was copied incorrectly
3. Account not fully set up
4. Free trial expired or not activated

**Action Required**:
- Visit https://serpstack.com/dashboard
- Verify account status
- Check if key needs activation
- Confirm free tier is active (100 requests/month)

---

## Usage Strategy

### Phase 1: GSC-Only Mode (Current - Working)

Use GSC data for all position tracking:

```bash
# Run one-time sync
python scripts/sync_gsc_to_serp.py

# View results in Grafana
# Dashboard: "SERP Position Tracking"
```

**What You Get**:
- Daily position updates for all ranked keywords
- Historical trends (30+ days)
- Position change alerts
- Opportunity keywords (easy wins)
- Zero cost

**Limitations**:
- 48-hour data delay (GSC limitation)
- Only tracks keywords you already rank for
- No competitor position tracking

### Phase 2: Hybrid Mode (Once API Key Works)

Use GSC as primary + API for specific cases:

**Use API For** (≈5-10 requests/month):
1. **Competitive analysis** - Track competitor positions
2. **New content** - Check positions before GSC updates
3. **High-priority keywords** - Real-time position checks
4. **Gaps** - Keywords not ranking yet (position 21+)

**Use GSC For** (unlimited):
1. Daily position tracking (90% of needs)
2. Historical analysis
3. Opportunity detection
4. Change alerts

---

## Configuration

### Current .env Settings

```env
# SERP API Provider
SERP_API_PROVIDER=serpstack

# API Key - get your free key at https://serpstack.com
SERPSTACK_API_KEY=your_serpstack_api_key_here

# Hybrid mode enabled
SERP_USE_GSC_DATA=true
SERP_GSC_FALLBACK=true

# Minimum impressions to track
SERP_MIN_IMPRESSIONS=10
```

### Switching to GSC-Only Mode

If you want to disable API entirely and use only GSC:

```env
SERP_API_PROVIDER=gsc-only
SERP_USE_GSC_DATA=true
# No API key needed
```

---

## Usage Examples

### 1. Initial Setup - Sync GSC Data

```bash
# One-time sync to populate SERP tables
python scripts/sync_gsc_to_serp.py

# Example output:
# ✓ Synced 1,247 queries
# ✓ Synced 37,410 position records
# Data source: GSC
```

### 2. Daily Automated Tracking

The system automatically runs daily (configured in Celery Beat):

```python
# services/gsc_serp_tasks.py
# Runs daily at 9 AM
@shared_task
def sync_serp_from_gsc_task(property_url='all', min_impressions=10):
    """Sync SERP positions from GSC"""
    # Automatically tracks all properties
```

### 3. Check Position Changes

```python
from insights_core.gsc_serp_tracker import GSCBasedSerpTracker

tracker = GSCBasedSerpTracker()
changes = await tracker.get_position_changes(
    property_url='https://yourdomain.com',
    days=7
)

for change in changes[:10]:
    print(f"{change['query_text']}: {change['previous_position']:.1f} → {change['current_position']:.1f}")
```

### 4. Find Opportunity Keywords

```python
# Keywords ranking 11-20 (easy wins)
opportunities = await tracker.get_opportunity_keywords(
    property_url='https://yourdomain.com',
    position_min=11,
    position_max=20
)

for opp in opportunities[:10]:
    print(f"#{opp['avg_position']:.1f} - {opp['query_text']}")
    print(f"  Potential gain: +{opp['potential_gain']} clicks/month")
```

### 5. Using API (When Available)

```python
from insights_core.serp_tracker import SerpTracker

# Initialize with hybrid mode
tracker = SerpTracker(
    api_provider='serpstack',
    api_key=os.getenv('SERPSTACK_API_KEY'),
    use_gsc_data=True,      # Use GSC as primary
    gsc_fallback=True       # Fallback to GSC if API fails
)

# Track a specific query (uses API if GSC doesn't have it)
await tracker.track_query(
    query_text='your target keyword',
    property='https://yourdomain.com',
    check_frequency_hours=168  # Weekly check
)
```

---

## API Usage Optimization

### Monthly Budget: 100 Requests

**Recommended Allocation**:

| Use Case | Requests/Month | Frequency |
|----------|---------------|-----------|
| Competitor tracking (top 10 keywords) | 40 | 4 checks/keyword |
| New content validation | 20 | As needed |
| High-priority keyword monitoring | 30 | Weekly checks |
| Ad-hoc analysis | 10 | Reserve |
| **Total** | **100** | |

### Rate Limiting

The system automatically:
- Tracks API usage
- Falls back to GSC if limit exceeded
- Warns when <10 requests remaining

```python
# Check remaining requests
from insights_core.serp_tracker import SerpStackProvider

provider = SerpStackProvider(api_key)
account_info = await provider.get_account_info()

print(f"Remaining: {account_info['requests_remaining']}/100")
```

---

## Troubleshooting

### Issue: API Key Not Working

**Error**: `401 - Invalid access key`

**Solutions**:
1. Check SerpStack dashboard: https://serpstack.com/dashboard
2. Verify account is activated (check email)
3. Confirm free tier is enabled
4. Try regenerating API key
5. Use GSC-only mode meanwhile:
   ```env
   SERP_API_PROVIDER=gsc-only
   ```

### Issue: No Data in SERP Tables

**Check**:
1. GSC data exists in `gsc.query_stats`:
   ```sql
   SELECT COUNT(*) FROM gsc.query_stats WHERE data_date >= CURRENT_DATE - 7;
   ```

2. Run initial sync:
   ```bash
   python scripts/sync_gsc_to_serp.py
   ```

3. Check Celery is running:
   ```bash
   celery -A services.tasks worker -l info
   ```

### Issue: Positions Not Updating

**Causes**:
- GSC has 48-hour delay (normal)
- Celery beat not running
- Minimum impressions filter too high

**Fix**:
```bash
# Manual sync
python scripts/sync_gsc_to_serp.py

# Check last sync
SELECT MAX(checked_at) FROM serp.position_history;
```

### Issue: Missing Keywords

**Check Filter**:
```env
# Lower threshold to track more keywords
SERP_MIN_IMPRESSIONS=5  # Default: 10
```

---

## Database Schema

### Tables Created

```sql
-- Tracked queries
serp.queries
  - query_id (PK)
  - query_text
  - property
  - target_page_path
  - is_active
  - data_source ('gsc' or 'api')

-- Position history
serp.position_history
  - query_id (FK)
  - position
  - impressions
  - clicks
  - ctr
  - checked_at
  - data_source
```

### Queries

**Top Position Changes**:
```sql
SELECT
    q.query_text,
    ph1.position as current_position,
    ph2.position as previous_position,
    (ph2.position - ph1.position) as change
FROM serp.position_history ph1
JOIN serp.position_history ph2 ON ph1.query_id = ph2.query_id
JOIN serp.queries q ON q.query_id = ph1.query_id
WHERE ph1.checked_at >= CURRENT_DATE - 3
  AND ph2.checked_at BETWEEN CURRENT_DATE - 10 AND CURRENT_DATE - 3
  AND ABS(ph2.position - ph1.position) >= 2
ORDER BY ABS(ph2.position - ph1.position) DESC
LIMIT 20;
```

**Opportunity Keywords**:
```sql
SELECT
    query_text,
    AVG(position) as avg_position,
    SUM(impressions) as total_impressions
FROM serp.position_history ph
JOIN serp.queries q ON q.query_id = ph.query_id
WHERE checked_at >= CURRENT_DATE - 30
  AND position BETWEEN 11 AND 20
GROUP BY query_text
HAVING SUM(impressions) > 50
ORDER BY SUM(impressions) DESC;
```

---

## Alternative SERP APIs

If SerpStack doesn't work, consider:

| Provider | Free Tier | Cost |
|----------|-----------|------|
| **SerpAPI** | 100 searches | $50/mo (5,000) |
| **ValueSERP** | 100 searches | $50/mo (10,000) |
| **ScraperAPI** | 1,000 searches | $49/mo (100,000) |
| **DataForSEO** | $1 trial | $0.0006/search |
| **SearchAPI.io** | 100 searches | $29/mo (3,000) |

**Recommendation**: Stick with GSC-only mode (FREE) unless you specifically need:
- Competitor tracking
- Real-time positions
- Keywords you don't rank for yet

---

## Next Steps

### Immediate (GSC-Only Mode)

1. ✅ Run initial sync:
   ```bash
   python scripts/sync_gsc_to_serp.py
   ```

2. ✅ View SERP dashboards in Grafana:
   - Position trends
   - Change alerts
   - Opportunities

3. ✅ Set up Celery Beat for daily sync (if not running)

### When API Key Works

1. Test API key:
   ```bash
   python scripts/test_serpstack_api.py YOUR_API_KEY
   ```

2. Update .env with verified key

3. Switch to hybrid mode:
   ```env
   SERP_API_PROVIDER=serpstack
   SERP_USE_GSC_DATA=true
   SERP_GSC_FALLBACK=true
   ```

4. Use API strategically (5-10 requests/month)

---

## Summary

**Current Setup** ✅:
- ✅ GSC-based tracking (FREE, unlimited)
- ✅ Daily automated sync
- ✅ Position change detection
- ✅ Opportunity analysis
- ⚠️ SerpStack API (needs key verification)

**You Have Everything You Need**:
- Position tracking works NOW with GSC data
- No API required for 90% of use cases
- API is optional enhancement for edge cases

**Action Required**:
1. Run sync: `python scripts/sync_gsc_to_serp.py`
2. View dashboards in Grafana
3. Verify SerpStack API key at https://serpstack.com/dashboard
4. Switch to hybrid mode once API key works

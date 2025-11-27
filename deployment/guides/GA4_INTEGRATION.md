# Google Analytics 4 Integration Guide

Quick reference for integrating Google Analytics 4 with your GSC Data Warehouse.

## Prerequisites

- ✅ Google Cloud Project created
- ✅ Google Analytics Data API enabled
- ✅ Service account created with JSON credentials
- ✅ Administrator or Viewer access to GA4 properties

**Don't have these?** See [GCP_SETUP_GUIDE.md](GCP_SETUP_GUIDE.md) first.

---

## Overview

This guide covers:
1. Adding service account to GA4 properties
2. Finding and configuring Property IDs
3. Testing GA4 data access
4. Understanding GA4 data collection
5. Troubleshooting common issues

---

## Step 1: Get Service Account Email

Your service account email from GCP Console looks like:
```
gsc-warehouse-sa@gsc-data-warehouse-123456.iam.gserviceaccount.com
```

**Find it:**
1. Go to [GCP Console - Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Copy the email address from the list
3. Keep this handy for the next steps

**Note:** You can use the same service account for both GSC and GA4.

---

## Step 2: Add Service Account to GA4 Property

### For Each Property You Want to Monitor:

#### 1. Open Google Analytics
Navigate to [Google Analytics](https://analytics.google.com)

#### 2. Access Admin Panel
Click **"Admin"** (gear icon ⚙️) in the bottom-left corner

#### 3. Select Account and Property
- **Account:** Choose your organization/account
- **Property:** Select the GA4 property you want to grant access to

#### 4. Open Property Access Management
In the **"Property"** column (middle), click **"Property Access Management"**

#### 5. Add Service Account User
1. Click **"+ ADD USERS"** button (top-right, blue button)
2. In the email field, enter your service account email:
   ```
   gsc-warehouse-sa@your-project.iam.gserviceaccount.com
   ```
3. Select user roles:
   - **✅ Viewer:** Recommended - Allows data access only
   - **Editor:** Allows configuration changes (usually unnecessary)
   - **Administrator:** Full access (not recommended for service accounts)

4. **Uncheck** "Notify this user by email" (service accounts can't receive emails)

5. Click **"ADD"** button

#### 6. Verify
The service account should appear in the users list with "Viewer" role.

### Repeat for All Properties
If you monitor multiple GA4 properties, repeat steps 2-5 for each property.

---

## Step 3: Find Your Property ID

### Method 1: Via Admin Panel

1. In Google Analytics, click **"Admin"** (gear icon)
2. Select your **Property** in the middle column
3. Click **"Property Settings"** (first option in Property column)
4. Find **"Property ID"** near the top
   - Format: 9-digit number (e.g., `123456789`)

### Method 2: Via Property Details

1. Click **"Admin"**
2. In the **Property** column, look at the property name
3. The property ID is shown below the property name in gray text

### Method 3: Via URL

When viewing any report in GA4, check the URL:
```
https://analytics.google.com/analytics/web/#/p123456789/reports/...
                                                 ^^^^^^^^^
                                                 Property ID
```

### Multiple Properties

If you have multiple properties, note each Property ID:

| Property Name | Property ID |
|---------------|-------------|
| Main Website | 123456789 |
| Blog | 987654321 |
| Docs Site | 456789123 |

---

## Step 4: Configure Application

### Update .env File

```bash
# Single GA4 property
GA4_PROPERTY_ID=123456789
GA4_CREDENTIALS_FILE=/secrets/gsc_sa.json

# If using separate credentials for GA4 (optional)
# GA4_CREDENTIALS_FILE=/secrets/ga4_sa.json
```

### Multiple Properties (Advanced)

For multiple GA4 properties, edit `ingestors/ga4/config.yaml`:

```yaml
ga4:
  properties:
    - property_id: "123456789"
      name: "main-website"
      enabled: true

    - property_id: "987654321"
      name: "blog"
      enabled: true

    - property_id: "456789123"
      name: "docs"
      enabled: true

  credentials_file: "/secrets/gsc_sa.json"

  # Metrics to collect
  metrics:
    - name: "sessions"
    - name: "totalUsers"
    - name: "screenPageViews"
    - name: "conversions"
    - name: "bounceRate"
    - name: "averageSessionDuration"

  # Dimensions
  dimensions:
    - name: "date"
    - name: "pagePath"
    - name: "deviceCategory"
```

---

## Step 5: Test GA4 Access

### Test 1: Python API Test

Create `test_ga4_access.py`:

```python
#!/usr/bin/env python3
"""Test GA4 API access with service account"""

import json
import os
from google.oauth2 import service_account
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Metric, Dimension

def test_ga4_access():
    # Configuration
    property_id = os.getenv('GA4_PROPERTY_ID', '123456789')
    creds_path = 'secrets/gsc_sa.json'

    if not os.path.exists(creds_path):
        print(f"❌ Error: {creds_path} not found")
        return False

    try:
        # Load credentials
        with open(creds_path, 'r') as f:
            creds_info = json.load(f)

        credentials = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=['https://www.googleapis.com/auth/analytics.readonly']
        )

        # Create client
        client = BetaAnalyticsDataClient(credentials=credentials)

        # Run simple query (last 7 days)
        request = RunReportRequest(
            property=f"properties/{property_id}",
            date_ranges=[DateRange(start_date="7daysAgo", end_date="yesterday")],
            metrics=[Metric(name="sessions")],
            dimensions=[Dimension(name="date")]
        )

        response = client.run_report(request)

        print("✅ GA4 API Connection Successful")
        print(f"\nProperty ID: {property_id}")
        print(f"Rows returned: {len(response.rows)}")

        if response.rows:
            print("\nSample data (last 3 days):")
            for row in response.rows[-3:]:
                date = row.dimension_values[0].value
                sessions = row.metric_values[0].value
                print(f"  {date}: {sessions} sessions")
        else:
            print("\n⚠️  Warning: No data returned")
            print("This could mean:")
            print("  - Property has no recent data")
            print("  - Service account lacks permissions")
            print("  - Property ID is incorrect")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    test_ga4_access()
```

Run the test:
```bash
export GA4_PROPERTY_ID=123456789  # Your property ID
python test_ga4_access.py
```

**Expected Output:**
```
✅ GA4 API Connection Successful

Property ID: 123456789
Rows returned: 7

Sample data (last 3 days):
  20241118: 1234 sessions
  20241119: 1456 sessions
  20241120: 1389 sessions
```

### Test 2: Data Collection Test

Run GA4 data extraction:

```bash
# Test collection (last 7 days)
python ingestors/ga4/ga4_extractor.py --days 7
```

**Expected Output:**
```
Starting GA4 Data Extractor
✅ Loaded credentials from secrets/gsc_sa.json
✅ Connected to GA4 API
✅ Property: 123456789
✅ Collecting data: 2024-11-14 to 2024-11-20
  • Processing: 100%
✅ Ingested 845 rows
✅ Data written to warehouse
```

### Test 3: Database Verification

Check data was stored:

```sql
-- Connect to database
psql $WAREHOUSE_DSN

-- Check row counts
SELECT
    property_id,
    COUNT(*) as row_count,
    MIN(date) as earliest_date,
    MAX(date) as latest_date,
    SUM(sessions) as total_sessions
FROM gsc.fact_ga4_daily
GROUP BY property_id
ORDER BY property_id;
```

**Expected Output:**
```
 property_id | row_count | earliest_date | latest_date | total_sessions
-------------+-----------+---------------+-------------+----------------
   123456789 |       845 | 2024-11-14    | 2024-11-20  |          8567
```

---

## Understanding GA4 Data Collection

### Available Metrics

The warehouse collects these GA4 metrics by default:

| Metric | Description | Field Name |
|--------|-------------|------------|
| Sessions | Total sessions | `sessions` |
| Users | Total users | `total_users` |
| Page Views | Screen/page views | `page_views` |
| Conversions | Conversion events | `conversions` |
| Bounce Rate | Percentage of bounced sessions | `bounce_rate` |
| Avg. Duration | Average session duration (seconds) | `avg_session_duration` |

### Available Dimensions

| Dimension | Description | Example |
|-----------|-------------|---------|
| Date | Calendar date | `2024-11-20` |
| Page Path | URL path | `/products/widget` |
| Device Category | Device type | `desktop`, `mobile`, `tablet` |
| Country | User country | `United States`, `Canada` |
| Source | Traffic source | `google`, `direct` |

### Data Granularity

**Daily Aggregation:**
- Data is collected at the day + page level
- Metrics are summed per day per page
- Similar to GSC data structure for easy joining

**Example:**
```sql
SELECT
    date,
    page_path,
    sessions,
    page_views,
    conversions
FROM gsc.fact_ga4_daily
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY date DESC, sessions DESC;
```

---

## Troubleshooting

### Issue: "User does not have sufficient permissions"

**Symptoms:**
```
Error 403: User does not have sufficient permissions
```

**Causes:**
1. Service account not added to GA4 property
2. Insufficient permission level
3. Wrong property ID

**Solutions:**

**Check 1:** Verify service account is added
1. Go to GA4 → Admin → Property Access Management
2. Confirm service account email is listed
3. Permission should be "Viewer" or higher

**Check 2:** Check property ID
```bash
# Verify property ID in .env
cat .env | grep GA4_PROPERTY_ID
```

**Check 3:** Re-add with Viewer permissions
1. Remove service account from GA4
2. Wait 2-3 minutes
3. Re-add with "Viewer" role

---

### Issue: "Property not found"

**Symptoms:**
```
Error: Property 'properties/123456789' not found
```

**Causes:**
1. Wrong property ID
2. Property was deleted
3. No access to property

**Solutions:**

**Check 1:** Verify property ID
1. Go to GA4 → Admin → Property Settings
2. Confirm Property ID matches your configuration
3. Property ID should be 9 digits (no spaces)

**Check 2:** Check property access
1. Admin → Property Access Management
2. Ensure service account is listed
3. Try accessing the property in GA4 web interface first

---

### Issue: "No data returned"

**Symptoms:**
```
✅ GA4 API Connection Successful
Rows returned: 0
```

**Causes:**
1. Property has no data yet (new property)
2. Date range has no data
3. Service account lacks data read permission

**Solutions:**

**Check 1:** Verify property has data
1. Open GA4 web interface
2. Go to Reports → Realtime
3. Confirm property is receiving data

**Check 2:** Try wider date range
```bash
# Try last 30 days instead of 7
python ingestors/ga4/ga4_extractor.py --days 30
```

**Check 3:** Check data retention settings
1. GA4 → Admin → Data Settings → Data Retention
2. Ensure data retention is not set too short

---

### Issue: "API not enabled"

**Symptoms:**
```
Error: Google Analytics Data API has not been used in project
```

**Cause:** API not enabled in GCP project

**Solution:**
1. Go to [GCP API Library](https://console.cloud.google.com/apis/library)
2. Search: "Google Analytics Data API"
3. Click **ENABLE**
4. Also enable: "Google Analytics Admin API" (optional)
5. Wait 2-3 minutes
6. Try again

---

### Issue: "Invalid credentials"

**Symptoms:**
```
Error: invalid_grant: Invalid JWT Signature
```

**Causes:**
1. Wrong service account JSON file
2. Corrupted JSON
3. Using credentials from different project

**Solutions:**

**Check 1:** Validate JSON
```bash
cat secrets/gsc_sa.json | python -m json.tool
```

**Check 2:** Verify project ID
```bash
cat secrets/gsc_sa.json | grep project_id
```

**Check 3:** Download fresh credentials
1. GCP Console → Service Accounts
2. Select service account
3. Keys → Add Key → Create new key → JSON
4. Replace secrets/gsc_sa.json

---

### Issue: "Quota exceeded"

**Symptoms:**
```
Error 429: Quota exceeded for quota metric 'Requests' and limit 'Requests per day'
```

**GA4 API Limits:**
- **25,000 requests per day** per property (standard)
- **10 concurrent requests** per property
- **250,000 requests per day** (with Analytics 360)

**Solutions:**

**Option 1:** Reduce collection frequency
```bash
# Collect daily instead of hourly
# In scheduler/scheduler.py
schedule.every().day.at("03:00").do(collect_ga4_data)
```

**Option 2:** Request quota increase
1. Go to [GCP Console - Quotas](https://console.cloud.google.com/iam-admin/quotas)
2. Filter: "Analytics Data API"
3. Select quota to increase
4. Click "EDIT QUOTAS"
5. Submit request

**Option 3:** Optimize queries
- Collect less data per request
- Use longer date ranges (batching)
- Cache results when possible

---

### Issue: "Property is GA4 but uses old API"

**Symptoms:**
```
Error: This property is not compatible with this API
```

**Cause:** Using old Universal Analytics API for GA4 property

**Solution:**

Ensure you're using the correct API:

**✅ Correct (GA4):**
```python
from google.analytics.data_v1beta import BetaAnalyticsDataClient
```

**❌ Wrong (Universal Analytics):**
```python
from googleapiclient.discovery import build
service = build('analytics', 'v3', credentials=credentials)
```

---

## Data Collection Schedule

### Manual Collection

```bash
# Last 7 days
python ingestors/ga4/ga4_extractor.py --days 7

# Last 30 days
python ingestors/ga4/ga4_extractor.py --days 30

# Specific date range
python ingestors/ga4/ga4_extractor.py \
    --start-date 2024-11-01 \
    --end-date 2024-11-20

# Specific property
python ingestors/ga4/ga4_extractor.py \
    --property-id 123456789 \
    --days 7
```

### Automated Collection

Edit `scheduler/scheduler.py`:

```python
# Daily collection (recommended)
schedule.every().day.at("03:00").do(collect_ga4_data)

# Every 6 hours
schedule.every(6).hours.do(collect_ga4_data)
```

Or use cron:
```cron
# Daily at 3 AM
0 3 * * * cd /opt/gsc-warehouse && python ingestors/ga4/ga4_extractor.py --days 7
```

---

## GA4 vs GSC Data Comparison

### Understanding the Difference

**Google Search Console (GSC):**
- Search engine visibility data
- Impressions, clicks, position in search results
- Query-level data (what users searched)
- Pre-click metrics

**Google Analytics 4 (GA4):**
- On-site behavior data
- Sessions, page views, conversions
- User engagement and behavior
- Post-click metrics

### Unified View

The warehouse joins GSC + GA4 data:

```sql
SELECT
    u.page_path,
    u.date,
    -- GSC metrics (pre-click)
    u.gsc_impressions,
    u.gsc_clicks,
    u.gsc_ctr,
    u.gsc_position,
    -- GA4 metrics (post-click)
    u.ga_sessions,
    u.ga_page_views,
    u.ga_conversions,
    u.ga_bounce_rate,
    -- Hybrid insights
    u.opportunity_index,
    u.quality_score
FROM gsc.vw_unified_page_performance u
WHERE u.date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY u.date DESC, u.gsc_clicks DESC;
```

---

## Advanced Configuration

### Custom Metrics

Edit `ingestors/ga4/config.yaml` to collect additional metrics:

```yaml
metrics:
  # Standard metrics
  - name: "sessions"
  - name: "totalUsers"
  - name: "conversions"

  # Custom events (if configured in GA4)
  - name: "eventCount"
    filter: "eventName=sign_up"
    alias: "signups"

  - name: "eventCount"
    filter: "eventName=purchase"
    alias: "purchases"

  # E-commerce metrics
  - name: "ecommercePurchases"
  - name: "totalRevenue"
```

### Custom Dimensions

```yaml
dimensions:
  - name: "date"
  - name: "pagePath"
  - name: "deviceCategory"

  # Traffic source dimensions
  - name: "sessionSource"
  - name: "sessionMedium"
  - name: "sessionCampaignName"

  # User dimensions
  - name: "country"
  - name: "city"
  - name: "language"
```

### Filters

Apply filters to reduce data volume:

```yaml
filters:
  # Only collect desktop traffic
  - dimension: "deviceCategory"
    operator: "EXACT"
    value: "desktop"

  # Exclude internal traffic
  - dimension: "country"
    operator: "NOT_EQUALS"
    value: "Internal"

  # Only pages with conversions
  - metric: "conversions"
    operator: "GREATER_THAN"
    value: "0"
```

---

## Security Best Practices

### 1. Credential Security

**Do:**
- ✅ Store JSON in `secrets/` directory (gitignored)
- ✅ Set file permissions to 600
- ✅ Use same service account for GSC and GA4
- ✅ Rotate keys every 90 days

**Don't:**
- ❌ Commit credentials to git
- ❌ Share credentials via email
- ❌ Use personal Google account
- ❌ Grant "Administrator" role unnecessarily

### 2. Permission Levels

**Recommended:**
- **Viewer:** Read-only data access (perfect for data collection)

**Not Recommended:**
- **Editor:** Allows property configuration changes
- **Administrator:** Full control (only for humans, not service accounts)

### 3. Data Access Monitoring

Monitor service account activity:

```sql
-- Check last GA4 data collection
SELECT MAX(ingested_at) as last_collection
FROM gsc.fact_ga4_daily;

-- Check for data gaps
SELECT date
FROM generate_series(
    (SELECT MIN(date) FROM gsc.fact_ga4_daily),
    CURRENT_DATE,
    '1 day'
) AS date
WHERE date NOT IN (SELECT DISTINCT date FROM gsc.fact_ga4_daily)
ORDER BY date DESC;
```

### 4. Audit Logs

Enable audit logging in GCP:

1. GCP Console → Logging
2. Create log sink for Analytics Data API
3. Monitor for unusual access patterns

---

## Next Steps

✅ **Completed:** GA4 integration

**Continue to:**
- [GSC_INTEGRATION.md](GSC_INTEGRATION.md) - Integrate Google Search Console
- [SETUP_GUIDE.md](SETUP_GUIDE.md) - Complete application setup
- [MONITORING_GUIDE.md](MONITORING_GUIDE.md) - Setup monitoring

---

## Quick Reference

### Configuration Checklist

- [ ] Service account created in GCP
- [ ] Google Analytics Data API enabled
- [ ] Service account JSON downloaded to `secrets/gsc_sa.json`
- [ ] Service account added to GA4 property (Viewer role)
- [ ] Property ID configured in `.env`
- [ ] Test script confirms access
- [ ] Initial data collection successful
- [ ] Data visible in database

### Important Files

```
secrets/
  └── gsc_sa.json           # Service account credentials

ingestors/ga4/
  ├── ga4_extractor.py      # Main data collector
  └── config.yaml           # GA4 configuration

.env                        # Configuration
```

### Key Configuration

```bash
# .env
GA4_PROPERTY_ID=123456789
GA4_CREDENTIALS_FILE=/secrets/gsc_sa.json
```

### Useful Commands

```bash
# Test API access
python test_ga4_access.py

# Collect last 7 days
python ingestors/ga4/ga4_extractor.py --days 7

# Check database
psql $WAREHOUSE_DSN -c "SELECT property_id, COUNT(*), SUM(sessions) FROM gsc.fact_ga4_daily GROUP BY property_id;"
```

---

## Support

**Issues?**
- Check [Troubleshooting](#troubleshooting) section above
- See [GCP_SETUP_GUIDE.md](GCP_SETUP_GUIDE.md) for GCP-specific issues
- Review [docs/TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md) for general issues

**API Documentation:**
- [GA4 Data API Reference](https://developers.google.com/analytics/devguides/reporting/data/v1)
- [GA4 Admin API Reference](https://developers.google.com/analytics/devguides/config/admin/v1)
- [Service Account Authentication](https://cloud.google.com/iam/docs/service-accounts)

# Google Search Console Integration Guide

Quick reference for integrating Google Search Console with your GSC Data Warehouse.

## Prerequisites

- ✅ Google Cloud Project created
- ✅ Google Search Console API enabled
- ✅ Service account created with JSON credentials
- ✅ Owner or Full access to GSC properties

**Don't have these?** See [GCP_SETUP_GUIDE.md](GCP_SETUP_GUIDE.md) first.

---

## Overview

This guide covers:
1. Adding service account to GSC properties
2. Configuring property URLs
3. Testing GSC data access
4. Troubleshooting common issues

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

---

## Step 2: Add Service Account to GSC Property

### For Each Property You Want to Monitor:

#### 1. Open Google Search Console
Navigate to [Google Search Console](https://search.google.com/search-console)

#### 2. Select Property
Click the **property dropdown** (top-left) and select your property

#### 3. Access Settings
Click **"Settings"** in the left sidebar (gear icon ⚙️)

#### 4. Manage Users
Scroll to **"Users and permissions"** section

#### 5. Add User
1. Click **"ADD USER"** button
2. Enter your service account email:
   ```
   gsc-warehouse-sa@your-project.iam.gserviceaccount.com
   ```
3. Choose permission level:
   - **✅ Full:** Recommended - Allows data access and some property management
   - **Restricted:** Read-only data access

4. Click **"ADD"**

#### 6. Verify
The service account should appear in the users list with the granted permission level.

### Repeat for All Properties
If you monitor multiple websites, repeat steps 2-5 for each GSC property.

---

## Step 3: Configure Property URLs

### Understanding Property Formats

Google Search Console uses specific URL formats:

#### Domain Properties
Format: `sc-domain:example.com`

**Example:**
- GSC shows: `example.com`
- Use in config: `sc-domain:example.com`

#### URL Prefix Properties
Format: `sc-domain:https://example.com`

**Examples:**
- GSC shows: `https://example.com/`
- Use in config: `sc-domain:https://example.com`

- GSC shows: `http://example.com/`
- Use in config: `sc-domain:http://example.com`

### Find Your Property URL

1. Go to [Google Search Console](https://search.google.com/search-console)
2. Click property dropdown
3. Note the format of your property name

**Domain Property Example:**
- Shows: `example.com` with 🌐 icon
- Use: `sc-domain:example.com`

**URL Prefix Example:**
- Shows: `https://example.com/` with 🔗 icon
- Use: `sc-domain:https://example.com`

### Update Configuration

Edit your `.env` file:

```bash
# Single property
GSC_PROPERTIES=sc-domain:example.com

# Multiple properties (comma-separated, no spaces)
GSC_PROPERTIES=sc-domain:example.com,sc-domain:blog.example.com,sc-domain:docs.example.com

# Mixed domain and URL prefix
GSC_PROPERTIES=sc-domain:example.com,sc-domain:https://old-site.example.com
```

**Important:** No spaces between comma-separated values!

---

## Step 4: Test GSC Access

### Test 1: Python API Test

Create `test_gsc_access.py`:

```python
#!/usr/bin/env python3
"""Test GSC API access with service account"""

import json
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

def test_gsc_access():
    # Load credentials
    creds_path = 'secrets/gsc_sa.json'

    if not os.path.exists(creds_path):
        print(f"❌ Error: {creds_path} not found")
        return False

    try:
        with open(creds_path, 'r') as f:
            creds_info = json.load(f)

        credentials = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=['https://www.googleapis.com/auth/webmasters.readonly']
        )

        # Build service
        service = build('searchconsole', 'v1', credentials=credentials)

        # List accessible sites
        sites = service.sites().list().execute()
        site_list = sites.get('siteEntry', [])

        print("✅ GSC API Connection Successful")
        print(f"\nAccessible Properties: {len(site_list)}")

        for site in site_list:
            url = site['siteUrl']
            permission = site['permissionLevel']
            print(f"  • {url} ({permission})")

        if not site_list:
            print("\n⚠️  Warning: No properties accessible")
            print("Make sure you added the service account to your GSC properties")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    test_gsc_access()
```

Run the test:
```bash
python test_gsc_access.py
```

**Expected Output:**
```
✅ GSC API Connection Successful

Accessible Properties: 2
  • sc-domain:example.com (siteOwner)
  • sc-domain:blog.example.com (siteFullUser)
```

### Test 2: Data Collection Test

Run a small data collection test:

```bash
# Test last 7 days
python ingestors/api/gsc_api_ingestor.py \
    --date-start $(date -d '7 days ago' +%Y-%m-%d) \
    --date-end $(date -d '1 day ago' +%Y-%m-%d)
```

**Expected Output:**
```
Starting GSC API Ingestor
✅ Loaded credentials from secrets/gsc_sa.json
✅ Connected to GSC API
✅ Processing 2 properties
  • sc-domain:example.com: 1,234 rows ingested
  • sc-domain:blog.example.com: 567 rows ingested
✅ Total: 1,801 rows ingested
```

### Test 3: Database Verification

Check data was stored:

```sql
-- Connect to database
psql $WAREHOUSE_DSN

-- Check row counts
SELECT
    property,
    COUNT(*) as row_count,
    MIN(date) as earliest_date,
    MAX(date) as latest_date
FROM gsc.fact_gsc_daily
GROUP BY property
ORDER BY property;
```

**Expected Output:**
```
          property           | row_count | earliest_date | latest_date
-----------------------------+-----------+---------------+-------------
 sc-domain:blog.example.com  |       567 | 2024-11-14    | 2024-11-20
 sc-domain:example.com       |      1234 | 2024-11-14    | 2024-11-20
```

---

## Troubleshooting

### Issue: "User does not have sufficient permissions"

**Symptoms:**
```
Error 403: User does not have sufficient permissions for this profile
```

**Causes:**
1. Service account not added to GSC property
2. Wrong property URL format
3. Insufficient permission level

**Solutions:**

**Check 1:** Verify service account is added
1. Go to GSC → Settings → Users and permissions
2. Confirm service account email is listed
3. Permission should be "Full" or "Restricted"

**Check 2:** Verify property URL format
```python
# Test different formats
properties_to_try = [
    'sc-domain:example.com',
    'sc-domain:https://example.com',
    'sc-domain:http://example.com',
    'https://example.com/',
]
```

**Check 3:** Re-add with Full permissions
1. Remove service account from GSC
2. Wait 2-3 minutes
3. Re-add with "Full" permission level

---

### Issue: "No properties accessible"

**Symptoms:**
```
✅ GSC API Connection Successful
Accessible Properties: 0
```

**Causes:**
1. Service account not added to any properties
2. Permissions not propagated yet
3. Wrong service account being used

**Solutions:**

**Check 1:** Confirm service account email
```bash
# From secrets/gsc_sa.json
cat secrets/gsc_sa.json | grep client_email
```

Output should match what you added to GSC:
```json
"client_email": "gsc-warehouse-sa@project.iam.gserviceaccount.com"
```

**Check 2:** Wait for propagation
- Permission changes can take 5-10 minutes
- Try again after waiting

**Check 3:** Verify in GSC
1. Open [Google Search Console](https://search.google.com/search-console)
2. Select property
3. Settings → Users and permissions
4. Service account should be listed

---

### Issue: "The caller does not have permission"

**Symptoms:**
```
Error: The caller does not have permission
```

**Cause:** API not enabled in GCP project

**Solution:**
1. Go to [GCP API Library](https://console.cloud.google.com/apis/library)
2. Search: "Search Console API"
3. Click **ENABLE**
4. Wait 2-3 minutes
5. Try again

---

### Issue: "Property URL not recognized"

**Symptoms:**
```
Error: Site 'sc-domain:example.com' not found
```

**Cause:** Wrong URL format for your property type

**Solution:**

**Try different formats:**
```bash
# Domain property (most common)
GSC_PROPERTIES=sc-domain:example.com

# URL prefix with HTTPS
GSC_PROPERTIES=sc-domain:https://example.com

# URL prefix with HTTP
GSC_PROPERTIES=sc-domain:http://example.com

# Subdomain
GSC_PROPERTIES=sc-domain:blog.example.com
```

**Find correct format:**
1. Run test script (see Test 1 above)
2. Note exact URLs listed
3. Use those exact URLs in .env

---

### Issue: "Invalid grant: account not found"

**Symptoms:**
```
Error: invalid_grant: Invalid JWT Signature
```

**Causes:**
1. Wrong service account JSON file
2. Corrupted JSON file
3. Using wrong project's credentials

**Solutions:**

**Check 1:** Validate JSON format
```bash
cat secrets/gsc_sa.json | python -m json.tool
```

If this errors, the JSON is corrupted.

**Check 2:** Verify project ID
```bash
# From JSON file
cat secrets/gsc_sa.json | grep project_id

# Should match your GCP project
```

**Check 3:** Download fresh credentials
1. Go to [GCP Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Select your service account
3. Keys → Add Key → Create new key
4. Choose JSON
5. Replace secrets/gsc_sa.json

---

### Issue: Rate limiting / quota errors

**Symptoms:**
```
Error 429: Rate limit exceeded
Error: Quota exceeded for quota metric
```

**GSC API Limits:**
- **600 requests per minute** per project
- **200 requests per minute** per user
- **50,000 requests per day**

**Solutions:**

**Option 1:** Reduce collection frequency
```bash
# In scheduler/scheduler.py
# Change from hourly to every 3 hours
schedule.every(3).hours.do(collect_gsc_data)
```

**Option 2:** Implement exponential backoff
Already implemented in `ingestors/api/rate_limiter.py`

**Option 3:** Request quota increase
1. Go to [GCP Console - Quotas](https://console.cloud.google.com/iam-admin/quotas)
2. Filter: "Search Console API"
3. Select quota to increase
4. Click "EDIT QUOTAS"
5. Submit request with justification

---

## Property URL Reference

### Common Property Formats

| GSC Display | Property Type | Configuration Format |
|-------------|---------------|---------------------|
| `example.com` | Domain | `sc-domain:example.com` |
| `https://example.com/` | URL Prefix | `sc-domain:https://example.com` |
| `http://example.com/` | URL Prefix | `sc-domain:http://example.com` |
| `blog.example.com` | Domain | `sc-domain:blog.example.com` |
| `https://blog.example.com/` | URL Prefix | `sc-domain:https://blog.example.com` |

### Multiple Properties Configuration

```bash
# .env file
# Format: property1,property2,property3
# NO SPACES between commas!

# ✅ Correct
GSC_PROPERTIES=sc-domain:example.com,sc-domain:blog.example.com

# ❌ Wrong (has spaces)
GSC_PROPERTIES=sc-domain:example.com, sc-domain:blog.example.com
```

---

## Data Collection Schedule

### Manual Collection

```bash
# Last 7 days
python ingestors/api/gsc_api_ingestor.py \
    --date-start $(date -d '7 days ago' +%Y-%m-%d) \
    --date-end $(date +%Y-%m-%d)

# Specific date range
python ingestors/api/gsc_api_ingestor.py \
    --date-start 2024-11-01 \
    --date-end 2024-11-20

# Single property
python ingestors/api/gsc_api_ingestor.py \
    --property sc-domain:example.com \
    --date-start 2024-11-01 \
    --date-end 2024-11-20
```

### Automated Collection

Edit `scheduler/scheduler.py`:

```python
# Daily collection (recommended)
schedule.every().day.at("02:00").do(collect_gsc_data)

# Every 3 hours
schedule.every(3).hours.do(collect_gsc_data)
```

Or use cron:
```cron
# Daily at 2 AM
0 2 * * * cd /opt/gsc-warehouse && python ingestors/api/gsc_api_ingestor.py --auto
```

---

## Security Best Practices

### 1. Credential Security

**Do:**
- ✅ Store `gsc_sa.json` in `secrets/` directory
- ✅ Add `secrets/` to `.gitignore`
- ✅ Set file permissions to 600 (read/write owner only)
- ✅ Use environment variables for file paths

**Don't:**
- ❌ Commit credentials to version control
- ❌ Share credentials via email/chat
- ❌ Use personal Google account credentials
- ❌ Grant "Owner" permission to service accounts

### 2. Permission Levels

**Recommended:**
- **Full:** For data collection and basic property management
- **Restricted:** For read-only data access

**Not Recommended:**
- **Owner:** Unnecessary and risky - allows property deletion

### 3. Key Rotation

Rotate service account keys every 90 days:

```bash
# 1. Create new key in GCP Console
# 2. Test with new key
# 3. Update secrets/gsc_sa.json
# 4. Delete old key from GCP Console
```

### 4. Monitoring

Monitor service account usage:
```sql
-- Check last collection timestamp
SELECT MAX(ingested_at) as last_collection
FROM gsc.fact_gsc_daily;

-- Check for gaps in data
SELECT date
FROM generate_series(
    (SELECT MIN(date) FROM gsc.fact_gsc_daily),
    CURRENT_DATE,
    '1 day'
) AS date
WHERE date NOT IN (SELECT DISTINCT date FROM gsc.fact_gsc_daily)
ORDER BY date DESC;
```

---

## Next Steps

✅ **Completed:** GSC integration

**Continue to:**
- [GA4_INTEGRATION.md](GA4_INTEGRATION.md) - Integrate Google Analytics 4
- [SETUP_GUIDE.md](SETUP_GUIDE.md) - Complete application setup
- [MONITORING_GUIDE.md](MONITORING_GUIDE.md) - Setup monitoring

---

## Quick Reference

### Configuration Checklist

- [ ] Service account created in GCP
- [ ] Search Console API enabled
- [ ] Service account JSON downloaded to `secrets/gsc_sa.json`
- [ ] Service account added to GSC properties (Full permission)
- [ ] Property URLs configured in `.env`
- [ ] Test script confirms access
- [ ] Initial data collection successful
- [ ] Data visible in database

### Important Files

```
secrets/
  └── gsc_sa.json          # Service account credentials

ingestors/api/
  ├── gsc_api_ingestor.py  # Main data collector
  └── rate_limiter.py      # Rate limit handling

.env                       # Configuration
```

### Key Configuration

```bash
# .env
GSC_SERVICE_ACCOUNT_FILE=/secrets/gsc_sa.json
GSC_PROPERTIES=sc-domain:example.com,sc-domain:blog.example.com
```

### Useful Commands

```bash
# Test API access
python test_gsc_access.py

# Collect last 7 days
python ingestors/api/gsc_api_ingestor.py --date-start $(date -d '7 days ago' +%Y-%m-%d)

# Check database
psql $WAREHOUSE_DSN -c "SELECT property, COUNT(*) FROM gsc.fact_gsc_daily GROUP BY property;"
```

---

## Support

**Issues?**
- Check [Troubleshooting](#troubleshooting) section above
- See [GCP_SETUP_GUIDE.md](GCP_SETUP_GUIDE.md) for GCP-specific issues
- Review [docs/TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md) for general issues

**API Documentation:**
- [Search Console API Reference](https://developers.google.com/webmaster-tools/search-console-api-original/v3/searchanalytics/query)
- [Service Account Authentication](https://cloud.google.com/iam/docs/service-accounts)

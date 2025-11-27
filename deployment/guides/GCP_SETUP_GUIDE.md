# Google Cloud Platform Setup Guide

Complete guide for setting up Google Cloud Platform, service accounts, and integrating with Google Search Console and Google Analytics 4.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Create Google Cloud Project](#create-google-cloud-project)
3. [Enable Required APIs](#enable-required-apis)
4. [Create Service Account](#create-service-account)
5. [Configure IAM Roles](#configure-iam-roles)
6. [Download Service Account Key](#download-service-account-key)
7. [Integrate with Google Search Console](#integrate-with-google-search-console)
8. [Integrate with Google Analytics 4](#integrate-with-google-analytics-4)
9. [Verify Setup](#verify-setup)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- **Google Cloud Account** - Sign up at [cloud.google.com](https://cloud.google.com)
- **Google Search Console Access** - Owner or Full access to properties
- **Google Analytics 4 Access** - Administrator access to properties
- **Billing Account** (optional for free tier, required for production)

---

## Create Google Cloud Project

### Step 1: Access Google Cloud Console

1. Navigate to [Google Cloud Console](https://console.cloud.google.com)
2. Sign in with your Google account
3. Accept Terms of Service if prompted

### Step 2: Create New Project

1. Click the **project dropdown** at the top of the page
2. Click **"NEW PROJECT"** button
3. Fill in project details:
   - **Project name:** `gsc-data-warehouse` (or your preferred name)
   - **Organization:** Select if applicable (optional)
   - **Location:** Choose parent organization or leave as "No organization"
4. Click **"CREATE"**
5. Wait for project creation (usually 10-30 seconds)
6. **Note the Project ID** - you'll need this later

**Example Project ID:** `gsc-data-warehouse-123456`

### Step 3: Select Your Project

1. Click the **project dropdown** again
2. Select your newly created project
3. Verify the project name appears in the top navigation bar

---

## Enable Required APIs

You need to enable several Google APIs for GSC and GA4 data access.

### Step 1: Navigate to APIs & Services

1. Click the **hamburger menu** (☰) in the top-left
2. Navigate to **"APIs & Services" → "Library"**
3. Or visit directly: [API Library](https://console.cloud.google.com/apis/library)

### Step 2: Enable Google Search Console API

1. In the API Library search bar, type: **"Search Console API"**
2. Click on **"Google Search Console API"**
3. Click **"ENABLE"** button
4. Wait for confirmation (5-10 seconds)

### Step 3: Enable Google Analytics Data API

1. Return to API Library (click "Library" in left sidebar)
2. Search for: **"Google Analytics Data API"**
3. Click on **"Google Analytics Data API"**
4. Click **"ENABLE"** button
5. Wait for confirmation

### Step 4: Enable Google Analytics Admin API (Optional)

1. Return to API Library
2. Search for: **"Google Analytics Admin API"**
3. Click and enable
4. This is optional but useful for property management

### Step 5: Verify Enabled APIs

1. Navigate to **"APIs & Services" → "Dashboard"**
2. You should see:
   - ✅ Google Search Console API
   - ✅ Google Analytics Data API
   - ✅ Google Analytics Admin API (optional)

---

## Create Service Account

Service accounts allow your application to authenticate with Google APIs.

### Step 1: Navigate to Service Accounts

1. Click **hamburger menu** (☰)
2. Go to **"IAM & Admin" → "Service Accounts"**
3. Or visit: [Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)

### Step 2: Create Service Account

1. Click **"+ CREATE SERVICE ACCOUNT"** at the top
2. Fill in service account details:

**Step 1 - Service account details:**
   - **Service account name:** `gsc-warehouse-sa`
   - **Service account ID:** Auto-generated (e.g., `gsc-warehouse-sa@project-id.iam.gserviceaccount.com`)
   - **Description:** "Service account for GSC Data Warehouse - access to Search Console and Analytics APIs"
3. Click **"CREATE AND CONTINUE"**

**Step 2 - Grant this service account access to project (optional):**
   - **Select a role:** Choose **"Viewer"** (basic read access to project)
   - This is optional for GSC/GA4 access but useful for monitoring
4. Click **"CONTINUE"**

**Step 3 - Grant users access to this service account (optional):**
   - Leave blank unless you need to grant other users permission to manage this service account
5. Click **"DONE"**

### Step 3: Note the Service Account Email

Your service account email will look like:
```
gsc-warehouse-sa@gsc-data-warehouse-123456.iam.gserviceaccount.com
```

**Save this email** - you'll need it for GSC and GA4 integration.

---

## Configure IAM Roles

### Project-Level Roles (Optional)

If you need the service account to access BigQuery or other GCP services:

1. Go to **"IAM & Admin" → "IAM"**
2. Click **"+ GRANT ACCESS"**
3. Add principal: `gsc-warehouse-sa@your-project.iam.gserviceaccount.com`
4. Select roles:
   - **BigQuery Data Viewer** - If storing data in BigQuery
   - **BigQuery Job User** - If running queries
5. Click **"SAVE"**

**Note:** For basic GSC/GA4 data collection, project-level roles are optional. API access is granted at the property level (see integration sections below).

---

## Download Service Account Key

### Step 1: Create JSON Key

1. Navigate to **"IAM & Admin" → "Service Accounts"**
2. Find your service account (`gsc-warehouse-sa`)
3. Click the **three dots (⋮)** in the Actions column
4. Select **"Manage keys"**
5. Click **"ADD KEY" → "Create new key"**
6. Choose key type: **JSON**
7. Click **"CREATE"**
8. The JSON file will download automatically

### Step 2: Secure the Key File

The downloaded file contains sensitive credentials. **Never commit this to version control!**

**File structure:**
```json
{
  "type": "service_account",
  "project_id": "gsc-data-warehouse-123456",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "gsc-warehouse-sa@gsc-data-warehouse-123456.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs/...",
  "universe_domain": "googleapis.com"
}
```

### Step 3: Install in Your Project

1. Rename the downloaded file to `gsc_sa.json`
2. Move it to your project's `secrets/` directory:
   ```bash
   # Linux/Mac
   mv ~/Downloads/gsc-data-warehouse-*.json ./secrets/gsc_sa.json

   # Windows
   move %USERPROFILE%\Downloads\gsc-data-warehouse-*.json secrets\gsc_sa.json
   ```
3. Set appropriate permissions:
   ```bash
   # Linux/Mac
   chmod 600 secrets/gsc_sa.json

   # Windows (via PowerShell)
   icacls secrets\gsc_sa.json /inheritance:r /grant:r "$($env:USERNAME):(R,W)"
   ```

### Step 4: Update .env File

```bash
# .env
GSC_SERVICE_ACCOUNT_FILE=/secrets/gsc_sa.json
```

---

## Integrate with Google Search Console

Grant your service account access to Search Console properties.

### Step 1: Access Google Search Console

1. Navigate to [Google Search Console](https://search.google.com/search-console)
2. Sign in with account that has **Owner** access to your property

### Step 2: Select Property

1. Click the **property dropdown** in the top-left
2. Select the property you want to grant access to
   - Example: `https://example.com`

### Step 3: Add Service Account as User

1. Click **"Settings"** in the left sidebar (gear icon)
2. Scroll to **"Users and permissions"**
3. Click **"ADD USER"**
4. Enter service account email:
   ```
   gsc-warehouse-sa@gsc-data-warehouse-123456.iam.gserviceaccount.com
   ```
5. Select permission level: **"Full"** or **"Restricted"**
   - **Full:** Recommended for data access
   - **Restricted:** Limited to viewing data only
6. Click **"ADD"**

### Step 4: Verify Access

The service account should now appear in the users list with granted permissions.

### Step 5: Get Property URL for Configuration

The property URL format in GSC API:
- **Domain property:** `sc-domain:example.com`
- **URL prefix property:** `sc-domain:https://example.com`

Update your `.env`:
```bash
GSC_PROPERTIES=sc-domain:example.com,sc-domain:docs.example.com
```

### Repeat for Multiple Properties

If you have multiple GSC properties, repeat Steps 2-4 for each property.

---

## Integrate with Google Analytics 4

Grant your service account access to GA4 properties.

### Step 1: Access Google Analytics

1. Navigate to [Google Analytics](https://analytics.google.com)
2. Sign in with account that has **Administrator** access

### Step 2: Navigate to Admin

1. Click **"Admin"** in the bottom-left corner (gear icon)
2. Ensure you're viewing the correct **Account** and **Property**

### Step 3: Add Service Account User

1. In the **"Property"** column, click **"Property Access Management"**
2. Click **"+ ADD USERS"** (top-right)
3. Enter service account email:
   ```
   gsc-warehouse-sa@gsc-data-warehouse-123456.iam.gserviceaccount.com
   ```
4. Select roles:
   - **Viewer:** Read-only access (recommended for data collection)
   - Uncheck **"Notify this user by email"** (service accounts don't need notifications)
5. Click **"ADD"**

### Step 4: Get Property ID

1. In **Admin**, select your property
2. Click **"Property Settings"** in the Property column
3. Copy the **Property ID** (numeric value)
   - Example: `123456789`

Update your `.env`:
```bash
GA4_PROPERTY_ID=123456789
GA4_CREDENTIALS_FILE=/secrets/gsc_sa.json  # Same service account works for both
```

### Step 5: Enable Google Analytics Data API (if not already done)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select your project
3. Navigate to **"APIs & Services" → "Library"**
4. Search for **"Google Analytics Data API"**
5. Click **"ENABLE"** if not already enabled

### Repeat for Multiple Properties

If you have multiple GA4 properties, repeat Steps 2-4 for each property.

---

## Verify Setup

### Test 1: Verify Service Account Exists

```bash
# List service accounts (requires gcloud CLI)
gcloud iam service-accounts list --project=gsc-data-warehouse-123456
```

Expected output:
```
NAME                                       EMAIL
GSC Warehouse SA  gsc-warehouse-sa@gsc-data-warehouse-123456.iam.gserviceaccount.com
```

### Test 2: Verify API Access

```python
# test_gcp_setup.py
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json

# Load credentials
with open('secrets/gsc_sa.json', 'r') as f:
    creds_info = json.load(f)

credentials = service_account.Credentials.from_service_account_info(
    creds_info,
    scopes=['https://www.googleapis.com/auth/webmasters.readonly']
)

# Test GSC API access
service = build('searchconsole', 'v1', credentials=credentials)
sites = service.sites().list().execute()

print("✅ GSC API Access Verified")
print(f"Properties accessible: {len(sites.get('siteEntry', []))}")
for site in sites.get('siteEntry', []):
    print(f"  - {site['siteUrl']}")
```

### Test 3: Run Data Collection

```bash
# Test GSC data ingestion
python ingestors/api/gsc_api_ingestor.py \
    --date-start $(date -d '7 days ago' +%Y-%m-%d) \
    --date-end $(date +%Y-%m-%d)
```

Expected output:
```
✅ Connected to GSC API
✅ Found 2 properties
✅ Ingested 1,234 rows
```

### Test 4: Verify Database

```sql
-- Check ingested data
SELECT
    property,
    COUNT(*) as row_count,
    MIN(date) as earliest_date,
    MAX(date) as latest_date
FROM gsc.fact_gsc_daily
GROUP BY property;
```

---

## Troubleshooting

### Error: "User does not have sufficient permissions"

**Cause:** Service account not added to GSC/GA4 property

**Solution:**
1. Verify service account email is correct
2. Check that service account was added with "Full" or "Viewer" permissions
3. Wait 5-10 minutes for permissions to propagate

### Error: "API not enabled"

**Cause:** Required APIs not enabled in GCP project

**Solution:**
1. Go to [API Library](https://console.cloud.google.com/apis/library)
2. Enable:
   - Google Search Console API
   - Google Analytics Data API
3. Wait 2-3 minutes for propagation

### Error: "Invalid grant: account not found"

**Cause:** Service account JSON key is incorrect or corrupted

**Solution:**
1. Download a new JSON key from GCP Console
2. Replace `secrets/gsc_sa.json`
3. Verify file is valid JSON:
   ```bash
   cat secrets/gsc_sa.json | python -m json.tool
   ```

### Error: "403 Forbidden"

**Cause:** Service account lacks necessary permissions

**Solution:**
1. **For GSC:** Ensure service account has "Full" access in Search Console
2. **For GA4:** Ensure service account has "Viewer" role in Analytics
3. Check that you're using the correct property ID/URL

### Error: "The caller does not have permission"

**Cause:** Project-level IAM permissions missing (if using BigQuery)

**Solution:**
1. Go to **"IAM & Admin" → "IAM"**
2. Grant service account:
   - BigQuery Data Viewer
   - BigQuery Job User

### Service Account Email Not Recognized in GSC

**Cause:** Email format incorrect or typo

**Solution:**
1. Copy email directly from [Service Accounts page](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Verify format: `name@project-id.iam.gserviceaccount.com`
3. Do not add extra spaces or characters

### Multiple Projects - Which One to Use?

**Best Practice:**
- Use **one project** for all GSC/GA4 data collection
- Create separate service accounts if you need to isolate permissions
- Use descriptive project names (e.g., `company-analytics-warehouse`)

---

## Security Best Practices

### 1. Key Rotation

Rotate service account keys every 90 days:

1. Create new key in GCP Console
2. Update `secrets/gsc_sa.json`
3. Test data collection
4. Delete old key from GCP Console

### 2. Principle of Least Privilege

- Grant **Viewer** role in GA4 (not Editor/Administrator)
- Grant **Full** or **Restricted** in GSC (not Owner)
- Only enable APIs you actually use

### 3. Key Storage

**Development:**
- Store in `secrets/` directory (gitignored)
- Use environment variables for paths

**Production:**
- Use **Google Secret Manager**
- Or encrypted volumes
- Never commit keys to version control

**Google Secret Manager Example:**
```bash
# Store secret
gcloud secrets create gsc-sa-key --data-file=secrets/gsc_sa.json

# Grant service account access to secret
gcloud secrets add-iam-policy-binding gsc-sa-key \
    --member="serviceAccount:your-app-sa@project.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### 4. Monitoring

Enable audit logs to monitor service account usage:

1. Go to **"IAM & Admin" → "Audit Logs"**
2. Enable **"Admin Read"**, **"Data Read"**, **"Data Write"**
3. Review logs regularly for suspicious activity

---

## Next Steps

After completing GCP setup:

1. ✅ **Complete** - GCP project created
2. ✅ **Complete** - APIs enabled
3. ✅ **Complete** - Service account created and configured
4. ✅ **Complete** - GSC and GA4 integration

**Continue to:**
- [SETUP_GUIDE.md](SETUP_GUIDE.md) - Complete application setup
- [PRODUCTION_GUIDE.md](PRODUCTION_GUIDE.md) - Production deployment
- [MONITORING_GUIDE.md](MONITORING_GUIDE.md) - Setup monitoring

---

## Quick Reference

### Important URLs

- **GCP Console:** https://console.cloud.google.com
- **API Library:** https://console.cloud.google.com/apis/library
- **Service Accounts:** https://console.cloud.google.com/iam-admin/serviceaccounts
- **GSC:** https://search.google.com/search-console
- **GA4:** https://analytics.google.com

### Required Scopes

**Google Search Console:**
```
https://www.googleapis.com/auth/webmasters.readonly
```

**Google Analytics 4:**
```
https://www.googleapis.com/auth/analytics.readonly
```

### Configuration Summary

```bash
# .env
GSC_SERVICE_ACCOUNT_FILE=/secrets/gsc_sa.json
GSC_PROPERTIES=sc-domain:example.com
GA4_PROPERTY_ID=123456789
GA4_CREDENTIALS_FILE=/secrets/gsc_sa.json
```

---

## Additional Resources

- [Google Cloud IAM Documentation](https://cloud.google.com/iam/docs)
- [Search Console API Documentation](https://developers.google.com/webmaster-tools)
- [Google Analytics Data API Documentation](https://developers.google.com/analytics/devguides/reporting/data/v1)
- [Service Account Best Practices](https://cloud.google.com/iam/docs/best-practices-service-accounts)

# Secrets Setup Guide

**Credential management for GSC Data Warehouse**

⚠️ **SECURITY WARNING**: Never commit secret files to version control! The `.gitignore` file is configured to exclude this directory.

---

## Required Secrets Files

### 1. Google Search Console Service Account

**File:** `gsc_sa.json`

**Purpose:** Credentials for accessing Google Search Console API and BigQuery

**How to obtain:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable APIs:
   - Google Search Console API
   - BigQuery API (optional)
4. Create a Service Account:
   - Navigate to IAM & Admin > Service Accounts
   - Click "Create Service Account"
   - Grant permissions:
     - **Search Console API**: Access to your GSC properties
     - **BigQuery Data Viewer** (if using BigQuery)
     - **BigQuery Job User** (if using BigQuery)
5. Create and download JSON key file
6. Place in `secrets/gsc_sa.json`

**Template available:** `secrets/gsc_sa.json.template` (example structure)

---

### 2. GA4 Credentials (Optional)

**File:** `ga4_credentials.json`

**Purpose:** Google Analytics 4 API access for unified analytics

**How to obtain:**
1. Follow similar steps as GSC service account
2. Enable Google Analytics Data API
3. Grant appropriate permissions
4. Download JSON key and save as `secrets/ga4_credentials.json`

---

## Docker Secrets Configuration

### Docker Compose Secret Declaration

Secrets are mounted into containers as read-only files:

```yaml
secrets:
  gsc_sa:
    file: ./secrets/gsc_sa.json
  ga4_creds:
    file: ./secrets/ga4_credentials.json
```

### Container Access

Inside containers, secrets are available at:
- `/run/secrets/gsc_sa`
- `/run/secrets/ga4_creds`

These paths are configured in `.env` file:
```bash
GSC_SA_PATH=/run/secrets/gsc_sa
GA4_CREDENTIALS_PATH=/run/secrets/ga4_creds
```

---

## Setup Instructions

### Windows

1. Create `secrets` folder in project root (if not exists)
   ```cmd
   mkdir secrets
   ```

2. Copy your Google Cloud service account JSON files:
   ```cmd
   copy path\to\your\service-account.json secrets\gsc_sa.json
   ```

3. Verify file exists:
   ```cmd
   dir secrets\gsc_sa.json
   ```

### Linux/MacOS

1. Create `secrets` folder:
   ```bash
   mkdir -p secrets
   ```

2. Copy credentials:
   ```bash
   cp /path/to/your/service-account.json secrets/gsc_sa.json
   ```

3. Set proper permissions (restrict access):
   ```bash
   chmod 600 secrets/gsc_sa.json
   ```

---

## Verification

Check that secrets are properly configured:

```bash
# Verify file exists
ls -la secrets/

# Test with Docker Compose (won't start if secrets missing)
docker-compose config

# Verify container can access secrets
docker-compose run --rm api_ingestor ls -la /run/secrets/
```

---

## Security Best Practices

1. **Never commit secrets to git**
   - `.gitignore` already excludes `secrets/` directory
   - Double-check with: `git status`

2. **Rotate credentials regularly**
   - Update service account keys every 90 days
   - Revoke old keys in Google Cloud Console

3. **Limit permissions**
   - Grant minimal required permissions
   - Use separate service accounts for different environments

4. **Encrypt at rest**
   - Consider using encrypted volumes in production
   - Use cloud provider secret management (AWS Secrets Manager, GCP Secret Manager)

5. **Audit access**
   - Review service account usage in Google Cloud Console
   - Monitor for unusual API activity

---

## Troubleshooting

### Error: "Permission denied" reading secrets

**Solution:** Check file permissions
```bash
chmod 600 secrets/gsc_sa.json
```

### Error: "File not found" in Docker container

**Cause:** Secret not properly mounted

**Solution:** Verify Docker Compose configuration:
```bash
docker-compose config | grep -A 5 secrets
```

### Error: "Invalid JSON" or "Authentication failed"

**Cause:** Malformed or incorrect service account file

**Solution:**
1. Validate JSON syntax: `cat secrets/gsc_sa.json | python -m json.tool`
2. Re-download from Google Cloud Console
3. Verify service account has correct permissions

---

## Related Documentation

- **[Deployment Setup Guide](../deployment/guides/SETUP_GUIDE.md)** - Initial deployment
- **[Main README](../README.md)** - Project overview
- **[TROUBLESHOOTING](../docs/TROUBLESHOOTING.md)** - Common issues

---

**Last Updated**: 2025-11-21

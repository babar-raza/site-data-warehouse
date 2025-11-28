# PageSpeed Insights API Setup Guide

## Overview

Core Web Vitals monitoring requires a Google PageSpeed Insights API key. Without an API key, the service has strict rate limits (0-25 queries per day).

## Obtaining a PageSpeed Insights API Key

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Enter project name (e.g., "GSC-Warehouse-Monitoring")
4. Click **Create**

### Step 2: Enable PageSpeed Insights API

1. In your project, go to **APIs & Services** → **Library**
2. Search for "PageSpeed Insights API"
3. Click on **PageSpeed Insights API**
4. Click **Enable**

### Step 3: Create API Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **+ CREATE CREDENTIALS** → **API key**
3. Copy the generated API key
4. (Recommended) Click **Restrict Key**:
   - **Application restrictions**: HTTP referrers or IP addresses
   - **API restrictions**: Restrict to "PageSpeed Insights API"
5. Click **Save**

### Step 4: Add API Key to Environment

Add the API key to your `.env` file:

```bash
PAGESPEED_API_KEY=YOUR_API_KEY_HERE
```

### Step 5: Verify API Access

Test the API:

```bash
curl "https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=https://www.google.com&key=YOUR_API_KEY&strategy=mobile"
```

Expected response: JSON with lighthouse results

## API Quotas

### Free Tier
- **Default Quota**: 25,000 queries per day
- **Cost**: Free

### Paid Tier
If you need more queries:
1. Enable billing in Google Cloud Console
2. Go to **APIs & Services** → **PageSpeed Insights API** → **Quotas**
3. Request quota increase

**Pricing**:
- First 25,000 queries/day: Free
- Additional queries: $5 per 1,000 queries (check current pricing)

## Rate Limiting Best Practices

The CWV collection script includes built-in rate limiting:
- 2-second delay between API calls
- Error handling for 429 (rate limit) responses
- Graceful degradation when API unavailable

### Recommended Collection Frequency

- **Development**: Once per day (minimal quota usage)
- **Production**: 2-4 times per day (morning, afternoon, evening, night)
- **High-frequency**: Hourly (requires monitoring quota usage)

### Calculating Quota Requirements

**Formula**: `pages × strategies × collections_per_day`

**Examples**:
- 10 pages × 2 strategies (mobile+desktop) × 4 collections/day = **80 queries/day**
- 50 pages × 2 strategies × 4 collections/day = **400 queries/day**
- 100 pages × 1 strategy × 1 collection/day = **100 queries/day**

## Monitoring Quota Usage

### In Google Cloud Console

1. Go to **APIs & Services** → **Dashboard**
2. Click **PageSpeed Insights API**
3. View **Traffic** and **Quotas** tabs

### Alert on Quota Exhaustion

Set up alerts:
1. Go to **Monitoring** → **Alerting**
2. Create alert policy for "API Quota" metric
3. Set threshold (e.g., 80% of daily quota)
4. Configure notification channel (email, Slack, etc.)

## Troubleshooting

### Error: "Quota exceeded"

**HTTP 429**: Daily quota exhausted

**Solutions**:
1. Wait until quota resets (midnight Pacific Time)
2. Request quota increase
3. Reduce collection frequency
4. Prioritize critical pages only

### Error: "API key not valid"

**HTTP 400**: Invalid or restricted API key

**Solutions**:
1. Verify API key is correct in `.env`
2. Check API restrictions (allow all or specific IPs)
3. Confirm PageSpeed Insights API is enabled
4. Regenerate API key if necessary

### Error: "The caller does not have permission"

**HTTP 403**: Billing not enabled or API not enabled

**Solutions**:
1. Enable PageSpeed Insights API in project
2. Enable billing (if needed for higher quota)
3. Check project permissions

## Security Best Practices

### Protect Your API Key

1. **Never commit to Git**: Add `.env` to `.gitignore`
2. **Use environment variables**: Never hardcode in source code
3. **Restrict key**: Apply application and API restrictions
4. **Rotate regularly**: Generate new key every 6-12 months
5. **Monitor usage**: Set up alerts for unexpected spikes

### Restrict API Key

**Recommended restrictions**:
```
Application restrictions: IP addresses
  - Add your server's IP address
  - Add Docker host IP if running in containers

API restrictions: Restrict key to specific APIs
  - PageSpeed Insights API only
```

## Alternative: Using PSI Without API Key

The script works without an API key but has severe limitations:

**Limitations**:
- 0-25 queries per day (no guaranteed quota)
- Higher chance of rate limiting
- No SLA or support
- Not recommended for production

**When to use**:
- Initial testing only
- Personal projects with 1-2 pages
- Proof of concept

## Integration with Scheduler

Once API key is configured, add CWV collection to scheduler ([`scheduler/scheduler.py`](../scheduler/scheduler.py)):

```python
# Add to scheduler jobs
scheduler.add_job(
    func=run_cwv_collection,
    trigger='cron',
    hour='*/6',  # Every 6 hours
    id='cwv_collection',
    name='Core Web Vitals Collection'
)
```

See [Phase 4 documentation](../reports/phase-4.md) for automated scheduling setup.

## References

- [PageSpeed Insights API Documentation](https://developers.google.com/speed/docs/insights/v5/get-started)
- [Google Cloud Console](https://console.cloud.google.com/)
- [API Key Best Practices](https://cloud.google.com/docs/authentication/api-keys)
- [Quota Management](https://cloud.google.com/apis/docs/capping-api-usage)

---

**Document Updated**: 2025-11-24
**Related**: [Phase 3 Report](../reports/phase-3.md), [Quick Start Guide](./QUICKSTART.md)

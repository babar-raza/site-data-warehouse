# Enterprise Rate Limiting Guide

## Overview

The GSC Data Warehouse implements professional-grade rate limiting to ensure compliance with Google Search Console API quotas while maximizing data throughput. The rate limiter uses a token bucket algorithm with exponential backoff and comprehensive monitoring.

## Architecture

### Token Bucket Algorithm

The rate limiter implements multiple token buckets:

1. **Minute Bucket**: 30 requests per minute (configurable)
2. **Burst Bucket**: 5 requests in quick succession
3. **Daily Quota**: 2000 requests per day (GSC API limit)

Each bucket refills automatically at configured rates:
- Minute bucket: Refills continuously at rate/60 tokens per second
- Burst bucket: Refills over 10 seconds
- Daily quota: Resets at midnight UTC

### Exponential Backoff

When rate limits are hit, the system applies exponential backoff:

```
backoff_time = min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF) + jitter
```

- Base backoff: 2 seconds
- Max backoff: 300 seconds (5 minutes)
- Jitter: Random 0-10% added to prevent thundering herd

## Configuration

### Environment Variables

```env
# Rate Limiting Configuration
REQUESTS_PER_MINUTE=30      # Per-minute rate limit
REQUESTS_PER_DAY=2000       # Daily quota (GSC API limit)
BURST_SIZE=5                # Burst capacity
API_COOLDOWN_SEC=2          # Minimum time between requests
BASE_BACKOFF=2.0            # Initial backoff duration
MAX_BACKOFF=300.0           # Maximum backoff duration
BACKOFF_JITTER=true         # Enable jitter
GSC_API_MAX_RETRIES=5       # Maximum retry attempts
```

### Tuning Guidelines

#### Conservative (Low Risk)
```env
REQUESTS_PER_MINUTE=20
BURST_SIZE=3
API_COOLDOWN_SEC=3
```
- Best for: Multiple properties, shared quotas
- Throughput: ~20 req/min sustained
- Risk: Very low

#### Balanced (Recommended)
```env
REQUESTS_PER_MINUTE=30
BURST_SIZE=5
API_COOLDOWN_SEC=2
```
- Best for: Standard deployments
- Throughput: ~30 req/min sustained
- Risk: Low

#### Aggressive (High Throughput)
```env
REQUESTS_PER_MINUTE=40
BURST_SIZE=8
API_COOLDOWN_SEC=1
```
- Best for: Single property, dedicated quota
- Throughput: ~40 req/min sustained  
- Risk: Medium (may hit rate limits more often)

## Monitoring

### Rate Limiter Metrics

The rate limiter exposes comprehensive metrics:

```python
metrics = {
    'total_requests': int,          # Total API requests made
    'total_throttled': int,         # Requests delayed by rate limiter
    'total_retries': int,           # Number of retries performed
    'daily_requests': int,          # Requests today
    'daily_quota_remaining': int,   # Remaining daily quota
    'consecutive_failures': int,    # Current failure streak
    'in_backoff': bool,             # Currently in backoff period
    'properties_tracked': int,      # Number of properties tracked
    'throttle_rate': float          # Percentage of throttled requests
}
```

### Prometheus Metrics

```promql
# Total requests
gsc_api_requests_total

# Throttled requests
gsc_api_throttled_total

# Retry attempts
gsc_api_retries_total

# Daily quota remaining
gsc_api_daily_quota_remaining

# Throttle rate
gsc_api_throttle_rate

# Backoff status
gsc_api_in_backoff
```

### Log Monitoring

```bash
# Watch rate limiter activity
docker compose logs -f api_ingestor | grep "Rate"

# Examples of log messages:
# "Rate limiter: waiting 1.23s before request"
# "Rate limit hit (429), attempt 1"
# "Backing off for 4.52s (attempt 2)"
# "Rate limiter metrics: {...}"
```

## Best Practices

### 1. Start Conservative

Begin with conservative settings and gradually increase:

```bash
# Week 1: Conservative
REQUESTS_PER_MINUTE=20

# Week 2: Increase if no issues
REQUESTS_PER_MINUTE=25

# Week 3: Balanced
REQUESTS_PER_MINUTE=30
```

### 2. Monitor Throttle Rate

Aim for throttle rate < 5%:

```bash
# Check metrics
curl http://localhost:9090/metrics | grep throttle_rate

# If throttle_rate > 0.05, consider reducing REQUESTS_PER_MINUTE
```

### 3. Use Per-Property Tracking

The rate limiter automatically tracks each property independently:

```python
# Properties are rate-limited separately
property1 = "https://example.com/"
property2 = "https://blog.example.com/"

# Each gets independent token buckets
```

### 4. Respect Daily Quotas

Monitor daily quota usage:

```bash
# Check remaining quota
docker compose logs api_ingestor | grep "quota_remaining"

# Plan ingestion windows
# - Historical data: Off-peak hours
# - Daily updates: Early morning UTC
```

### 5. Enable Jitter

Always use jitter in production:

```env
BACKOFF_JITTER=true  # Prevents thundering herd
```

## Troubleshooting

### Issue: Frequent 429 Errors

**Symptoms:**
```
Rate limit hit (429), attempt 1
Backing off for 2.0s
```

**Solutions:**
1. Reduce `REQUESTS_PER_MINUTE`
2. Increase `API_COOLDOWN_SEC`
3. Reduce `BURST_SIZE`
4. Check if multiple services are sharing the quota

### Issue: Daily Quota Exceeded

**Symptoms:**
```
Daily quota exceeded: 2000/2000
```

**Solutions:**
1. Reduce `INGEST_DAYS` for initial load
2. Schedule ingestion across multiple days
3. Process one property at a time
4. Request quota increase from Google

### Issue: High Throttle Rate

**Symptoms:**
```
throttle_rate: 0.15  (15% throttled)
```

**Solutions:**
1. Increase `REQUESTS_PER_MINUTE`
2. Reduce `BURST_SIZE`
3. Check concurrent processes
4. Review API usage patterns

### Issue: Backoff Not Working

**Symptoms:**
```
Max retries exceeded for rate limiting
```

**Solutions:**
1. Increase `GSC_API_MAX_RETRIES`
2. Increase `MAX_BACKOFF`
3. Enable `BACKOFF_JITTER`
4. Check GSC API status

## Advanced Configuration

### Custom Rate Limit Profiles

Create custom profiles for different scenarios:

#### High-Volume Property
```env
REQUESTS_PER_MINUTE=35
BURST_SIZE=7
API_COOLDOWN_SEC=1.5
BASE_BACKOFF=1.5
```

#### Shared Quota Environment
```env
REQUESTS_PER_MINUTE=15
BURST_SIZE=2
API_COOLDOWN_SEC=4
BASE_BACKOFF=3.0
```

#### Batch Processing
```env
REQUESTS_PER_MINUTE=25
BURST_SIZE=10
API_COOLDOWN_SEC=2
BASE_BACKOFF=2.0
```

### Distributed Rate Limiting

For multi-instance deployments, implement distributed coordination:

1. **Redis-based token bucket** (future enhancement)
2. **Database-backed quota tracking**
3. **Instance-specific quotas**

## Testing

### Unit Tests

```bash
# Test rate limiter
pytest tests/test_rate_limiter.py -v

# Test with specific config
REQUESTS_PER_MINUTE=50 pytest tests/test_rate_limiter.py
```

### Load Tests

```bash
# Simulate high load
python tests/load_test_rate_limiter.py \
  --requests=100 \
  --concurrency=5 \
  --duration=60
```

### Integration Tests

```bash
# Test full ingestion with rate limiting
docker compose --profile ingestion run --rm \
  -e REQUESTS_PER_MINUTE=10 \
  api_ingestor
```

## Performance Impact

### Throughput Analysis

| Config | Req/Min | Daily Max | 16mo Data Time |
|--------|---------|-----------|----------------|
| Conservative | 20 | 1440 | ~25 hours |
| Balanced | 30 | 2000 | ~18 hours |
| Aggressive | 40 | 2000 | ~14 hours |

### Resource Usage

- CPU: < 5% per instance
- Memory: ~50MB for rate limiter state
- Network: Minimal (state tracking only)
- Disk: None (in-memory only)

## API Quota Guidelines

### Google Search Console API Limits

**Official Limits:**
- 600 queries per minute per project
- 2000 queries per day per property (soft limit)
- 25,000 rows per query

**Recommended Usage:**
- Stay well below limits (50-75% utilization)
- Implement backoff for 429 errors
- Use pagination for large datasets
- Cache when possible

### Best Practices

1. **Stagger Property Updates**: Don't update all properties simultaneously
2. **Use Incremental Windows**: Fetch 1-7 days at a time
3. **Schedule Off-Peak**: Run heavy loads during low-traffic hours
4. **Monitor Quotas**: Track daily usage patterns
5. **Request Increases**: Contact Google for production quotas

## References

- [Token Bucket Algorithm](https://en.wikipedia.org/wiki/Token_bucket)
- [Exponential Backoff](https://en.wikipedia.org/wiki/Exponential_backoff)
- [Google Search Console API](https://developers.google.com/webmaster-tools/search-console-api-original)
- [Rate Limiting Patterns](https://cloud.google.com/architecture/rate-limiting-strategies)

## Support

For rate limiting issues:

1. Check logs: `docker compose logs -f api_ingestor`
2. Review metrics: `curl http://localhost:9090/metrics`
3. Adjust configuration based on symptoms
4. Test changes in development first
5. Monitor for 24 hours after changes

---

*Last Updated: November 2025*

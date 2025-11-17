# API Reference

Complete reference for all APIs provided by the GSC Data Warehouse.

## Table of Contents

- [MCP Server API](#mcp-server-api)
- [Insights REST API](#insights-rest-api)
- [Rate Limiter API](#rate-limiter-api)
- [Database Schema](#database-schema)

---

## MCP Server API

**Base URL**: `http://localhost:8000`

**Protocol**: Model Context Protocol 2025-01-18

### Health Check

#### GET /health

Check server health status.

**Response**:
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "2.0.0"
}
```

### List Tools

#### GET /tools

Return a deterministic list of available MCP tools. Each entry
includes the tool name, a short description, and its input
parameters. The parameter definitions are derived from the
underlying request models.

**Response**:

```json
{
  "tools": [
    {
      "name": "get_page_health",
      "description": "Get page performance and health metrics",
      "parameters": {
        "scope": {
          "type": "object",
          "properties": {
            "property": {"type": "string"},
            "directory": {"type": "string"},
            "min_impressions": {"type": "integer"}
          }
        },
        "window_days": {"type": "integer"},
        "limit": {"type": "integer"},
        "sort_by": {"type": "string"}
      }
    },
    {
      "name": "get_query_trends",
      "description": "Get query performance trends (winners/losers)",
      "parameters": {
        "scope": {
          "type": "object",
          "properties": {
            "property": {"type": "string"},
            "min_impressions": {"type": "integer"}
          }
        },
        "window_days": {"type": "integer"},
        "limit": {"type": "integer"},
        "category_filter": {"type": "string"}
      }
    },
    {
      "name": "find_cannibalization",
      "description": "Detect keyword cannibalization issues",
      "parameters": {
        "scope": {
          "type": "object",
          "properties": {
            "property": {"type": "string"}
          }
        },
        "window_days": {"type": "integer"},
        "min_severity": {"type": "string"},
        "limit": {"type": "integer"}
      }
    },
    {
      "name": "suggest_actions",
      "description": "Generate actionable SEO recommendations",
      "parameters": {
        "scope": {
          "type": "object",
          "properties": {
            "property": {"type": "string"}
          }
        },
        "window_days": {"type": "integer"},
        "focus_area": {"type": "string"},
        "limit": {"type": "integer"}
      }
    }
  ],
  "mcp_version": "2025-01-18"
}
```

### Tool Invocation

#### POST /call-tool

Invoke an MCP tool in a unified manner. The body must specify
the `tool` name and an `arguments` object containing the
parameters for that tool. Arguments are flattened and then
mapped onto the tool’s request model. Unknown tools or
invalid arguments return structured errors.

**Request**:

```json
{
  "tool": "get_page_health",
  "arguments": {
    "property": "https://example.com/",
    "window_days": 28,
    "limit": 10,
    "sort_by": "clicks"
  }
}
```

**Response**:

```json
{
  "result": [
    {
      "property": "https://example.com/",
      "url": "https://example.com/page1.html",
      "total_clicks": 150,
      "total_impressions": 5000,
      "ctr_percentage": 3.0,
      "avg_position": 5.2,
      "health_score": 80,
      "trend_status": "IMPROVING"
    }
  ],
  "metadata": {
    "execution_time_ms": 150,
    "rows_returned": 1
  }
}
```

On success the server returns the tool’s result data along with
execution metadata. The `rows_returned` value corresponds to
the number of items returned for list‑like responses. Tools
that return categories or nested objects will still report the
row count based on their primary data array.

### Available Tools

#### 1. get_page_health

Get page performance and health metrics.

**Parameters**:
- `property` (string, required): GSC property URL
- `window_days` (integer, optional): Analysis window in days (default: 28)
- `limit` (integer, optional): Maximum results (default: 10)

**Returns**: Array of page health objects

```json
[
  {
    "page": "https://example.com/page1",
    "clicks_current": 100,
    "clicks_previous": 80,
    "clicks_change_pct": 25.0,
    "impressions_current": 1000,
    "avg_ctr": 0.1,
    "avg_position": 5.5,
    "health_status": "IMPROVING"
  }
]
```

#### 2. get_query_trends

Get query performance trends (winners/losers).

**Parameters**:
- `property` (string, required): GSC property URL
- `category` (string, optional): Filter by WINNER or LOSER
- `limit` (integer, optional): Maximum results (default: 20)

**Returns**: Array of query trend objects

```json
[
  {
    "query": "example search term",
    "clicks_delta": 50,
    "impressions_delta": 500,
    "category": "WINNER",
    "current_position": 3.2,
    "previous_position": 5.8
  }
]
```

#### 3. find_cannibalization

Detect keyword cannibalization issues.

**Parameters**:
- `property` (string, required): GSC property URL
- `min_severity` (string, optional): Minimum severity (LOW/MEDIUM/HIGH)
- `limit` (integer, optional): Maximum results (default: 10)

**Returns**: Array of cannibalization issues

```json
[
  {
    "query": "example keyword",
    "pages": [
      "https://example.com/page1",
      "https://example.com/page2"
    ],
    "total_clicks": 150,
    "severity": "HIGH",
    "recommendation": "Consolidate content..."
  }
]
```

#### 4. suggest_actions

Get AI-powered SEO action recommendations.

**Parameters**:
- `property` (string, required): GSC property URL
- `focus_area` (string, optional): technical, content, or links
- `limit` (integer, optional): Maximum actions (default: 5)

**Returns**: Array of action recommendations

```json
[
  {
    "priority": "HIGH",
    "area": "content",
    "action": "Improve CTR for...",
    "pages_affected": 5,
    "estimated_impact": "15-20% traffic increase"
  }
]
```

---

## Insights REST API

**Base URL**: `http://localhost:8002`

**Format**: JSON

### Health Check

#### GET /api/health

Check API health status.

**Response**:
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0"
}
```

### Page Health

#### GET /api/page-health

Get page health metrics from analytical view.

**Query Parameters**:
- `property` (string, optional): Filter by property
- `limit` (integer, optional): Maximum results
- `offset` (integer, optional): Pagination offset

**Response**:
```json
{
  "data": [
    {
      "property": "https://example.com/",
      "page": "https://example.com/page1",
      "clicks_current": 100,
      "clicks_previous": 80,
      "clicks_change_pct": 25.0,
      "impressions_current": 1000,
      "avg_ctr": 0.1,
      "avg_position": 5.5,
      "health_status": "IMPROVING"
    }
  ],
  "total": 150,
  "limit": 10,
  "offset": 0
}
```

### Query Trends

#### GET /api/query-trends

Get query trend analysis.

**Query Parameters**:
- `property` (string, optional): Filter by property
- `category` (string, optional): WINNER or LOSER
- `limit` (integer, optional): Maximum results
- `offset` (integer, optional): Pagination offset

**Response**:
```json
{
  "data": [
    {
      "property": "https://example.com/",
      "query": "example term",
      "clicks_delta": 50,
      "impressions_delta": 500,
      "category": "WINNER"
    }
  ],
  "total": 75,
  "limit": 20,
  "offset": 0
}
```

### Directory Trends

#### GET /api/directory-trends

Get directory-level aggregations.

**Query Parameters**:
- `property` (string, optional): Filter by property
- `min_clicks` (integer, optional): Minimum clicks threshold
- `limit` (integer, optional): Maximum results

**Response**:
```json
{
  "data": [
    {
      "property": "https://example.com/",
      "directory": "/blog/",
      "total_clicks": 500,
      "total_impressions": 5000,
      "avg_ctr": 0.1,
      "avg_position": 12.3,
      "unique_pages": 25
    }
  ]
}
```

### Brand/Non-Brand Split

#### GET /api/brand-nonbrand

Get brand vs non-brand query breakdown.

**Query Parameters**:
- `property` (string, optional): Filter by property

**Response**:
```json
{
  "data": [
    {
      "property": "https://example.com/",
      "query_type": "brand",
      "total_clicks": 1000,
      "total_impressions": 5000,
      "avg_ctr": 0.2,
      "query_count": 50
    },
    {
      "property": "https://example.com/",
      "query_type": "non_brand",
      "total_clicks": 500,
      "total_impressions": 10000,
      "avg_ctr": 0.05,
      "query_count": 200
    }
  ]
}
```

---

## Rate Limiter API

**Module**: `ingestors/api/rate_limiter.py`

### RateLimitConfig

Configuration dataclass for rate limiter.

```python
from rate_limiter import RateLimitConfig

config = RateLimitConfig(
    requests_per_minute=30,
    requests_per_day=2000,
    burst_size=5,
    cooldown_seconds=2.0,
    max_retries=5,
    base_backoff=2.0,
    max_backoff=300.0,
    jitter=True
)
```

**Attributes**:
- `requests_per_minute` (int): Per-minute rate limit
- `requests_per_day` (int): Daily quota
- `burst_size` (int): Burst capacity
- `cooldown_seconds` (float): Minimum time between requests
- `max_retries` (int): Maximum retry attempts
- `base_backoff` (float): Initial backoff duration
- `max_backoff` (float): Maximum backoff duration
- `jitter` (bool): Enable backoff randomization

### EnterprisRateLimiter

Main rate limiter class.

#### Constructor

```python
from rate_limiter import EnterprisRateLimiter, RateLimitConfig

config = RateLimitConfig(requests_per_minute=30)
limiter = EnterprisRateLimiter(config)
```

#### acquire(property_url)

Acquire permission to make a request.

```python
wait_time = limiter.acquire("https://example.com/")
if wait_time > 0:
    time.sleep(wait_time)
# Make request
```

**Returns**: Float - seconds to wait before request (0.0 if immediate)

#### record_success()

Record successful request.

```python
# After successful API call
limiter.record_success()
```

#### record_failure(is_rate_limit)

Record failed request and apply backoff.

```python
# After 429 rate limit error
limiter.record_failure(is_rate_limit=True)

# After other error
limiter.record_failure(is_rate_limit=False)
```

**Parameters**:
- `is_rate_limit` (bool): Whether failure was due to rate limiting

#### should_retry()

Check if should retry after failure.

```python
if limiter.should_retry():
    # Retry request
else:
    # Max retries exceeded
```

**Returns**: Bool - whether retry should be attempted

#### get_backoff_time()

Calculate exponential backoff time.

```python
backoff = limiter.get_backoff_time()
time.sleep(backoff)
```

**Returns**: Float - backoff duration in seconds

#### get_metrics()

Get rate limiter metrics.

```python
metrics = limiter.get_metrics()
print(f"Total requests: {metrics['total_requests']}")
print(f"Throttle rate: {metrics['throttle_rate']:.2%}")
```

**Returns**: Dict with metrics:
- `total_requests`: Total API requests
- `total_throttled`: Throttled requests
- `total_retries`: Retry attempts
- `daily_requests`: Requests today
- `daily_quota_remaining`: Remaining quota
- `consecutive_failures`: Current failure streak
- `in_backoff`: Currently backing off
- `properties_tracked`: Number of properties
- `throttle_rate`: Throttle percentage

---

## Database Schema

### Tables

#### fact_gsc_daily

Main fact table for daily GSC data.

**Columns**:
- `property` VARCHAR(500)
- `date` DATE
- `page` VARCHAR(2000)
- `query` VARCHAR(2000)
- `country` VARCHAR(3)
- `device` VARCHAR(20)
- `clicks` INTEGER
- `impressions` INTEGER
- `ctr` NUMERIC(10,8)
- `position` NUMERIC(10,2)
- `created_at` TIMESTAMP
- `updated_at` TIMESTAMP

**Primary Key**: `(property, date, page, query, country, device)`

**Indexes**:
- `idx_fact_property_date`
- `idx_fact_page`
- `idx_fact_query`
- `idx_fact_date`
- `idx_fact_clicks`
- `idx_fact_impressions`
- `idx_fact_position`

#### dim_property

Property dimension table.

**Columns**:
- `property_url` VARCHAR(500) PRIMARY KEY
- `display_name` VARCHAR(500)
- `api_only` BOOLEAN DEFAULT true
- `has_bulk_export` BOOLEAN DEFAULT false
- `created_at` TIMESTAMP
- `updated_at` TIMESTAMP

#### ingest_watermarks

Ingestion watermark tracking.

**Columns**:
- `property` VARCHAR(500)
- `source_type` VARCHAR(20)
- `last_date` DATE
- `rows_processed` INTEGER
- `last_run_at` TIMESTAMP
- `last_run_status` VARCHAR(50)
- `created_at` TIMESTAMP
- `updated_at` TIMESTAMP

**Primary Key**: `(property, source_type)`

### Views

#### vw_page_health_28d

Page performance and health analysis.

**Columns**:
- `property`
- `page`
- `clicks_current`
- `clicks_previous`
- `clicks_change_pct`
- `impressions_current`
- `impressions_previous`
- `avg_ctr`
- `avg_position`
- `health_status` (IMPROVING/DECLINING/STABLE)

#### vw_query_winners_losers_28d_vs_prev

Query trend analysis.

**Columns**:
- `property`
- `query`
- `clicks_delta`
- `impressions_delta`
- `category` (WINNER/LOSER)
- `current_avg_position`
- `previous_avg_position`

#### vw_directory_trends

Directory-level aggregations.

**Columns**:
- `property`
- `directory`
- `total_clicks`
- `total_impressions`
- `avg_ctr`
- `avg_position`
- `unique_pages`

#### vw_brand_nonbrand_split

Brand vs non-brand query split.

**Columns**:
- `property`
- `query_type` (brand/non_brand)
- `total_clicks`
- `total_impressions`
- `avg_ctr`
- `avg_position`
- `query_count`

---

## Error Codes

### MCP Server Errors

| Code | Description |
|------|-------------|
| 400 | Invalid tool or parameters |
| 404 | Tool not found |
| 500 | Internal server error |
| 503 | Database unavailable |

### Insights API Errors

| Code | Description |
|------|-------------|
| 400 | Invalid query parameters |
| 404 | Endpoint not found |
| 500 | Internal server error |
| 503 | Database unavailable |

### Rate Limiter Errors

| Situation | Behavior |
|-----------|----------|
| Rate limit (429) | Exponential backoff and retry |
| Server error (500/503) | Exponential backoff and retry |
| Quota exceeded | Wait until next day |
| Max retries | Raise exception |

---

## Authentication

### Service Account (GSC API)

All API calls use service account authentication:

```json
{
  "type": "service_account",
  "project_id": "your-project",
  "private_key_id": "...",
  "private_key": "...",
  "client_email": "...",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token"
}
```

Place in `secrets/gsc_sa.json`

### Database Credentials

Database password stored in Docker secret:

```
secrets/db_password.txt
```

---

## Rate Limits

### Google Search Console API

**Official Limits**:
- 600 queries per minute per project
- ~2000 queries per day per property
- 25,000 rows per query

**Recommended Settings**:
- 30 requests/minute (conservative)
- 2000 requests/day (matches quota)
- 5 burst capacity

### MCP Server

No rate limiting (internal service)

### Insights API

No rate limiting (internal service)

---

## Examples

### Python MCP Client

```python
import requests

response = requests.post(
    'http://localhost:8000/call-tool',
    json={
        'tool': 'get_page_health',
        'arguments': {
            'property': 'https://example.com/',
            'window_days': 28,
            'limit': 10
        }
    }
)

data = response.json()
for page in data['result']:
    print(f"{page['page']}: {page['health_status']}")
```

### cURL Insights API

```bash
# Get page health
curl http://localhost:8001/api/page-health?limit=10

# Get query trends (winners only)
curl "http://localhost:8001/api/query-trends?category=WINNER&limit=20"

# Get directory trends
curl http://localhost:8001/api/directory-trends
```

### SQL Direct Query

```sql
-- Connect to database
psql -h localhost -U gsc_user -d gsc_db

-- Query fact table
SELECT property, page, SUM(clicks) as total_clicks
FROM gsc.fact_gsc_daily
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY property, page
ORDER BY total_clicks DESC
LIMIT 10;

-- Query analytical view
SELECT * FROM gsc.vw_page_health_28d
WHERE health_status = 'DECLINING'
ORDER BY clicks_change_pct ASC
LIMIT 10;
```

---

*Last Updated: November 2025*

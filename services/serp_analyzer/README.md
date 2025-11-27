# SERP Analyzer Service

Google Custom Search Engine (CSE) analyzer for SERP analysis, position tracking, and competitor intelligence.

## Quick Start

```python
from services.serp_analyzer import GoogleCSEAnalyzer

# Initialize
analyzer = GoogleCSEAnalyzer()

# Search
results = analyzer.search('python tutorial')

# Analyze
analysis = analyzer.analyze_serp('python tutorial', 'realpython.com')
print(f"Position: {analysis['target_position']}")
print(f"Competitors: {len(analysis['competitors'])}")
```

## Setup

### 1. Get Google CSE Credentials

1. Create a Google Cloud project
2. Enable Custom Search API
3. Create API key
4. Create Custom Search Engine at https://programmablesearchengine.google.com/

### 2. Set Environment Variables

```bash
export GOOGLE_CSE_API_KEY="your_api_key_here"
export GOOGLE_CSE_ID="your_cse_id_here"
```

### 3. Configuration (Optional)

Edit `config/google_cse_config.yaml`:

```yaml
google_cse:
  rate_limit:
    daily_quota: 100
    requests_per_second: 1
  defaults:
    num_results: 10
    language: en
    country: us
  cache_ttl_minutes: 60
  retries: 3
  retry_delay: 2
```

## Features

- **Quota Management**: Tracks daily API quota (100 queries/day free tier)
- **Caching**: 1-hour TTL cache to reduce API calls
- **Rate Limiting**: Respects API rate limits
- **Retry Logic**: Automatic retries with exponential backoff
- **Thread-Safe**: Safe for concurrent use
- **Position Tracking**: Track your domain's position in SERPs
- **Competitor Analysis**: Identify and analyze competitors
- **SERP Features**: Detect rich snippets, thumbnails, ratings, etc.

## Usage Examples

### Basic Search

```python
analyzer = GoogleCSEAnalyzer()

# Simple search
results = analyzer.search('python tutorial', num_results=10)

for result in results:
    print(f"{result['position']}: {result['title']}")
    print(f"   URL: {result['link']}")
    print(f"   Domain: {result['domain']}")
```

### SERP Analysis

```python
# Analyze for your domain
analysis = analyzer.analyze_serp('python tutorial', 'realpython.com')

print(f"Your position: {analysis['target_position']}")
print(f"Total competitors: {len(analysis['competitors'])}")

# Top competitors
for comp in analysis['competitors'][:3]:
    print(f"  {comp['position']}: {comp['domain']}")
```

### Batch Analysis

```python
queries = [
    'python tutorial',
    'python basics',
    'learn python',
    'python for beginners'
]

results = analyzer.batch_analyze(queries, 'realpython.com')

for r in results:
    pos = r['target_position'] or 'Not ranked'
    print(f"{r['query']}: {pos}")
```

### Check Quota

```python
status = analyzer.get_quota_status()

print(f"Daily quota: {status['daily_quota']}")
print(f"Used today: {status['queries_today']}")
print(f"Remaining: {status['remaining']}")
print(f"Resets on: {status['reset_date']}")
```

### Custom Configuration

```python
analyzer = GoogleCSEAnalyzer(
    api_key='your_key',
    cse_id='your_id',
    config_path='path/to/custom_config.yaml'
)
```

## API Reference

### GoogleCSEAnalyzer

#### `__init__(api_key=None, cse_id=None, config_path=None)`

Initialize the analyzer.

**Parameters:**
- `api_key` (str, optional): Google API key (or use GOOGLE_CSE_API_KEY env var)
- `cse_id` (str, optional): CSE ID (or use GOOGLE_CSE_ID env var)
- `config_path` (str, optional): Path to configuration file

#### `search(query, num_results=None, start=1, language=None, country=None)`

Execute a search query.

**Parameters:**
- `query` (str): Search query
- `num_results` (int, optional): Number of results (max 10)
- `start` (int, optional): Starting result index (1-based)
- `language` (str, optional): Language code (e.g., 'en')
- `country` (str, optional): Country code (e.g., 'us')

**Returns:** List[Dict] - Search results

#### `analyze_serp(query, target_domain, num_results=10)`

Analyze SERP for a target domain.

**Parameters:**
- `query` (str): Search query
- `target_domain` (str): Domain to analyze
- `num_results` (int, optional): Number of results to analyze

**Returns:** Dict - SERP analysis

#### `batch_analyze(queries, target_domain)`

Analyze multiple queries for a domain.

**Parameters:**
- `queries` (List[str]): List of search queries
- `target_domain` (str): Domain to track

**Returns:** List[Dict] - List of analyses

#### `get_quota_status()`

Get current quota status.

**Returns:** Dict - Quota information

#### `clear_cache()`

Clear the response cache.

## Response Formats

### Search Result

```python
{
    'position': 1,
    'title': 'Page Title',
    'link': 'https://example.com/page',
    'display_link': 'example.com',
    'snippet': 'Description...',
    'domain': 'example.com',
    'has_rich_snippet': True,
    'has_thumbnail': False,
    'has_rating': False,
    'has_breadcrumbs': True,
    'og_title': 'OG Title',
    'og_description': 'OG Description'
}
```

### SERP Analysis

```python
{
    'query': 'search query',
    'target_domain': 'example.com',
    'target_position': 3,  # or None if not ranked
    'target_result': {...},  # Full result dict or None
    'competitors': [
        {
            'domain': 'competitor.com',
            'position': 1,
            'title': 'Competitor Page',
            'link': 'https://competitor.com',
            'has_rich_snippet': True
        }
    ],
    'serp_features': ['rich_snippets', 'breadcrumbs'],
    'total_results': 10,
    'analyzed_at': '2025-11-26T10:00:00',
    'domain_distribution': {
        'example.com': 1,
        'competitor.com': 2
    }
}
```

### Quota Status

```python
{
    'daily_quota': 100,
    'queries_today': 15,
    'remaining': 85,
    'reset_date': '2025-11-26'
}
```

## Limitations

### Free Tier
- 100 queries per day
- Maximum 10 results per query
- No access to some SERP features (featured snippets, knowledge panels)

### Rate Limits
- Default: 1 query per second
- Configurable in config file

## Error Handling

The analyzer handles errors gracefully:

- **No credentials**: Logs warning, returns empty results
- **Quota exceeded**: Logs warning, returns empty results
- **API errors**: Retries up to 3 times with exponential backoff
- **Rate limiting (429)**: Automatic retry with delay
- **Network errors**: Retry with exponential backoff

## Testing

Run the test suite:

```bash
pytest tests/services/test_google_cse.py -v
```

All tests use mocks - no real API calls are made.

## Best Practices

1. **Cache Results**: Use the built-in cache to minimize API calls
2. **Monitor Quota**: Check quota status regularly
3. **Batch Operations**: Use `batch_analyze()` for multiple queries
4. **Error Handling**: Always check if results are empty
5. **Rate Limiting**: Respect the rate limits to avoid 429 errors

## Example: Daily Rank Tracking

```python
from services.serp_analyzer import GoogleCSEAnalyzer
import json
from datetime import datetime

analyzer = GoogleCSEAnalyzer()

# Your keywords to track
keywords = [
    'python tutorial',
    'python basics',
    'learn python programming',
    'python for beginners'
]

# Your domain
domain = 'realpython.com'

# Analyze
results = analyzer.batch_analyze(keywords, domain)

# Save results
report = {
    'date': datetime.utcnow().isoformat(),
    'domain': domain,
    'rankings': [
        {
            'keyword': r['query'],
            'position': r['target_position'],
            'competitors': len(r['competitors']),
            'features': r['serp_features']
        }
        for r in results
    ]
}

# Save to file
with open('rank_report.json', 'w') as f:
    json.dump(report, f, indent=2)

print(f"Tracked {len(results)} keywords")
print(f"Remaining quota: {analyzer.get_quota_status()['remaining']}")
```

## Support

For issues or questions:
1. Check the test file for examples: `tests/services/test_google_cse.py`
2. Review the main implementation: `services/serp_analyzer/google_cse.py`
3. Check Google CSE API docs: https://developers.google.com/custom-search/v1/overview

## License

Part of the site-data-warehouse project.

# URL Variations Schema and Parser Guide

## Overview

The URL Variations system tracks and normalizes different variations of the same URL to help identify consolidation opportunities, prevent duplicate content issues, and improve SEO performance.

## Components

### 1. Database Schema (`sql/23_url_variations_schema.sql`)

The schema includes:

#### Main Table: `analytics.url_variations`
Stores individual URL variations with their canonical forms.

**Columns:**
- `property` - Property identifier (e.g., 'sc-domain:example.com')
- `canonical_url` - Normalized URL without tracking parameters
- `variation_url` - Original URL with variations
- `variation_type` - Type of variation (query_param, fragment, trailing_slash, case, protocol, other)
- `first_seen` - When this variation was first observed
- `last_seen` - When this variation was last observed
- `occurrences` - Number of times this variation has been seen

#### Views

**`vw_url_consolidation_candidates`** - URLs with multiple variations that may need consolidation
**`vw_recent_url_variations`** - Variations observed in the last 30 days
**`vw_url_variation_summary`** - Summary of variation types by property
**`vw_high_impact_url_variations`** - Variations with high occurrence counts

#### Functions

**`cleanup_old_url_variations(days_threshold)`** - Remove old variations with low occurrence counts

### 2. URL Parser (`insights_core/url_parser.py`)

Python class for normalizing URLs and detecting variations.

## Usage Examples

### Basic Normalization

```python
from insights_core.url_parser import URLParser

parser = URLParser()

# Remove tracking parameters
url = '/page?utm_source=google&id=123'
canonical = parser.normalize(url)
print(canonical)  # Output: /page?id=123

# Handle case, trailing slash, fragments
url = '/Product/Category/?utm_campaign=test#section'
canonical = parser.normalize(url)
print(canonical)  # Output: /product/category
```

### Extract Variation Information

```python
url = '/page?utm_source=google&id=123&sort=desc#reviews'
info = parser.extract_variations(url)

print(info['has_query'])              # True
print(info['tracking_param_count'])   # 1
print(info['tracking_params'])        # ['utm_source']
print(info['semantic_params'])        # ['id', 'sort']
print(info['has_fragment'])           # True
print(info['has_trailing_slash'])     # False
print(info['is_mixed_case'])          # False
```

### Group URLs by Canonical Form

```python
urls = [
    '/page?utm_source=google',
    '/page?utm_source=facebook',
    '/Page/?utm_campaign=summer',
    '/page',
    '/other'
]

groups = parser.group_by_canonical(urls)

for canonical, variations in groups.items():
    print(f"Canonical: {canonical}")
    print(f"Variations: {len(variations)}")
    for var in variations:
        print(f"  - {var}")
```

### Detect Variation Type

```python
canonical = '/page'
variation = '/page?utm_source=google'

var_type = parser.detect_variation_type(canonical, variation)
print(var_type)  # Output: query_param

# Other types: fragment, trailing_slash, case, protocol, other
```

### Store Variations in Database

```python
parser = URLParser(db_dsn='postgresql://user:pass@host:5432/dbname')

# Store single variation
parser.store_variation(
    property='sc-domain:example.com',
    canonical='/page',
    variation='/page?utm_source=google'
)

# Batch store multiple variations
url_pairs = [
    ('/page', '/page?utm_source=google'),
    ('/page', '/page?utm_source=facebook'),
    ('/other', '/other#section'),
]

count = parser.batch_store_variations('sc-domain:example.com', url_pairs)
print(f"Stored {count} variations")
```

### Detect Consolidation Opportunities

```python
parser = URLParser(db_dsn='postgresql://user:pass@host:5432/dbname')

opportunities = parser.detect_consolidation_opportunities('sc-domain:example.com')

for opp in opportunities:
    print(f"Canonical: {opp['canonical_url']}")
    print(f"Variations: {opp['variation_count']}")
    print(f"Types: {opp['variation_types']}")
    print(f"Recommendation: {opp['recommendation']}")
    print()
```

## Tracking Parameters

The parser recognizes and removes over 50 tracking parameters from various platforms:

### UTM Parameters (Google Analytics)
- `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`
- `utm_id`, `utm_source_platform`, `utm_creative_format`, `utm_marketing_tactic`

### Social Media
- **Facebook:** `fbclid`, `fb_action_ids`, `fb_action_types`, `fb_source`, `fbadid`, etc.
- **Twitter:** `twclid`, `twsrc`
- **LinkedIn:** `li_fat_id`, `lipi`
- **TikTok:** `ttclid`

### Advertising Platforms
- **Google:** `gclid`, `gclsrc`, `dclid`, `gbraid`, `wbraid`
- **Microsoft/Bing:** `msclkid`, `mstoken`
- **Yandex:** `yclid`

### Email Marketing
- **Mailchimp:** `mc_cid`, `mc_eid`
- **HubSpot:** `_hsenc`, `_hsmi`
- **Klaviyo:** `klaviyo`

### Analytics & Session
- `_ga`, `_gl`, `_gac` (Google Analytics client-side)
- `sessionid`, `sid`, `token`, `auth`

## Semantic Parameters (Preserved)

These parameters have semantic meaning and are preserved:

### Navigation & Pagination
- `id`, `page`, `p`, `offset`, `limit`, `start`

### Search & Filtering
- `q`, `query`, `search`, `s`, `keywords`, `term`
- `sort`, `order`, `orderby`, `sortby`, `dir`, `direction`
- `filter`, `filters`, `facets`, `category`, `categories`

### Content Selection
- `type`, `format`, `view`, `display`, `mode`

### Localization
- `lang`, `language`, `locale`, `region`, `country`

### Product/Commerce
- `sku`, `product`, `variant`, `color`, `size`

## Database Queries

### Find URLs with Most Variations

```sql
SELECT
    canonical_url,
    variation_count,
    total_occurrences,
    variation_types
FROM analytics.vw_url_consolidation_candidates
WHERE property = 'sc-domain:example.com'
ORDER BY variation_count DESC
LIMIT 20;
```

### Recent URL Variations

```sql
SELECT
    canonical_url,
    variation_url,
    variation_type,
    occurrences,
    last_seen
FROM analytics.vw_recent_url_variations
WHERE property = 'sc-domain:example.com'
    AND occurrences >= 5
ORDER BY last_seen DESC;
```

### Variation Summary by Type

```sql
SELECT
    variation_type,
    variation_count,
    total_occurrences,
    affected_urls
FROM analytics.vw_url_variation_summary
WHERE property = 'sc-domain:example.com'
ORDER BY total_occurrences DESC;
```

### High-Impact Variations

```sql
SELECT
    canonical_url,
    variation_url,
    variation_type,
    occurrences,
    avg_occurrences_per_day
FROM analytics.vw_high_impact_url_variations
WHERE property = 'sc-domain:example.com'
    AND variation_type = 'query_param'
ORDER BY occurrences DESC
LIMIT 50;
```

## Integration with Ingestors

### GSC Ingestion

```python
from insights_core.url_parser import URLParser

parser = URLParser(db_dsn=os.getenv('WAREHOUSE_DSN'))

# During GSC data collection
for row in gsc_data:
    original_url = row['page']
    canonical_url = parser.normalize(original_url)

    # Store variation if different
    if original_url != canonical_url:
        parser.store_variation(
            property=property_name,
            canonical=canonical_url,
            variation=original_url
        )

    # Use canonical URL for analytics
    row['canonical_page'] = canonical_url
```

### GA4 Ingestion

```python
# Similar integration for GA4 page paths
for event in ga4_events:
    page_path = event['page_path']
    canonical_path = parser.normalize(page_path)

    if page_path != canonical_path:
        parser.store_variation(
            property=ga4_property_id,
            canonical=canonical_path,
            variation=page_path
        )
```

## Consolidation Recommendations

The system generates specific recommendations based on variation types:

### Query Parameter Variations
**Issue:** Multiple URLs with tracking parameters
**Recommendation:** Set up canonical tags and 301 redirects
```html
<link rel="canonical" href="https://example.com/page" />
```

### Trailing Slash Variations
**Issue:** `/page` vs `/page/`
**Recommendation:** Standardize trailing slash usage, add redirects
```nginx
# Nginx example - remove trailing slashes
rewrite ^/(.*)/$ /$1 permanent;
```

### Case Variations
**Issue:** `/Page` vs `/page`
**Recommendation:** Normalize to lowercase, add case-insensitive redirects
```apache
# Apache example
RewriteMap lc int:tolower
RewriteCond %{REQUEST_URI} [A-Z]
RewriteRule ^(.*)$ ${lc:$1} [R=301,L]
```

### Fragment Variations
**Issue:** `/page#section` variations
**Recommendation:** Review if fragments should be separate pages or use JavaScript routing

### Protocol Variations
**Issue:** `http://` vs `https://`
**Recommendation:** Implement HTTPS redirects and HSTS
```apache
# Apache example
RewriteCond %{HTTPS} off
RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]
```

## Maintenance

### Cleanup Old Variations

```sql
-- Remove variations older than 90 days with less than 5 occurrences
SELECT analytics.cleanup_old_url_variations(90);
```

### Monitor Variation Growth

```sql
-- Check variation growth over time
SELECT
    DATE_TRUNC('day', created_at) as date,
    COUNT(*) as new_variations,
    COUNT(DISTINCT canonical_url) as unique_canonicals
FROM analytics.url_variations
WHERE property = 'sc-domain:example.com'
    AND created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY date;
```

## Testing

Run the comprehensive test suite:

```bash
pytest tests/insights_core/test_url_parser.py -v
```

Test coverage includes:
- URL normalization (tracking params, case, trailing slashes)
- Variation extraction and detection
- Grouping and classification
- Database operations (with mocks)
- Edge cases and error handling

## Performance Considerations

1. **Batch Operations:** Use `batch_store_variations()` for bulk inserts
2. **Indexing:** Schema includes indexes on property, canonical_url, variation_type
3. **Caching:** Consider caching canonical URLs for frequently accessed pages
4. **Cleanup:** Schedule regular cleanup of old, low-occurrence variations

## Troubleshooting

### Issue: Too Many Variations Detected

**Cause:** Semantic parameters incorrectly classified as tracking params
**Solution:** Add parameter to `PRESERVE_PARAMS` set

```python
# In url_parser.py
PRESERVE_PARAMS = {
    # ... existing params ...
    'your_param_name',  # Add your custom parameter
}
```

### Issue: Variations Not Grouping Correctly

**Cause:** Semantic parameters causing separate canonical URLs
**Solution:** Review if parameters should be removed or normalized differently

### Issue: Database Connection Errors

**Cause:** Missing or incorrect `WAREHOUSE_DSN` environment variable
**Solution:** Set database connection string:

```bash
export WAREHOUSE_DSN='postgresql://user:pass@host:5432/dbname'
```

## Best Practices

1. **Review Regularly:** Check consolidation opportunities weekly
2. **Test First:** Test URL changes on staging before production
3. **Monitor Impact:** Track changes in search console after implementing redirects
4. **Document Decisions:** Keep track of why certain parameters are preserved/removed
5. **Update Patterns:** Add new tracking parameters as platforms introduce them

## Related Documentation

- [GSC Integration Guide](GSC_INTEGRATION.md)
- [GA4 Integration Guide](GA4_INTEGRATION.md)
- [Technical Architecture](../analysis/TECHNICAL_ARCHITECTURE.md)
- [Deployment Guide](../DEPLOYMENT.md)

## Support

For issues or questions:
1. Check test suite for usage examples
2. Review code comments in `insights_core/url_parser.py`
3. Examine sample data in database views
4. Consult SQL schema documentation

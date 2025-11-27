# URL Consolidation Guide

## Overview
URL consolidation helps eliminate SEO issues caused by content being accessible through multiple URL variations. This guide explains how to use the URL consolidation system to identify and fix these issues.

## What is URL Consolidation?

URL consolidation is the process of combining traffic and ranking signals from multiple URL variations into a single canonical URL. This prevents:

- **Content Dilution**: Search engines splitting ranking power across variations
- **Duplicate Content Issues**: Penalties for similar content at different URLs
- **Link Equity Loss**: Backlinks split across variations instead of consolidated
- **Crawl Budget Waste**: Search engines crawling duplicate content

## Common URL Variation Types

### 1. Query Parameter Variations
```
/page               (canonical)
/page?utm_source=google
/page?utm_campaign=summer
/page?ref=twitter
```
**Solution**: Canonical tags + optional redirects for tracking parameters

### 2. Trailing Slash Variations
```
/page               (canonical)
/page/
```
**Solution**: 301 redirects to standardize

### 3. Case Variations
```
/page               (canonical)
/Page
/PAGE
```
**Solution**: 301 redirects to lowercase

### 4. Protocol Variations
```
https://example.com/page    (canonical)
http://example.com/page
```
**Solution**: 301 redirects from HTTP to HTTPS

### 5. Fragment Variations
```
/page               (canonical)
/page#section1
/page#section2
```
**Solution**: Evaluate if fragments should be separate pages

## Using the System

### 1. Finding Consolidation Opportunities

#### Via Python API
```python
from insights_core.url_consolidator import URLConsolidator

consolidator = URLConsolidator(db_dsn='postgresql://user:pass@localhost/db')
candidates = consolidator.find_consolidation_candidates('sc-domain:example.com')

for candidate in candidates[:10]:  # Top 10
    print(f"\nURL: {candidate['canonical_url']}")
    print(f"Variations: {candidate['variation_count']}")
    print(f"Score: {candidate['consolidation_score']}")
    print(f"Action: {candidate['recommended_action']}")
    print(f"Traffic: {candidate['total_clicks']} clicks")
    print(f"Impact: {candidate['potential_impact']}")
```

#### Via SQL
```sql
-- High priority opportunities
SELECT
    canonical_url,
    variation_count,
    consolidation_score,
    recommended_action,
    total_clicks,
    total_impressions
FROM analytics.vw_high_priority_consolidations
WHERE property = 'sc-domain:example.com'
ORDER BY consolidation_score DESC
LIMIT 20;
```

### 2. Understanding Priority Scores

Scores range from 0-100 and are calculated based on:
- **Traffic** (40% weight): Higher traffic = higher priority
- **Rankings** (30% weight): Better rankings = higher priority
- **Freshness** (15% weight): Recent activity = higher priority
- **Variations** (15% weight): More variations = higher priority

**Priority Levels**:
- **High (80-100)**: Immediate action recommended
- **Medium (50-79)**: Action recommended soon
- **Low (0-49)**: Monitor or low priority

### 3. Recommended Actions

#### Canonical Tag
Add to HTML `<head>` of variation pages:
```html
<link rel="canonical" href="https://example.com/page" />
```

**When to Use**:
- Medium priority
- Query parameter variations
- You want to keep variations accessible

#### 301 Redirect
Add to server configuration:

**Apache (.htaccess)**:
```apache
RewriteEngine On
RewriteRule ^page/$ /page [R=301,L]
```

**Nginx**:
```nginx
location /page/ {
    return 301 /page;
}
```

**When to Use**:
- High priority
- Trailing slash, case, or protocol variations
- You want to eliminate variations entirely

#### Canonical Tag + Redirect
Implement both for maximum consolidation.

**When to Use**:
- High priority query parameter variations
- Strong consolidation signal needed

### 4. Taking Action on Candidates

#### Mark as Actioned
```python
# Via Python
from insights_core.url_consolidator import URLConsolidator

consolidator = URLConsolidator(db_dsn='postgresql://...')
```

```sql
-- Via SQL
SELECT analytics.mark_consolidation_actioned(
    p_candidate_id := 123,
    p_action_taken := 'redirect_implemented',
    p_action_details := '{"redirect_type": "301", "from": "/page/", "to": "/page"}',
    p_performed_by := 'admin@example.com'
);
```

#### Dismiss a Candidate
```sql
SELECT analytics.dismiss_consolidation_candidate(
    p_candidate_id := 456,
    p_reason := 'Variations are intentional for different audiences',
    p_performed_by := 'admin@example.com'
);
```

### 5. Tracking Outcomes

After implementing consolidation:

```sql
-- Track the outcome
SELECT analytics.track_consolidation_outcome(
    p_candidate_id := 123,
    p_outcome := '{
        "clicks_before": 150,
        "clicks_after": 180,
        "position_before": 8.5,
        "position_after": 7.2,
        "improvement_pct": 20,
        "measured_at": "2025-12-01"
    }'::jsonb
);
```

## Best Practices

### 1. Start with High Priority
Focus on candidates with scores > 80 first. These have the most impact potential.

### 2. Test Before Full Deployment
- Start with 2-3 low-traffic pages
- Monitor for 2 weeks
- Check for traffic/ranking changes
- Scale if successful

### 3. Use Appropriate Method
- **Redirects** for permanent consolidation (can't be undone easily)
- **Canonical tags** for soft consolidation (reversible)
- **Both** for maximum signal when high stakes

### 4. Monitor After Implementation
```sql
-- Check recent actions and outcomes
SELECT
    canonical_url,
    action_taken,
    performed_at,
    outcome->>'improvement_pct' as improvement
FROM analytics.vw_recent_consolidation_actions
WHERE property = 'sc-domain:example.com'
    AND performed_at >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY performed_at DESC;
```

### 5. Regular Review
Run consolidation detection weekly to catch new variations:
```python
# Automated detection
from insights_core.detectors.opportunity import OpportunityDetector
from insights_core.repository import InsightRepository
from insights_core.config import InsightsConfig

repo = InsightRepository(dsn='postgresql://...')
config = InsightsConfig(warehouse_dsn='postgresql://...')
detector = OpportunityDetector(repository=repo, config=config)

# Run for all properties
insights_created = detector.detect()
print(f"Created {insights_created} new consolidation insights")
```

## Common Scenarios

### Scenario 1: Marketing Tracking Parameters
**Problem**: Marketing campaigns create dozens of URL variations
```
/product?utm_source=facebook&utm_campaign=summer
/product?utm_source=google&utm_campaign=summer
/product?utm_source=email&utm_campaign=summer
```

**Solution**:
1. Set canonical to `/product` on all variations
2. Ensure analytics still tracks parameters
3. Consider Google Search Console parameter handling

### Scenario 2: Trailing Slash Inconsistency
**Problem**: Internal links use both `/page` and `/page/`

**Solution**:
1. Implement 301 redirects to standardize
2. Update site-wide templates
3. Fix internal links
4. Update sitemap

### Scenario 3: Legacy HTTP URLs
**Problem**: Old backlinks point to HTTP version

**Solution**:
1. Implement server-wide HTTP→HTTPS redirect
2. Update internal links
3. Submit HTTPS sitemap
4. Request HSTS preloading

### Scenario 4: Case Sensitivity Issues
**Problem**: URLs accessible with different casing

**Solution**:
1. Enforce lowercase URLs via redirects
2. Update site configuration for case-insensitive routing
3. Fix internal links

## Troubleshooting

### Issue: No Candidates Found
**Possible Causes**:
- No URL variations exist (good!)
- url_variations table not populated
- Recent data not available

**Check**:
```sql
SELECT COUNT(*) FROM analytics.url_variations
WHERE property = 'sc-domain:example.com';
```

### Issue: Low Priority Scores
**Possible Causes**:
- Low traffic to affected pages
- Old variation data (not recent)
- Few variations per canonical

**Action**: Focus on the highest-scoring candidates you have

### Issue: Canonical Selection Seems Wrong
**Review**:
```python
url_group = {
    'canonical_url': '/page',
    'url_metrics': candidates[0]['url_metrics'],
    'variation_types': candidates[0]['variation_types']
}
result = consolidator.recommend_canonical(url_group)
print(f"Chosen: {result['url']}")
print(f"Reason: {result['reason']}")
print(f"Score: {result['score']}")
```

## Maintenance

### Weekly Tasks
1. Review new high-priority candidates
2. Monitor outcomes of recent actions
3. Update dismissed candidates if situation changes

### Monthly Tasks
1. Clean up old dismissed candidates:
```sql
DELETE FROM analytics.consolidation_candidates
WHERE status = 'dismissed'
    AND updated_at < CURRENT_DATE - INTERVAL '90 days';
```

2. Review consolidation success rate:
```sql
SELECT
    COUNT(*) as total_actions,
    COUNT(*) FILTER (WHERE outcome->>'improvement_pct' > '0') as successes,
    AVG((outcome->>'improvement_pct')::float) as avg_improvement
FROM analytics.consolidation_history
WHERE performed_at >= CURRENT_DATE - INTERVAL '30 days'
    AND outcome IS NOT NULL;
```

### Quarterly Tasks
1. Archive old history
2. Review and update scoring weights if needed
3. Analyze patterns across properties

## API Reference

### Main Methods

#### `find_consolidation_candidates(property, limit=100)`
Find consolidation opportunities for a property.

**Returns**: List of candidates with scores and recommendations

#### `calculate_consolidation_score(url_group)`
Calculate priority score (0-100) for a URL group.

**Returns**: Float score

#### `recommend_canonical(url_group)`
Recommend which URL should be canonical.

**Returns**: Dict with url, reason, and score

#### `create_consolidation_insight(candidate, property)`
Create an insight for a candidate.

**Returns**: InsightCreate object

#### `store_candidate(candidate)`
Store candidate in database.

**Returns**: Boolean success

#### `get_consolidation_history(property)`
Get action history for a property.

**Returns**: List of history records

## Support

For questions or issues:
1. Check this guide first
2. Review the implementation docs at `docs/implementation/TASKCARD-028_IMPLEMENTATION.md`
3. Examine test cases at `tests/insights_core/test_url_consolidator.py`
4. Check the source code at `insights_core/url_consolidator.py`

## Related Documentation
- TASKCARD-024: URL Parser (foundation for consolidation)
- Insight Engine Guide
- Opportunity Detector Documentation

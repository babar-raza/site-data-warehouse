# Quick Reference: CSE Integration with DiagnosisDetector

## TL;DR

DiagnosisDetector now includes optional GoogleCSE integration for real-time SERP analysis and competitor insights.

## Quick Start

### Basic Usage (CSE Enabled by Default)
```python
from insights_core.detectors.diagnosis import DiagnosisDetector

detector = DiagnosisDetector(repository, config)
insights = detector.detect(property="sc-domain:example.com")
```

### Disable CSE
```python
detector = DiagnosisDetector(repository, config, use_cse=False)
```

## What You Get

When a ranking issue is diagnosed and SERP data is available:

✅ **Current SERP position** for the query
✅ **Top competitors** (up to 5) with details
✅ **Rich snippet detection** (who has them)
✅ **SERP features** present (thumbnails, breadcrumbs, etc.)
✅ **Competitive analysis** in plain English

## Example Output

**Before CSE Integration:**
```
Root cause identified: Search ranking declined significantly.
Average position worsened by 12.0 spots week-over-week.
```

**After CSE Integration:**
```
Root cause identified: Search ranking declined significantly.
Average position worsened by 12.0 spots week-over-week.

Current SERP position for 'python tutorial': #5.
Top competitors: realpython.com, tutorialspoint.com, w3schools.com.
2 of top 3 competitors have rich snippets.
SERP features detected: rich_snippets, thumbnails, breadcrumbs.
```

## Configuration (Optional)

### Environment Variables
```bash
export GOOGLE_CSE_API_KEY="your-api-key"
export GOOGLE_CSE_ID="your-cse-id"
```

### Config File
```yaml
# config/google_cse_config.yaml
google_cse:
  daily_quota: 100
  cache_ttl_minutes: 60
  num_results: 10
```

## API Quota

- **Free Tier:** 100 queries/day
- **Quota Management:** Automatic (checks before each call)
- **Minimum Reserved:** 5 queries (configurable)
- **Low Quota Behavior:** Skips CSE, diagnosis continues normally

## Testing

### Run CSE Tests
```bash
pytest tests/insights_core/test_diagnosis_cse.py -v
```

### Verify Integration
```bash
python tests/insights_core/verify_diagnosis_cse_integration.py
```

## Key Features

### Graceful Degradation ✅
- Works without CSE configured
- Works without API keys
- Works with CSE errors
- Never blocks diagnosis

### Smart Quota Management ✅
- Checks quota before calls
- Reserves minimum threshold
- Caches results (60min TTL)
- Logs quota warnings

### Rich Insights ✅
- Real-time SERP position
- Competitor identification
- Rich snippet analysis
- SERP feature detection

## Access SERP Data

### From Diagnosis Insights
```python
diagnosis = detector._diagnose_risk(risk)

# SERP data in metrics
serp_position = diagnosis.metrics.serp_position
serp_competitors = diagnosis.metrics.serp_top_competitors
serp_features = diagnosis.metrics.serp_features

# SERP insights in description
print(diagnosis.description)
# Includes position, competitors, features
```

### Direct SERP Context
```python
serp_data = detector._get_serp_context(
    property="sc-domain:example.com",
    query="python tutorial"
)

if serp_data:
    print(f"Position: {serp_data['target_position']}")
    print(f"Competitors: {serp_data['competitors']}")
    print(f"Features: {serp_data['serp_features']}")
```

## Troubleshooting

### CSE Not Working?

1. **Check API keys:**
   ```bash
   echo $GOOGLE_CSE_API_KEY
   echo $GOOGLE_CSE_ID
   ```

2. **Check quota:**
   ```python
   status = detector.cse_analyzer.get_quota_status()
   print(f"Remaining: {status['remaining']}")
   ```

3. **Check logs:**
   ```
   Look for: "CSE quota low, skipping SERP analysis"
   Or: "CSE analysis failed: ..."
   ```

### Common Issues

**"No API key configured"**
→ Set `GOOGLE_CSE_API_KEY` environment variable

**"CSE quota low"**
→ Wait for daily reset or increase `daily_quota` in config

**"CSE analyzer not available"**
→ Install: `pip install google-api-python-client`

## Performance

- **Lazy Loading:** CSE only initialized when needed
- **Caching:** Results cached for 60 minutes
- **Rate Limiting:** 1 request/second (configurable)
- **Timeout:** 30 seconds per request
- **Retries:** 3 attempts with exponential backoff

## Integration with Other Features

### With EventCorrelationEngine
```python
detector = DiagnosisDetector(
    repository, config,
    use_correlation=True,  # Git commits, algorithm updates
    use_cse=True          # SERP insights
)
# Gets both trigger events AND SERP context
```

### With CausalAnalyzer
```python
detector = DiagnosisDetector(
    repository, config,
    use_causal_analysis=True,  # Statistical significance
    use_cse=True              # SERP insights
)
# Gets causal analysis AND SERP context
```

### All Together
```python
detector = DiagnosisDetector(
    repository, config,
    use_correlation=True,
    use_causal_analysis=True,
    use_cse=True
)
# Maximum insights: triggers + causality + SERP
```

## Documentation

- **Full Implementation:** `docs/implementation/TASKCARD-040-CSE-INTEGRATION.md`
- **Test Documentation:** `tests/insights_core/README_CSE_TESTS.md`
- **Completion Summary:** `TASKCARD-040-COMPLETION-SUMMARY.md`
- **Main Code:** `insights_core/detectors/diagnosis.py`
- **CSE Analyzer:** `services/serp_analyzer/google_cse.py`

## Support

For issues or questions:

1. Check logs for warnings/errors
2. Run verification script
3. Check test suite
4. Review documentation

## Version

- **Feature:** CSE Integration
- **Taskcard:** TASKCARD-040
- **Status:** ✅ Complete
- **Date:** November 26, 2025
- **Tests:** 19 tests, 100% passing

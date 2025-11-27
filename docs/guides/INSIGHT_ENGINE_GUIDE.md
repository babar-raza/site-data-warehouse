# Insight Engine - Complete Guide

**Version:** 2.0
**Last Updated:** 2025
**Audience:** All users, developers, data analysts

---

## Table of Contents

1. [What Is the Insight Engine?](#what-is-the-insight-engine)
2. [How the Insight Engine Works](#how-the-insight-engine-works)
3. [Detector Types](#detector-types)
4. [Insight Categories & Severity](#insight-categories--severity)
5. [Detection Rules Reference](#detection-rules-reference)
6. [Insight Workflow](#insight-workflow)
7. [Using Insights](#using-insights)
8. [Configuration & Tuning](#configuration--tuning)
9. [API Reference](#api-reference)
10. [Troubleshooting](#troubleshooting)

---

## What Is the Insight Engine?

The **Insight Engine** is an automated system that continuously monitors your site's performance data (GSC + GA4) and automatically detects:

- 🔴 **Problems** (traffic drops, ranking losses, conversion issues)
- 🟢 **Opportunities** (growth potential, optimization targets)
- 🔵 **Root Causes** (why problems happened)
- 🟡 **Trends** (long-term patterns)

### Why Automated Insights?

**Manual Analysis Problems**:
- Time-consuming (hours per week)
- Easy to miss important changes
- Requires expertise to interpret patterns
- Cannot monitor 24/7

**Insight Engine Benefits**:
- ✅ Detects problems within 24 hours
- ✅ Analyzes 100% of pages automatically
- ✅ Provides actionable recommendations
- ✅ Frees up team time for strategic work

### What Makes It "Intelligent"?

1. **Statistical Analysis**: Uses z-scores, standard deviations, and percentile ranking
2. **Contextual Understanding**: Considers historical baselines, not just absolute values
3. **Cross-Metric Correlation**: Detects when multiple metrics drop together (stronger signal)
4. **Deterministic Deduplication**: Same issue won't create multiple insights

---

## How the Insight Engine Works

### High-Level Process

```
┌─────────────────────────────────────────────────┐
│  1. SCHEDULED TRIGGER (Daily 2 AM UTC)          │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  2. QUERY UNIFIED VIEW                          │
│     SELECT * FROM vw_unified_page_performance   │
│     WHERE date >= CURRENT_DATE - 7 days         │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  3. RUN DETECTORS IN SEQUENCE                   │
│     ├─ AnomalyDetector                          │
│     ├─ DiagnosisDetector                        │
│     └─ OpportunityDetector                      │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  4. CREATE INSIGHTS                             │
│     Each detector creates InsightCreate objects │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  5. STORE IN DATABASE                           │
│     INSERT INTO gsc.insights                    │
│     ON CONFLICT (id) DO UPDATE ...              │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  6. AVAILABLE IN DASHBOARDS & API               │
└─────────────────────────────────────────────────┘
```

### Engine Architecture

```python
class InsightEngine:
    """Main orchestrator for insight detection"""

    def __init__(self, config: InsightsConfig):
        self.config = config
        self.repository = InsightRepository(config.warehouse_dsn)

        # Register all detectors
        self.detectors = [
            # Core detectors
            AnomalyDetector(self.repository, self.config),      # Traffic/conversion anomalies
            DiagnosisDetector(self.repository, self.config),    # Root cause analysis
            OpportunityDetector(self.repository, self.config),  # Growth opportunities

            # Advanced detectors (implemented in 2025)
            ContentQualityDetector(self.repository, self.config),  # Content quality issues
            TrendDetector(self.repository, self.config),           # Gradual trend patterns
            TopicStrategyDetector(self.repository, self.config),   # Topic coverage/strategy
            CWVQualityDetector(self.repository, self.config),      # Core Web Vitals quality
            CannibalizationDetector(self.repository, self.config), # Keyword cannibalization
        ]

    def refresh(self, property: str = None) -> dict:
        """
        Run all detectors and return statistics

        Returns:
            {
                'total_insights_created': 42,
                'insights_by_detector': {
                    'AnomalyDetector': 15,
                    'DiagnosisDetector': 10,
                    'OpportunityDetector': 17
                },
                'duration_seconds': 12.34
            }
        """
        stats = {}

        for detector in self.detectors:
            try:
                count = detector.detect(property=property)
                stats[detector.__class__.__name__] = count
            except Exception as e:
                logger.error(f"{detector.__class__.__name__} failed: {e}")
                stats[detector.__class__.__name__] = 0

        return stats
```

### Execution Flow

**Step 1: Trigger**
- Scheduled: Daily at 2 AM UTC
- Manual: `python -m insights_core.cli refresh`
- API: `POST /insights/refresh`

**Step 2: Data Query**
Each detector queries `vw_unified_page_performance`:
```sql
SELECT *
FROM gsc.vw_unified_page_performance
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
  AND (
      gsc_clicks_change_wow < -20
      OR ga_conversions_change_wow < -20
      OR gsc_impressions_change_wow > 50
  )
```

**Step 3: Detection Logic**
For each row matching criteria:
1. Calculate severity (high, medium, low)
2. Calculate confidence (0.0 to 1.0)
3. Generate title and description
4. Create InsightCreate object

**Step 4: Deduplication**
Before storing, generate deterministic ID:
```python
insight_id = SHA256(
    property + entity_type + entity_id +
    category + source + window_days
)
```
Same ID = same issue = no duplicate

**Step 5: Storage**
```sql
INSERT INTO gsc.insights (...)
VALUES (...)
ON CONFLICT (id) DO UPDATE SET
    updated_at = CURRENT_TIMESTAMP
```
Re-detecting same issue updates timestamp but doesn't create duplicate

---

## Detector Types

### 1. AnomalyDetector

**Purpose**: Find statistical anomalies in traffic and conversions

**What It Detects**:
- Traffic drops (clicks down >20% WoW)
- Conversion drops (conversions down >20% WoW)
- Impression surges (impressions up >50% WoW)
- Correlated drops (both clicks AND conversions down)

**Data Source**: `vw_unified_page_performance` (last 7 days)

**Detection Window**: Week-over-Week (WoW) comparisons

**Example Output**:
```
Title: "Traffic & Conversion Drop"
Description: "Page experiencing significant decline in both traffic and
             conversions. Clicks down 45.2%, conversions down 32.1%
             week-over-week."
Category: risk
Severity: high
Confidence: 0.9
```

**Detection Rules**:

| Condition | Category | Severity | Confidence |
|-----------|----------|----------|------------|
| Clicks < -20% AND Conversions < -20% | risk | high | 0.9 |
| Clicks < -20% | risk | medium | 0.8 |
| Impressions > +50% | opportunity | medium | 0.75 |

**Code Example**:
```python
def _analyze_row(self, row: dict) -> List[InsightCreate]:
    insights = []

    clicks_change = row.get('gsc_clicks_change_wow', 0)
    conversions_change = row.get('ga_conversions_change_wow', 0)

    # High severity: Both metrics dropping
    if (clicks_change < -20 and conversions_change < -20):
        insights.append(InsightCreate(
            property=row['property'],
            entity_type=EntityType.PAGE,
            entity_id=row['page_path'],
            category=InsightCategory.RISK,
            title="Traffic & Conversion Drop",
            description=f"Clicks down {abs(clicks_change):.1f}%, "
                       f"conversions down {abs(conversions_change):.1f}%",
            severity=InsightSeverity.HIGH,
            confidence=0.9,
            metrics=InsightMetrics(...),
            window_days=7,
            source="AnomalyDetector"
        ))

    return insights
```

---

### 2. DiagnosisDetector

**Purpose**: Perform root cause analysis on detected risks

**What It Does**:
- Links to risks created by AnomalyDetector
- Analyzes timing of drops
- Checks for technical issues
- Identifies pattern similarities
- Generates hypotheses

**Data Source**:
- `gsc.insights` (existing risks)
- `vw_unified_page_performance` (historical context)
- External events (if configured)

**Detection Window**: 30-day historical analysis

**Example Output**:
```
Title: "Root Cause: Content Update"
Description: "Traffic drop correlates with content update on 2024-11-15.
             Similar pattern observed on 3 other pages updated same day.
             Recommendation: Review content changes for SEO issues."
Category: diagnosis
Severity: medium
Confidence: 0.7
Linked To: insight_abc123 (Traffic & Conversion Drop)
```

**Diagnosis Types**:

1. **Timing Correlation**
   - Drop coincides with deployment
   - Drop coincides with algorithm update
   - Seasonal pattern

2. **Technical Issues**
   - Page became slow (>3s load time)
   - 404/500 errors detected
   - Robots.txt blocking

3. **Content Issues**
   - Thin content (word count dropped)
   - Keyword cannibalization
   - Duplicate content

4. **Pattern Matching**
   - Similar drops on related pages
   - Directory-wide issues
   - Site-wide problems

**Code Flow**:
```python
def detect(self, property: str = None) -> int:
    # 1. Get all undiagnosed risks
    risks = self.repository.query(
        InsightQuery(
            category=InsightCategory.RISK,
            status=InsightStatus.NEW
        )
    )

    insights_created = 0

    for risk in risks:
        # 2. Gather context
        context = self._gather_context(risk)

        # 3. Test hypotheses
        hypotheses = self._test_hypotheses(context)

        # 4. Create diagnosis
        if hypotheses:
            diagnosis = self._create_diagnosis(risk, hypotheses)
            self.repository.create(diagnosis)
            insights_created += 1

    return insights_created
```

---

### 3. OpportunityDetector

**Purpose**: Find optimization opportunities and growth potential

**What It Detects**:
- High-potential pages (high impressions, low CTR)
- Hidden gems (high conversion rate, low visibility)
- Quick wins (small ranking improvement = big traffic gain)
- Content gaps (queries with impressions but no dedicated page)

**Data Source**: `vw_unified_page_performance` (last 30 days)

**Detection Window**: 30-day aggregates

**Example Output**:
```
Title: "High-Potential Page: CTR Optimization"
Description: "Page has 50,000 impressions/month but only 2.1% CTR.
             Industry average is 4.5%. Improving CTR to 4% would gain
             950 additional clicks/month. Recommendation: Rewrite meta
             title and description to be more compelling."
Category: opportunity
Severity: medium
Confidence: 0.8
```

**Opportunity Types**:

1. **CTR Optimization**
   ```
   Criteria: impressions > 1000 AND ctr < 2.5% AND position < 10
   Potential: (target_ctr - current_ctr) * impressions
   Action: Rewrite meta tags
   ```

2. **Ranking Opportunity**
   ```
   Criteria: conversions > 10 AND position > 10
   Potential: position improvement → traffic multiplier
   Action: On-page SEO, backlinks
   ```

3. **Engagement Opportunity**
   ```
   Criteria: clicks > 100 AND engagement_rate < 0.2
   Potential: Better engagement → better rankings
   Action: Improve content quality, UX
   ```

4. **Conversion Opportunity**
   ```
   Criteria: sessions > 100 AND conversions = 0
   Potential: Add conversion path
   Action: Add CTAs, optimize funnel
   ```

**Code Example**:
```python
def detect(self, property: str = None) -> int:
    query = """
        SELECT *
        FROM gsc.vw_unified_page_performance
        WHERE date >= CURRENT_DATE - INTERVAL '30 days'
        AND (
            (gsc_impressions > 1000 AND gsc_ctr < 2.5 AND gsc_position < 10)
            OR (ga_conversions > 10 AND gsc_position > 10)
            OR (gsc_clicks > 100 AND ga_engagement_rate < 0.2)
            OR (ga_sessions > 100 AND ga_conversions = 0)
        )
        GROUP BY property, page_path
    """

    # Analyze each opportunity
    for row in rows:
        if row['gsc_impressions'] > 1000 and row['gsc_ctr'] < 2.5:
            # CTR opportunity
            potential_clicks = row['gsc_impressions'] * (0.04 - row['gsc_ctr'])

            insights.append(InsightCreate(
                category=InsightCategory.OPPORTUNITY,
                title="High-Potential Page: CTR Optimization",
                description=f"Improving CTR from {row['gsc_ctr']:.1f}% to 4% "
                           f"would gain {potential_clicks:.0f} clicks/month",
                severity=InsightSeverity.MEDIUM,
                confidence=0.8,
                ...
            ))
```

---

### 4. ContentQualityDetector

**Purpose**: Analyze page content for SEO quality issues

**What It Detects**:
- Low readability (Flesch Reading Ease < 60)
- Missing or short meta descriptions
- Title length issues (< 30 or > 60 chars)
- Missing H1 tags
- Thin content (word count < 300)
- Keyword cannibalization (via embeddings)

**Data Source**: `content.page_snapshots` table

**Example Output**:
```
Title: "Content Quality Issue: Thin Content"
Description: "Page has only 187 words. Minimum recommended is 300+.
             Consider expanding content to improve search rankings."
Category: risk
Severity: medium
Confidence: 0.85
```

---

### 5. TrendDetector

**Purpose**: Identify gradual trends (not just sudden anomalies)

**What It Detects**:
- Gradual traffic decline (slope < -0.1, R² > 0.7)
- Gradual traffic growth (slope > 0.1, R² > 0.7)
- Cyclical patterns (seasonal variations)

**Detection Method**: Linear regression using scipy.stats.linregress over 90-day window

**Data Source**: `vw_unified_page_performance` (90-day lookback)

**Example Output**:
```
Title: "Gradual Traffic Decline"
Description: "Page shows consistent declining trend over 90 days.
             Slope: -0.15, R²: 0.82. Traffic down ~40% from baseline."
Category: trend
Severity: medium
Metrics: {trend_slope: -0.15, r_squared: 0.82, days_analyzed: 90}
```

---

### 6. TopicStrategyDetector

**Purpose**: Analyze topic coverage and content strategy using clustering

**What It Detects**:
- Topic gaps (queries with impressions but no dedicated pages)
- Topic coverage opportunities
- Related content clustering

**Data Source**: `topic_clustering.py` module with embeddings

**Example Output**:
```
Title: "Topic Coverage Gap"
Description: "High-traffic queries in 'widget installation' topic cluster
             have no dedicated content. Potential: 2,500 clicks/month."
Category: opportunity
Severity: medium
```

---

### 7. CWVQualityDetector

**Purpose**: Monitor Core Web Vitals and page experience

**What It Detects**:
- Poor LCP (Largest Contentful Paint > 2.5s)
- High CLS (Cumulative Layout Shift > 0.1)
- Slow FID/INP (First Input Delay > 100ms)
- Pages with degraded CWV scores

**Data Source**: `cwv_monitor.py` module, PageSpeed API data

**Example Output**:
```
Title: "Core Web Vitals Degradation"
Description: "LCP increased from 1.8s to 3.2s on /products page.
             This may impact search rankings and user experience."
Category: risk
Severity: high
Metrics: {lcp_current: 3.2, lcp_previous: 1.8, threshold: 2.5}
```

---

### 8. CannibalizationDetector

**Purpose**: Detect keyword cannibalization between pages using embeddings

**What It Detects**:
- Pages competing for same keywords (similarity > 0.8)
- Query overlap (> 5 shared keywords)
- Ranking confusion between similar pages

**Detection Method**: Content embeddings with cosine similarity

**Data Source**: `embeddings.py` module, query data from unified view

**Example Output**:
```
Title: "Keyword Cannibalization Detected"
Description: "/blog/widget-guide and /products/widgets compete for
             12 overlapping keywords. Consolidate or differentiate."
Category: diagnosis
Severity: medium
Metrics: {similar_page: '/products/widgets', similarity: 0.87, shared_keywords: 12}
```

---

### Enhanced Detection Features

#### Prophet Forecasting in AnomalyDetector

The AnomalyDetector now uses Prophet (from `insights_core/forecasting.py`) instead of simple Z-score for anomaly detection:

```python
# Anomaly detection uses forecast-based deviation
forecaster.detect_forecast_anomaly(page_path, property, metric='gsc_clicks')

# Returns insights with:
# - expected: Prophet forecast value
# - actual: Current value
# - deviation_pct: Percentage difference from forecast
```

**Benefits**:
- Better handles seasonality
- More accurate anomaly thresholds
- Provides expected value context

#### Causal Impact Analysis in DiagnosisDetector

The DiagnosisDetector now integrates causal impact analysis (from `insights_core/causal_analyzer.py`):

```python
# Diagnosis includes causal analysis
CausalImpactAnalyzer.analyze(page_path, event_date)

# Returns insights with:
# - causal_probability: Statistical significance (0.0-1.0)
# - relative_effect_pct: Estimated causal impact
# - p_value: Statistical p-value (< 0.05 = significant)
```

#### Event Correlation Engine

For ranking changes, the DiagnosisDetector uses EventCorrelationEngine to find trigger events:

```python
# Find correlated events
correlation_engine.find_trigger_events(page_path, ranking_change_date)

# Returns correlated events:
# - content_change: Git commits, CMS updates
# - algorithm_update: Known Google updates
# - technical_issue: Performance degradation, errors
```

---

## Insight Categories & Severity

### Categories

#### RISK
**Definition**: Problems detected that need immediate attention

**Examples**:
- Traffic drop >20%
- Conversion drop >20%
- Position loss >5 spots
- Zero traffic on previously active page

**Status Flow**:
```
new → investigating → diagnosed → actioned → resolved
```

**SLA**: Investigate within 24 hours

---

#### OPPORTUNITY
**Definition**: Growth potential or optimization targets

**Examples**:
- High impressions, low CTR
- High conversion rate, low visibility
- Impression surge (+50%)

**Status Flow**:
```
new → evaluating → prioritized → implementing → completed
```

**Prioritization**: By potential impact (estimated traffic/conversion gain)

---

#### DIAGNOSIS
**Definition**: Root cause analysis of existing risks

**Examples**:
- "Drop caused by algorithm update"
- "Technical issue: 404 errors"
- "Content cannibalization detected"

**Links To**: Parent risk insight via `linked_insight_id`

**Status Flow**:
```
new → reviewing → confirmed → actioned
```

---

#### TREND
**Definition**: Long-term patterns (not necessarily problems)

**Examples**:
- Seasonal traffic pattern
- Gradual growth trend
- Volatility detection

**Status Flow**:
```
new → noted → monitoring
```

**Action**: Usually informational, monitor for changes

---

### Severity Levels

#### HIGH
**Criteria**:
- Traffic drop >50% OR
- Correlated drop (multiple metrics) OR
- Business-critical page affected

**Response Time**: Immediate (within 4 hours)

**Example**:
```
Severity: high
Page: /pricing (conversion page)
Issue: Traffic down 65% AND conversions down 58%
Impact: Lost ~$10K revenue/week
```

---

#### MEDIUM
**Criteria**:
- Traffic drop 20-50% OR
- Single metric affected OR
- Moderate potential gain

**Response Time**: Within 24 hours

**Example**:
```
Severity: medium
Page: /blog/tutorial-123
Issue: Traffic down 32%
Impact: Lost ~500 visits/week
```

---

#### LOW
**Criteria**:
- Traffic drop <20% OR
- Low-traffic page OR
- Informational trend

**Response Time**: Review weekly

**Example**:
```
Severity: low
Page: /old-blog-post
Issue: Traffic down 15%
Impact: Lost ~20 visits/week
```

---

## Detection Rules Reference

### Traffic Drop Rules

| WoW Change | Severity | Confidence | Action |
|------------|----------|------------|--------|
| -50% or more | high | 0.9 | Immediate investigation |
| -20% to -49% | medium | 0.8 | Investigate within 24h |
| -10% to -19% | low | 0.7 | Monitor, review weekly |

**Additional Factors**:
- **Volume**: Drops on high-traffic pages → higher severity
- **Recency**: Drops in last 3 days → higher urgency
- **Correlation**: Multiple metrics dropping → higher confidence

---

### Conversion Drop Rules

| WoW Change | Severity | Confidence | Action |
|------------|----------|------------|--------|
| -30% or more | high | 0.9 | Urgent investigation |
| -15% to -29% | medium | 0.8 | Investigate within 24h |
| -5% to -14% | low | 0.6 | Monitor weekly |

**Context Matters**:
```
Page with 100 conversions/week drops 20%:
→ Lost 20 conversions/week
→ HIGH severity (significant business impact)

Page with 2 conversions/week drops 50%:
→ Lost 1 conversion/week
→ LOW severity (minimal business impact)
```

---

### Opportunity Detection Rules

#### CTR Opportunity

**Formula**:
```
IF impressions > 1000
   AND ctr < industry_avg * 0.7
   AND position <= 10
THEN opportunity detected
```

**Potential Calculation**:
```python
potential_clicks = impressions * (industry_avg_ctr - current_ctr)
```

**Example**:
```
Impressions: 10,000/month
Current CTR: 2.0%
Industry Avg: 4.5%
Current Clicks: 200
Potential Clicks: 450
Gain: +250 clicks/month (+125%)
```

---

#### Ranking Opportunity

**Formula**:
```
IF conversions > 0
   AND conversion_rate > avg_site_conversion_rate
   AND position > 10
THEN ranking opportunity detected
```

**Impact Estimate**:
| Current Position | Target Position | Traffic Multiplier |
|------------------|-----------------|-------------------|
| 11-20 (page 2) | 4-6 (page 1) | 5x to 10x |
| 21-30 (page 3) | 7-10 (page 1) | 3x to 5x |
| 31+ (page 4+) | Top 10 | 2x to 4x |

---

### Threshold Configuration

**Default Thresholds** (configurable in `insights_core/config.py`):

```python
class InsightsConfig:
    # Risk thresholds (negative % change)
    risk_threshold_clicks_pct: float = -20.0
    risk_threshold_conversions_pct: float = -20.0
    risk_threshold_engagement_pct: float = -25.0

    # Opportunity thresholds (positive % change or absolute values)
    opportunity_threshold_impressions_pct: float = 50.0
    opportunity_min_impressions: int = 1000
    opportunity_target_ctr: float = 0.04  # 4%

    # Confidence thresholds
    min_confidence: float = 0.6
    high_confidence: float = 0.8

    # Volume thresholds (ignore low-traffic pages)
    min_clicks: int = 10
    min_sessions: int = 10
```

**Customization Example**:
```python
# More aggressive detection
config = InsightsConfig(
    risk_threshold_clicks_pct=-15.0,  # Detect 15% drops
    opportunity_threshold_impressions_pct=30.0  # Detect 30% surges
)

# Less noisy detection
config = InsightsConfig(
    risk_threshold_clicks_pct=-30.0,  # Only detect 30%+ drops
    min_clicks=50  # Ignore pages with <50 clicks
)
```

---

## Insight Workflow

### Status Lifecycle

```
┌───────┐  investigate   ┌──────────────┐  diagnose  ┌──────────┐
│  NEW  ├───────────────→│INVESTIGATING ├───────────→│DIAGNOSED │
└───────┘                └──────────────┘            └─────┬────┘
                                                           │
                         action taken                      │
                         ┌────────────┐                    │
                         │  ACTIONED  │←───────────────────┘
                         └──────┬─────┘
                                │
                         verify fix
                                │
                                ▼
                         ┌──────────┐
                         │ RESOLVED │
                         └──────────┘
```

### Status Definitions

**NEW**
- Insight just detected
- No action taken yet
- Appears in "Recent Insights" dashboard

**INVESTIGATING**
- Team is looking into the issue
- Gathering context
- Testing hypotheses

**DIAGNOSED**
- Root cause identified
- Action plan created
- Ready for implementation

**ACTIONED**
- Fix has been applied
- Monitoring for results
- Not yet verified

**RESOLVED**
- Fix confirmed working
- Metrics returned to normal
- Can be archived

### Updating Status

**Via API**:
```python
import requests

response = requests.patch(
    'http://localhost:8000/api/insights/abc123def456',
    json={
        'status': 'investigating',
        'description': 'Team is reviewing page changes from Nov 15'
    }
)
```

**Via SQL**:
```sql
UPDATE gsc.insights
SET status = 'investigating',
    updated_at = CURRENT_TIMESTAMP
WHERE id = 'abc123def456';
```

**Via Dashboard** (if enabled):
Click insight → Change status dropdown → Save

---

## Using Insights

### Daily Routine

**Morning Check (5 minutes)**:
```sql
-- High-priority new insights
SELECT
    entity_id as page,
    title,
    description,
    severity
FROM gsc.insights
WHERE status = 'new'
  AND severity IN ('high', 'medium')
  AND generated_at >= CURRENT_DATE - INTERVAL '1 day'
ORDER BY
    CASE severity
        WHEN 'high' THEN 1
        WHEN 'medium' THEN 2
        ELSE 3
    END,
    generated_at DESC;
```

**Actions**:
1. Mark high-severity as "investigating"
2. Assign to team members
3. Create tasks in project management tool

---

### Weekly Review (30 minutes)

**Opportunity Prioritization**:
```sql
-- Top opportunities by potential impact
SELECT
    entity_id as page,
    title,
    description,
    metrics->>'potential_clicks' as potential_gain
FROM gsc.insights
WHERE category = 'opportunity'
  AND status IN ('new', 'evaluating')
ORDER BY (metrics->>'potential_clicks')::numeric DESC
LIMIT 10;
```

**Actions**:
1. Prioritize top 3 opportunities
2. Assign to content/SEO team
3. Set target completion dates

---

### Monthly Analysis (2 hours)

**Impact Assessment**:
```sql
-- Resolved insights this month
SELECT
    category,
    severity,
    COUNT(*) as resolved_count,
    AVG(EXTRACT(EPOCH FROM (updated_at - generated_at))/86400) as avg_days_to_resolve
FROM gsc.insights
WHERE status = 'resolved'
  AND updated_at >= DATE_TRUNC('month', CURRENT_DATE)
GROUP BY category, severity;
```

**Review**:
1. Calculate ROI of fixes
2. Identify recurring issues
3. Refine detection thresholds

---

### Integration with Workflow Tools

#### Slack Notifications

```python
from insights_core.channels.slack import SlackChannel

slack = SlackChannel(webhook_url=config.slack_webhook)

# Send high-severity insights
for insight in high_priority_insights:
    slack.send_insight(insight)
```

#### Jira Ticket Creation

```python
from insights_core.channels.jira import JiraChannel

jira = JiraChannel(
    url=config.jira_url,
    token=config.jira_token
)

# Create ticket for each high-severity insight
for insight in insights:
    if insight.severity == InsightSeverity.HIGH:
        ticket = jira.create_ticket(
            project='SEO',
            summary=insight.title,
            description=insight.description,
            priority='High'
        )
```

---

## Configuration & Tuning

### Adjusting Detection Sensitivity

**Problem**: Too many false positives

**Solution**: Increase thresholds
```python
config = InsightsConfig(
    risk_threshold_clicks_pct=-30.0,  # Was -20
    min_clicks=100,  # Was 10
    min_confidence=0.8  # Was 0.6
)
```

**Problem**: Missing important issues

**Solution**: Decrease thresholds
```python
config = InsightsConfig(
    risk_threshold_clicks_pct=-15.0,  # Was -20
    min_confidence=0.5  # Was 0.6
)
```

---

### Custom Detectors

**Create Your Own Detector**:

```python
from insights_core.detectors.base import BaseDetector
from insights_core.models import InsightCreate, InsightCategory

class CustomDetector(BaseDetector):
    """Detect custom business-specific patterns"""

    def detect(self, property: str = None) -> int:
        # 1. Query data
        conn = self._get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT *
            FROM gsc.vw_unified_page_performance
            WHERE <your custom logic>
        """)

        # 2. Analyze and create insights
        insights_created = 0
        for row in cur.fetchall():
            if self._meets_criteria(row):
                insight = InsightCreate(
                    property=row['property'],
                    entity_type=EntityType.PAGE,
                    entity_id=row['page_path'],
                    category=InsightCategory.OPPORTUNITY,
                    title="Custom Pattern Detected",
                    description="Your custom description",
                    severity=InsightSeverity.MEDIUM,
                    confidence=0.75,
                    metrics=InsightMetrics(...),
                    window_days=7,
                    source="CustomDetector"
                )

                self.repository.create(insight)
                insights_created += 1

        return insights_created

    def _meets_criteria(self, row: dict) -> bool:
        # Your custom logic
        return True
```

**Register Detector**:
```python
# insights_core/engine.py
from insights_core.detectors.custom import CustomDetector

self.detectors = [
    AnomalyDetector(self.repository, self.config),
    DiagnosisDetector(self.repository, self.config),
    OpportunityDetector(self.repository, self.config),
    CustomDetector(self.repository, self.config),  # Add here
]
```

---

## API Reference

### Refresh Insights

**Endpoint**: `POST /insights/refresh`

**Parameters**:
- `property` (optional): Filter by property

**Example**:
```bash
curl -X POST http://localhost:8000/api/insights/refresh \
  -H "Content-Type: application/json" \
  -d '{"property": "https://example.com/"}'
```

**Response**:
```json
{
  "status": "completed",
  "stats": {
    "total_insights_created": 42,
    "insights_by_detector": {
      "AnomalyDetector": 15,
      "DiagnosisDetector": 10,
      "OpportunityDetector": 17
    },
    "duration_seconds": 12.34
  }
}
```

---

### Query Insights

**Endpoint**: `GET /insights`

**Parameters**:
- `property` (optional)
- `category` (optional): risk, opportunity, diagnosis, trend
- `status` (optional): new, investigating, diagnosed, actioned, resolved
- `severity` (optional): low, medium, high
- `limit` (optional): default 100, max 1000
- `offset` (optional): for pagination

**Example**:
```bash
curl "http://localhost:8000/api/insights?category=risk&severity=high&status=new"
```

**Response**:
```json
[
  {
    "id": "abc123def456...",
    "property": "https://example.com/",
    "entity_type": "page",
    "entity_id": "/blog/post-123",
    "category": "risk",
    "title": "Traffic & Conversion Drop",
    "description": "Clicks down 45%, conversions down 32%",
    "severity": "high",
    "confidence": 0.9,
    "metrics": {
      "gsc_clicks": 234,
      "gsc_clicks_change": -45.2,
      "ga_conversions": 12,
      "ga_conversions_change": -32.1
    },
    "window_days": 7,
    "source": "AnomalyDetector",
    "status": "new",
    "generated_at": "2024-11-20T08:23:15Z",
    "created_at": "2024-11-20T08:23:15Z",
    "updated_at": "2024-11-20T08:23:15Z"
  }
]
```

---

### Update Insight

**Endpoint**: `PATCH /insights/{insight_id}`

**Body**:
```json
{
  "status": "investigating",
  "description": "Updated description with investigation notes"
}
```

**Example**:
```bash
curl -X PATCH http://localhost:8000/api/insights/abc123def456 \
  -H "Content-Type: application/json" \
  -d '{"status": "investigating"}'
```

---

## Troubleshooting

### No Insights Being Created

**Check 1: Data Exists**
```sql
SELECT COUNT(*) FROM gsc.vw_unified_page_performance
WHERE date >= CURRENT_DATE - INTERVAL '7 days';
-- Should be > 0
```

**Check 2: WoW Calculations Populated**
```sql
SELECT COUNT(*) FROM gsc.vw_unified_page_performance
WHERE gsc_clicks_change_wow IS NOT NULL;
-- Need at least 7 days of data
```

**Check 3: Threshold Too High**
```python
# Try lower threshold temporarily
config = InsightsConfig(risk_threshold_clicks_pct=-10.0)
```

**Check 4: Engine Running**
```bash
docker compose logs insights_engine | tail -50
```

---

### Too Many False Positives

**Solution 1: Increase Minimum Volume**
```python
config = InsightsConfig(
    min_clicks=50,  # Ignore pages with <50 clicks
    min_sessions=50
)
```

**Solution 2: Increase Confidence Threshold**
```python
config = InsightsConfig(
    min_confidence=0.8  # Only high-confidence insights
)
```

**Solution 3: Longer Detection Window**
```sql
-- Compare 28-day averages instead of WoW
WHERE gsc_clicks_28d_avg IS NOT NULL
  AND (gsc_clicks - gsc_clicks_28d_avg) / gsc_clicks_28d_avg < -0.3
```

---

### Insights Not Updating

**Check**: ON CONFLICT behavior
```sql
-- Manual test
INSERT INTO gsc.insights (id, ...) VALUES (...)
ON CONFLICT (id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP;
```

**Solution**: Verify deterministic ID generation
```python
# Same parameters should produce same ID
id1 = Insight.generate_id("prop", "page", "/path", "risk", "source", 7)
id2 = Insight.generate_id("prop", "page", "/path", "risk", "source", 7)
assert id1 == id2
```

---

**Document Version**: 1.0
**Last Updated**: 2025
**Next Review**: Q2 2025

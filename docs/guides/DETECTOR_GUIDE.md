# Writing Custom Detectors
## Guide to Extending the Insight Engine

---

## Overview

Detectors are the "intelligence" of the Hybrid Plan. They analyze the unified view and generate insights.

### Detector Pattern

```python
from insights_core.detectors.base import BaseDetector
from insights_core.models import InsightCreate, InsightCategory

class MyDetector(BaseDetector):
    """
    My custom detector
    
    Rules:
    - Rule 1 description
    - Rule 2 description
    """
    
    def detect(self, property: str = None) -> int:
        """
        Run detection logic
        
        Returns: Number of insights created
        """
        conn = self._get_db_connection()
        insights_created = 0
        
        try:
            # 1. Query unified view
            rows = self._query_unified_view(property)
            
            # 2. Analyze each row
            for row in rows:
                insights = self._analyze_row(row)
                
                # 3. Persist insights
                for insight in insights:
                    self.repository.create(insight)
                    insights_created += 1
            
            return insights_created
        finally:
            conn.close()
    
    def _query_unified_view(self, property):
        # Your SQL query here
        pass
    
    def _analyze_row(self, row):
        # Your detection logic here
        pass
```

---

## Step-by-Step Example

### Scenario: Detect "Ranking Drop Without Click Loss"

**Business Rule:** Page dropped 5+ positions but clicks unchanged → opportunity to investigate competitors.

### Step 1: Create Detector File

```python
# insights_core/detectors/ranking_drop.py

from insights_core.detectors.base import BaseDetector
from insights_core.models import (
    InsightCreate, InsightCategory, InsightSeverity, 
    EntityType, InsightMetrics
)
from typing import List
from datetime import timedelta

class RankingDropDetector(BaseDetector):
    """
    Detects pages with significant ranking drops without corresponding click loss
    
    Rules:
    - Position dropped >5 places WoW
    - Clicks change within ±10% (minimal impact)
    - Impressions maintained or increased
    
    Insight: Competitors may have gained ground; investigate SERPs
    """
    
    def detect(self, property: str = None) -> int:
        conn = self._get_db_connection()
        insights_created = 0
        
        try:
            from psycopg2.extras import RealDictCursor
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT DISTINCT ON (property, page_path)
                        property,
                        page_path,
                        date,
                        gsc_clicks,
                        gsc_clicks_change_wow,
                        gsc_impressions,
                        gsc_impressions_change_wow,
                        gsc_position,
                        gsc_position_change_wow
                    FROM gsc.vw_unified_page_performance
                    WHERE date >= CURRENT_DATE - INTERVAL '7 days'
                        AND gsc_position_change_wow > 5  -- Dropped 5+ positions
                        AND ABS(gsc_clicks_change_wow) < 10  -- Clicks stable
                        AND gsc_impressions_change_wow >= 0  -- Impressions maintained
                """
                
                if property:
                    query += " AND property = %s"
                    cur.execute(query, (property,))
                else:
                    cur.execute(query)
                
                rows = cur.fetchall()
            
            for row in rows:
                insights = self._analyze_row(dict(row))
                for insight in insights:
                    self.repository.create(insight)
                    insights_created += 1
            
            return insights_created
        finally:
            conn.close()
    
    def _analyze_row(self, row: dict) -> List[InsightCreate]:
        """Generate insight for ranking drop"""
        
        # Calculate window
        row_date = row['date']
        window_start = (row_date - timedelta(days=7)).isoformat()
        window_end = row_date.isoformat()
        
        insight = InsightCreate(
            property=row['property'],
            entity_type=EntityType.PAGE,
            entity_id=row['page_path'],
            category=InsightCategory.TREND,
            title="Ranking Drop Without Click Impact",
            description=(
                f"Page position dropped by {row['gsc_position_change_wow']:.1f} places "
                f"but clicks remained stable ({row['gsc_clicks_change_wow']:+.1f}%). "
                f"This suggests competitors may have improved or Google algorithm shifted. "
                f"Investigate SERP changes and competitor content."
            ),
            severity=InsightSeverity.MEDIUM,
            confidence=0.75,
            metrics=InsightMetrics(
                gsc_position=row['gsc_position'],
                gsc_position_change=row['gsc_position_change_wow'],
                gsc_clicks=row['gsc_clicks'],
                gsc_clicks_change=row['gsc_clicks_change_wow'],
                gsc_impressions=row['gsc_impressions'],
                window_start=window_start,
                window_end=window_end
            ),
            window_days=7,
            source="RankingDropDetector"
        )
        
        return [insight]
```

### Step 2: Register Detector

```python
# insights_core/engine.py

from insights_core.detectors import (
    AnomalyDetector,
    DiagnosisDetector,
    OpportunityDetector,
)
from insights_core.detectors.ranking_drop import RankingDropDetector  # ← Add import

class InsightEngine:
    def __init__(self, config: InsightsConfig = None):
        self.detectors = [
            AnomalyDetector(self.repository, self.config),
            DiagnosisDetector(self.repository, self.config),
            OpportunityDetector(self.repository, self.config),
            RankingDropDetector(self.repository, self.config),  # ← Add here
        ]
```

### Step 3: Test Detector

```python
# tests/test_ranking_drop_detector.py

import pytest
from insights_core.detectors.ranking_drop import RankingDropDetector
from insights_core.repository import InsightRepository
from insights_core.config import InsightsConfig

def test_ranking_drop_detector(test_db_connection):
    """Test ranking drop detection"""
    
    # Setup
    repo = InsightRepository(test_db_connection)
    config = InsightsConfig()
    detector = RankingDropDetector(repo, config)
    
    # Insert test data
    test_db_connection.execute("""
        INSERT INTO gsc.vw_unified_page_performance (...)
        VALUES (...);  -- Data with position drop
    """)
    
    # Run detector
    insights_created = detector.detect()
    
    # Verify
    assert insights_created > 0
    insights = repo.query(category=InsightCategory.TREND, limit=10)
    assert len(insights) > 0
    assert "Ranking Drop" in insights[0].title
```

---

## Best Practices

### 1. Always Query Unified View

```python
# ✅ CORRECT (Hybrid Plan)
query = """
    SELECT * FROM gsc.vw_unified_page_performance
    WHERE ...
"""

# ❌ WRONG (Breaks hybrid architecture)
query = """
    SELECT * FROM gsc.fact_gsc_daily
    WHERE ...
"""
```

### 2. Use Time-Series Fields

```python
# ✅ GOOD: Use pre-calculated WoW
WHERE gsc_clicks_change_wow < -20

# ❌ BAD: Calculate yourself (slow, error-prone)
WHERE ((clicks - LAG(clicks, 7)) / LAG(clicks, 7)) * 100 < -20
```

### 3. Set Appropriate Severity

```python
# High severity: Immediate business impact
severity=InsightSeverity.HIGH
# Example: Revenue-generating page lost 50% traffic

# Medium severity: Important but not critical
severity=InsightSeverity.MEDIUM
# Example: Position drop without click loss

# Low severity: Informational
severity=InsightSeverity.LOW
# Example: Slight CTR improvement
```

### 4. Provide Actionable Descriptions

```python
# ✅ GOOD: Specific, actionable
description=(
    f"Page dropped 8 positions (now position {position}). "
    f"Investigate competitors and update content to regain rankings."
)

# ❌ BAD: Vague
description="Ranking dropped"
```

### 5. Use Appropriate Confidence

```python
# High confidence: Statistical significance
confidence=0.9
# Example: 45% drop with 1000+ clicks/day

# Medium confidence: Likely but uncertain
confidence=0.75
# Example: Pattern detected but low traffic

# Low confidence: Speculative
confidence=0.5
# Example: Weak signal, requires investigation
```

---

## Advanced Patterns

### Pattern 1: Multi-Stage Detection

```python
def detect(self, property: str = None) -> int:
    # Stage 1: Find candidates
    candidates = self._find_candidates(property)
    
    # Stage 2: Apply complex rules
    filtered = self._apply_rules(candidates)
    
    # Stage 3: Enrich with external data
    enriched = self._enrich_with_cms_data(filtered)
    
    # Stage 4: Generate insights
    return self._create_insights(enriched)
```

### Pattern 2: Linked Insights

```python
# Create parent insight
parent_insight = InsightCreate(
    category=InsightCategory.RISK,
    title="Traffic Drop",
    ...
)
parent = self.repository.create(parent_insight)

# Create child diagnosis
diagnosis = InsightCreate(
    category=InsightCategory.DIAGNOSIS,
    title="Root Cause: CMS Update",
    linked_insight_id=parent.id,  # ← Link to parent
    ...
)
```

### Pattern 3: Confidence Scoring

```python
def _calculate_confidence(self, row: dict) -> float:
    """Dynamic confidence based on data quality"""
    
    confidence = 0.5  # Base confidence
    
    # Boost for high traffic
    if row['gsc_clicks'] > 1000:
        confidence += 0.2
    
    # Boost for consistent trend
    if row['gsc_clicks_7d_avg'] < row['gsc_clicks_28d_avg']:
        confidence += 0.1
    
    # Boost for correlated GA4 data
    if row['ga_conversions_change_wow'] < -15:
        confidence += 0.1
    
    return min(confidence, 1.0)
```

---

## Configuration

### Add Detector-Specific Config

```python
# insights_core/config.py

class InsightsConfig:
    # Existing config
    risk_threshold_clicks_pct: float = -20
    
    # Add your detector config
    ranking_drop_threshold_positions: int = 5
    ranking_drop_click_tolerance_pct: float = 10
```

Use in detector:
```python
def detect(self, property: str = None) -> int:
    threshold = self.config.ranking_drop_threshold_positions
    tolerance = self.config.ranking_drop_click_tolerance_pct
    
    query = f"""
        WHERE gsc_position_change_wow > {threshold}
            AND ABS(gsc_clicks_change_wow) < {tolerance}
    """
```

---

## Testing

### Unit Test Template

```python
def test_my_detector():
    # Setup
    detector = MyDetector(mock_repo, mock_config)
    
    # Insert test data
    # ...
    
    # Run
    count = detector.detect()
    
    # Assert
    assert count > 0
    insights = mock_repo.query()
    assert insights[0].category == InsightCategory.OPPORTUNITY
```

### Integration Test Template

```python
def test_my_detector_integration(real_db):
    # Use real database with real data
    detector = MyDetector(real_repo, real_config)
    
    # Run
    count = detector.detect()
    
    # Verify in database
    result = real_db.execute("""
        SELECT * FROM gsc.insights
        WHERE source = 'MyDetector'
    """)
    assert len(result) > 0
```

---

## Troubleshooting

### Detector Creates No Insights

**Possible causes:**
1. No anomalies in data (expected if stable)
2. Thresholds too strict
3. Not enough historical data

**Debug:**
```python
# Add logging
import logging
logger = logging.getLogger(__name__)

def detect(self, property: str = None) -> int:
    rows = self._query_unified_view(property)
    logger.info(f"Found {len(rows)} candidate rows")
    
    for i, row in enumerate(rows):
        insights = self._analyze_row(row)
        logger.debug(f"Row {i}: Generated {len(insights)} insights")
```

### Detector Too Slow

**Optimize query:**
```python
# ✅ GOOD: Filter early
query = """
    SELECT * FROM gsc.vw_unified_page_performance
    WHERE date >= CURRENT_DATE - INTERVAL '7 days'
        AND property = %s
        AND gsc_clicks > 100  -- Filter low-traffic pages
"""

# ❌ BAD: Filter after loading
query = "SELECT * FROM gsc.vw_unified_page_performance"
rows = [r for r in all_rows if r['gsc_clicks'] > 100]
```

---

## Examples Repository

See `insights_core/detectors/` for production examples:
- `anomaly.py` - Traffic/conversion drops
- `diagnosis.py` - Root cause analysis
- `opportunity.py` - Growth opportunities

---

**Next Steps:**
- [Understand unified view](UNIFIED_VIEW_GUIDE.md)
- [Deploy detector](../deployment/PRODUCTION_GUIDE.md)
- [Monitor insights](../runbooks/MONITORING.md)

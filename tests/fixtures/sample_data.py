"""
Sample data generators for test fixtures.

Provides functions to generate realistic test data that matches production schema.
All generators use random.seed(42) for deterministic, reproducible data.

Usage:
    >>> from tests.fixtures.sample_data import generate_gsc_data
    >>> gsc_rows = generate_gsc_data(num_rows=100)
    >>> assert len(gsc_rows) == 100
"""

import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from insights_core.models import (
    EntityType,
    Insight,
    InsightCategory,
    InsightCreate,
    InsightMetrics,
    InsightSeverity,
    InsightStatus,
)

# Seed for deterministic data generation
RANDOM_SEED = 42


def reset_seed() -> None:
    """Reset random seed to ensure deterministic test data."""
    random.seed(RANDOM_SEED)


# Sample data pools for realistic variation
SAMPLE_PROPERTIES = [
    "https://example.com/",
    "https://blog.example.com/",
    "sc-domain:example.net",
]

SAMPLE_PAGES = [
    "/",
    "/about",
    "/blog/python-tutorial",
    "/blog/javascript-guide",
    "/products/widget-pro",
    "/products/widget-lite",
    "/docs/getting-started",
    "/docs/api-reference",
    "/pricing",
    "/contact",
]

SAMPLE_QUERIES = [
    "python tutorial",
    "javascript guide",
    "best widget software",
    "widget pro vs lite",
    "how to use widget",
    "widget api documentation",
    "widget pricing",
    "widget support",
    "widget alternatives",
    "widget reviews",
]

SAMPLE_COUNTRIES = ["USA", "GBR", "CAN", "AUS", "DEU", "FRA", "JPN"]
SAMPLE_DEVICES = ["DESKTOP", "MOBILE", "TABLET"]


def generate_gsc_data(
    num_rows: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    property_url: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Generate GSC fact table data matching gsc.fact_gsc_daily schema.

    Args:
        num_rows: Number of rows to generate
        start_date: Start date for data (defaults to 30 days ago)
        end_date: End date for data (defaults to today)
        property_url: Specific property to use (or random if None)

    Returns:
        List of dictionaries with GSC data
    """
    reset_seed()

    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    rows = []
    date_range = (end_date - start_date).days + 1

    for _ in range(num_rows):
        days_offset = random.randint(0, date_range - 1)
        row_date = start_date + timedelta(days=days_offset)

        # Generate realistic metric correlations
        position = random.uniform(1.0, 50.0)
        # Better positions typically have higher CTR
        base_ctr = max(0.01, 0.2 - (position * 0.003))
        ctr = random.uniform(base_ctr * 0.5, base_ctr * 1.5)
        impressions = random.randint(10, 10000)
        clicks = int(impressions * ctr)

        rows.append(
            {
                "date": row_date,
                "property": property_url or random.choice(SAMPLE_PROPERTIES),
                "url": random.choice(SAMPLE_PAGES),
                "query": random.choice(SAMPLE_QUERIES),
                "country": random.choice(SAMPLE_COUNTRIES),
                "device": random.choice(SAMPLE_DEVICES),
                "clicks": clicks,
                "impressions": impressions,
                "ctr": round(ctr, 6),
                "position": round(position, 2),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )

    return rows


def generate_ga4_data(
    num_rows: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    property_url: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Generate GA4 fact table data matching gsc.fact_ga4_daily schema.

    Args:
        num_rows: Number of rows to generate
        start_date: Start date for data
        end_date: End date for data
        property_url: Specific property to use

    Returns:
        List of dictionaries with GA4 data
    """
    reset_seed()

    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    rows = []
    date_range = (end_date - start_date).days + 1

    for _ in range(num_rows):
        days_offset = random.randint(0, date_range - 1)
        row_date = start_date + timedelta(days=days_offset)

        # Generate realistic GA4 metrics with correlations
        sessions = random.randint(10, 5000)
        engagement_rate = random.uniform(0.3, 0.8)
        engaged_sessions = int(sessions * engagement_rate)
        bounce_rate = random.uniform(0.2, 0.7)
        conversions = int(sessions * random.uniform(0.01, 0.05))
        conversion_rate = conversions / sessions if sessions > 0 else 0
        page_views = int(sessions * random.uniform(1.5, 3.0))
        avg_session_duration = random.uniform(30, 300)
        avg_time_on_page = random.uniform(20, 200)

        rows.append(
            {
                "date": row_date,
                "property": property_url or random.choice(SAMPLE_PROPERTIES),
                "page_path": random.choice(SAMPLE_PAGES),
                "sessions": sessions,
                "engaged_sessions": engaged_sessions,
                "engagement_rate": round(engagement_rate, 4),
                "bounce_rate": round(bounce_rate, 4),
                "conversions": conversions,
                "conversion_rate": round(conversion_rate, 4),
                "avg_session_duration": round(avg_session_duration, 2),
                "page_views": page_views,
                "avg_time_on_page": round(avg_time_on_page, 2),
                "exits": 0,  # Optional field
                "exit_rate": 0.0,  # Optional field
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )

    return rows


def generate_anomaly_scenario(
    scenario_type: str,
    baseline_value: float = 100.0,
    days: int = 30,
) -> List[Tuple[date, float]]:
    """
    Generate time series data for different anomaly scenarios.

    Args:
        scenario_type: Type of anomaly (normal, spike, drop, gradual_decline, seasonal)
        baseline_value: Baseline metric value
        days: Number of days to generate

    Returns:
        List of (date, value) tuples
    """
    reset_seed()

    start_date = date.today() - timedelta(days=days)
    data = []

    for i in range(days):
        current_date = start_date + timedelta(days=i)
        noise = random.uniform(-5, 5)  # Random noise ±5%

        if scenario_type == "normal":
            value = baseline_value + noise

        elif scenario_type == "spike":
            # Spike on day 20
            if i == 20:
                value = baseline_value * 2.5 + noise
            else:
                value = baseline_value + noise

        elif scenario_type == "drop":
            # Sudden drop on day 20
            if i >= 20:
                value = baseline_value * 0.5 + noise
            else:
                value = baseline_value + noise

        elif scenario_type == "gradual_decline":
            # Linear decline over time
            decline_rate = baseline_value * 0.02  # 2% per day
            value = baseline_value - (i * decline_rate) + noise

        elif scenario_type == "seasonal":
            # Weekly seasonality (higher on weekdays)
            day_of_week = current_date.weekday()
            if day_of_week < 5:  # Monday-Friday
                value = baseline_value * 1.2 + noise
            else:  # Weekend
                value = baseline_value * 0.8 + noise

        else:
            raise ValueError(f"Unknown scenario_type: {scenario_type}")

        data.append((current_date, max(0, value)))  # Ensure non-negative

    return data


def generate_cannibalization_data(
    num_pages: int = 5,
    overlapping_queries: int = 3,
) -> Dict[str, Any]:
    """
    Generate data showing keyword cannibalization scenario.

    Args:
        num_pages: Number of competing pages
        overlapping_queries: Number of overlapping keywords

    Returns:
        Dictionary with cannibalization data structure
    """
    reset_seed()

    pages = random.sample(SAMPLE_PAGES, min(num_pages, len(SAMPLE_PAGES)))
    queries = random.sample(SAMPLE_QUERIES, min(overlapping_queries, len(SAMPLE_QUERIES)))

    data = {
        "property": random.choice(SAMPLE_PROPERTIES),
        "queries": queries,
        "pages": pages,
        "overlaps": [],
    }

    for query in queries:
        for page in pages:
            # Each page ranks for the query at different positions
            data["overlaps"].append(
                {
                    "query": query,
                    "page": page,
                    "position": random.uniform(5.0, 30.0),
                    "clicks": random.randint(10, 500),
                    "impressions": random.randint(100, 5000),
                }
            )

    return data


def generate_content_quality_metrics(
    quality_level: str = "normal",
) -> Dict[str, Any]:
    """
    Generate content quality metrics for different quality levels.

    Args:
        quality_level: Quality level (thin, high_bounce, stale, normal, good)

    Returns:
        Dictionary with content quality metrics
    """
    reset_seed()

    if quality_level == "thin":
        return {
            "word_count": random.randint(50, 200),
            "bounce_rate": random.uniform(0.7, 0.9),
            "avg_time_on_page": random.uniform(5, 20),
            "page_views": random.randint(5, 50),
        }

    elif quality_level == "high_bounce":
        return {
            "word_count": random.randint(500, 1000),
            "bounce_rate": random.uniform(0.8, 0.95),
            "avg_time_on_page": random.uniform(10, 30),
            "page_views": random.randint(100, 500),
        }

    elif quality_level == "stale":
        return {
            "word_count": random.randint(800, 1500),
            "bounce_rate": random.uniform(0.5, 0.7),
            "avg_time_on_page": random.uniform(60, 120),
            "page_views": random.randint(10, 100),
            "last_modified": datetime.utcnow() - timedelta(days=random.randint(365, 730)),
        }

    elif quality_level == "good":
        return {
            "word_count": random.randint(1500, 3000),
            "bounce_rate": random.uniform(0.2, 0.4),
            "avg_time_on_page": random.uniform(120, 300),
            "page_views": random.randint(500, 5000),
        }

    else:  # normal
        return {
            "word_count": random.randint(800, 1200),
            "bounce_rate": random.uniform(0.4, 0.6),
            "avg_time_on_page": random.uniform(60, 120),
            "page_views": random.randint(100, 1000),
        }


def generate_cwv_metrics(
    assessment: str = "good",
    strategy: str = "mobile",
) -> Dict[str, Any]:
    """
    Generate Core Web Vitals metrics matching performance.core_web_vitals schema.

    Args:
        assessment: CWV assessment (good, needs_improvement, poor)
        strategy: Device strategy (mobile, desktop)

    Returns:
        Dictionary with CWV metrics
    """
    reset_seed()

    if assessment == "good":
        lcp = random.uniform(1000, 2400)  # Good: <2500ms
        fid = random.uniform(10, 90)  # Good: <100ms
        cls = random.uniform(0.01, 0.09)  # Good: <0.1
        performance_score = random.randint(90, 100)

    elif assessment == "needs_improvement":
        lcp = random.uniform(2500, 3800)  # Needs improvement: 2500-4000ms
        fid = random.uniform(100, 280)  # Needs improvement: 100-300ms
        cls = random.uniform(0.1, 0.24)  # Needs improvement: 0.1-0.25
        performance_score = random.randint(50, 89)

    else:  # poor
        lcp = random.uniform(4000, 8000)  # Poor: >4000ms
        fid = random.uniform(300, 600)  # Poor: >300ms
        cls = random.uniform(0.25, 0.6)  # Poor: >0.25
        performance_score = random.randint(0, 49)

    return {
        "property": random.choice(SAMPLE_PROPERTIES),
        "page_path": random.choice(SAMPLE_PAGES),
        "check_date": date.today(),
        "strategy": strategy,
        "lcp": round(lcp, 2),
        "fid": round(fid, 2),
        "cls": round(cls, 3),
        "fcp": round(random.uniform(800, 3000), 2),
        "inp": round(random.uniform(100, 500), 2),
        "ttfb": round(random.uniform(200, 1500), 2),
        "performance_score": performance_score,
        "accessibility_score": random.randint(70, 100),
        "best_practices_score": random.randint(70, 100),
        "seo_score": random.randint(70, 100),
        "cwv_assessment": assessment,
        "created_at": datetime.utcnow(),
    }


def generate_trend_data(
    trend_type: str,
    baseline: float = 100.0,
    days: int = 30,
) -> List[Tuple[date, float]]:
    """
    Generate trend data for different trend types.

    Args:
        trend_type: Type of trend (upward, downward, stable, volatile, seasonal)
        baseline: Baseline value
        days: Number of days

    Returns:
        List of (date, value) tuples
    """
    reset_seed()

    start_date = date.today() - timedelta(days=days)
    data = []

    for i in range(days):
        current_date = start_date + timedelta(days=i)
        noise = random.uniform(-2, 2)

        if trend_type == "upward":
            # Steady growth
            growth_rate = baseline * 0.03  # 3% per day
            value = baseline + (i * growth_rate) + noise

        elif trend_type == "downward":
            # Steady decline
            decline_rate = baseline * 0.02  # 2% per day
            value = baseline - (i * decline_rate) + noise

        elif trend_type == "stable":
            # Flat with minimal noise
            value = baseline + noise

        elif trend_type == "volatile":
            # High variance
            value = baseline + random.uniform(-30, 30)

        elif trend_type == "seasonal":
            # Weekly pattern
            day_of_week = current_date.weekday()
            if day_of_week < 5:  # Weekday
                value = baseline * 1.3 + noise
            else:  # Weekend
                value = baseline * 0.7 + noise

        else:
            raise ValueError(f"Unknown trend_type: {trend_type}")

        data.append((current_date, max(0, value)))

    return data


def generate_insight(
    category: InsightCategory = InsightCategory.RISK,
    severity: InsightSeverity = InsightSeverity.MEDIUM,
    entity_type: EntityType = EntityType.PAGE,
    property_url: Optional[str] = None,
) -> InsightCreate:
    """
    Generate a sample InsightCreate object.

    Args:
        category: Insight category
        severity: Insight severity
        entity_type: Entity type
        property_url: Property URL (or random)

    Returns:
        InsightCreate object
    """
    reset_seed()

    if not property_url:
        property_url = random.choice(SAMPLE_PROPERTIES)

    entity_id = random.choice(SAMPLE_PAGES) if entity_type == EntityType.PAGE else random.choice(SAMPLE_QUERIES)

    metrics = InsightMetrics(
        gsc_clicks=random.uniform(50, 500),
        gsc_clicks_change=random.uniform(-50, 50),
        gsc_impressions=random.uniform(500, 5000),
        gsc_position=random.uniform(1, 20),
        window_start=(date.today() - timedelta(days=7)).isoformat(),
        window_end=date.today().isoformat(),
    )

    return InsightCreate(
        property=property_url,
        entity_type=entity_type,
        entity_id=entity_id,
        category=category,
        title=f"Sample {category.value} insight",
        description=f"This is a test {category.value} insight with {severity.value} severity.",
        severity=severity,
        confidence=random.uniform(0.7, 0.95),
        metrics=metrics,
        window_days=7,
        source="TestDataGenerator",
    )


def generate_insights_batch(
    count: int = 10,
    categories: Optional[List[InsightCategory]] = None,
) -> List[InsightCreate]:
    """
    Generate a batch of insights with varied characteristics.

    Args:
        count: Number of insights to generate
        categories: List of categories to use (or all if None)

    Returns:
        List of InsightCreate objects
    """
    reset_seed()

    if not categories:
        categories = list(InsightCategory)

    insights = []
    severities = list(InsightSeverity)
    entity_types = list(EntityType)

    for _ in range(count):
        insights.append(
            generate_insight(
                category=random.choice(categories),
                severity=random.choice(severities),
                entity_type=random.choice(entity_types),
            )
        )

    return insights


def generate_time_series_for_forecasting(
    metric: str = "gsc_clicks",
    days: int = 90,
    include_anomaly: bool = False,
    anomaly_day: int = 80,
) -> List[Dict[str, Any]]:
    """
    Generate time series data suitable for Prophet forecasting tests.

    Args:
        metric: Metric name
        days: Number of days
        include_anomaly: Whether to include an anomaly
        anomaly_day: Day index for anomaly (if included)

    Returns:
        List of dicts with 'ds' (date) and 'y' (value) keys (Prophet format)
    """
    reset_seed()

    start_date = date.today() - timedelta(days=days)
    data = []

    for i in range(days):
        current_date = start_date + timedelta(days=i)

        # Base value with weekly seasonality
        day_of_week = current_date.weekday()
        base_value = 100.0

        # Weekday boost
        if day_of_week < 5:
            base_value *= 1.2
        else:
            base_value *= 0.8

        # Add trend
        trend = i * 0.5

        # Add noise
        noise = random.uniform(-5, 5)

        value = base_value + trend + noise

        # Inject anomaly
        if include_anomaly and i == anomaly_day:
            value *= 0.5  # 50% drop

        data.append({"ds": current_date, "y": max(0, value)})

    return data


def generate_path_variations(base_path: str = "/blog/article") -> List[str]:
    """
    Generate URL path variations for URL consolidation testing.

    Args:
        base_path: Base path to create variations from

    Returns:
        List of URL variations
    """
    reset_seed()

    variations = [
        base_path,
        f"{base_path}/",
        f"{base_path}?utm_source=google",
        f"{base_path}?ref=twitter",
        f"{base_path}#section-1",
        f"{base_path}/?page=1",
        f"{base_path}/index.html",
    ]

    return variations

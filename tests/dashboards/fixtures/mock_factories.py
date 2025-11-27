"""
Mock data factories for unit tests
Generates realistic test data without database connection

Usage:
    from tests.dashboards.fixtures.mock_factories import GSCDataFactory, GA4DataFactory

    # Generate mock GSC data
    gsc_data = GSCDataFactory.create_daily_metrics(days=30)

    # Generate mock GA4 data
    ga4_data = GA4DataFactory.create_daily_metrics(days=30)
"""

import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional


class GSCDataFactory:
    """Factory for generating mock GSC data"""

    @staticmethod
    def create_daily_metrics(
        days: int = 30,
        property_url: str = "https://test-domain.com",
        page_path: str = "/test-page",
        base_clicks: int = 100,
        base_impressions: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Generate daily GSC metrics.

        Args:
            days: Number of days to generate
            property_url: Property URL
            page_path: Page path
            base_clicks: Base click count
            base_impressions: Base impression count

        Returns:
            List of daily metric dictionaries
        """
        data = []

        for i in range(days):
            date = datetime.now().date() - timedelta(days=i)
            variance = random.uniform(0.8, 1.2)

            clicks = int(base_clicks * variance)
            impressions = int(base_impressions * variance)

            data.append({
                "date": date.isoformat(),
                "property": property_url,
                "url": f"{property_url}{page_path}",
                "page_path": page_path,
                "clicks": clicks,
                "impressions": impressions,
                "ctr": round(clicks / impressions if impressions > 0 else 0, 4),
                "position": round(5 + random.uniform(-2, 2), 1)
            })

        return data

    @staticmethod
    def create_query_metrics(
        queries: Optional[List[str]] = None,
        property_url: str = "https://test-domain.com",
        days: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Generate query-level metrics.

        Args:
            queries: List of query strings (defaults to sample queries)
            property_url: Property URL
            days: Number of days

        Returns:
            List of query metric dictionaries
        """
        if queries is None:
            queries = [
                "running shoes",
                "best running shoes 2024",
                "marathon training",
                "brand name shoes",
                "shoe size guide"
            ]

        data = []
        for query in queries:
            for i in range(days):
                date = datetime.now().date() - timedelta(days=i)
                clicks = random.randint(10, 500)
                impressions = random.randint(100, 5000)

                data.append({
                    "query": query,
                    "property": property_url,
                    "date": date.isoformat(),
                    "clicks": clicks,
                    "impressions": impressions,
                    "ctr": round(clicks / impressions if impressions > 0 else 0, 4),
                    "position": round(random.uniform(1, 50), 1)
                })

        return data

    @staticmethod
    def create_page_metrics(
        pages: Optional[List[str]] = None,
        property_url: str = "https://test-domain.com",
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Generate page-level metrics.

        Args:
            pages: List of page paths
            property_url: Property URL
            days: Number of days

        Returns:
            List of page metric dictionaries
        """
        if pages is None:
            pages = [
                "/",
                "/product/shoes",
                "/blog/seo-guide",
                "/about",
                "/contact"
            ]

        data = []
        for page in pages:
            page_data = GSCDataFactory.create_daily_metrics(
                days=days,
                property_url=property_url,
                page_path=page,
                base_clicks=50 + random.randint(0, 200),
                base_impressions=500 + random.randint(0, 2000)
            )
            data.extend(page_data)

        return data


class GA4DataFactory:
    """Factory for generating mock GA4 data"""

    @staticmethod
    def create_daily_metrics(
        days: int = 30,
        property_url: str = "https://test-domain.com",
        page_path: str = "/test-page",
        base_sessions: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Generate daily GA4 metrics.

        Args:
            days: Number of days to generate
            property_url: Property URL
            page_path: Page path
            base_sessions: Base session count

        Returns:
            List of daily metric dictionaries
        """
        data = []

        for i in range(days):
            date = datetime.now().date() - timedelta(days=i)
            variance = random.uniform(0.8, 1.2)
            sessions = int(base_sessions * variance)

            data.append({
                "date": date.isoformat(),
                "property": property_url,
                "page_path": page_path,
                "sessions": sessions,
                "engaged_sessions": int(sessions * random.uniform(0.5, 0.7)),
                "conversions": int(sessions * random.uniform(0.01, 0.05)),
                "engagement_rate": round(0.5 + random.uniform(-0.15, 0.15), 4),
                "bounce_rate": round(0.3 + random.uniform(-0.1, 0.2), 4),
                "conversion_rate": round(random.uniform(0.01, 0.05), 4),
                "avg_session_duration": round(random.uniform(60, 300), 1),
                "users": int(sessions * random.uniform(0.7, 0.9))
            })

        return data

    @staticmethod
    def create_page_metrics(
        pages: Optional[List[str]] = None,
        property_url: str = "https://test-domain.com",
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Generate page-level GA4 metrics.

        Args:
            pages: List of page paths
            property_url: Property URL
            days: Number of days

        Returns:
            List of page metric dictionaries
        """
        if pages is None:
            pages = [
                "/",
                "/product/shoes",
                "/blog/seo-guide",
                "/checkout",
                "/thank-you"
            ]

        data = []
        for page in pages:
            base = 200 + random.randint(0, 500)
            page_data = GA4DataFactory.create_daily_metrics(
                days=days,
                property_url=property_url,
                page_path=page,
                base_sessions=base
            )
            data.extend(page_data)

        return data


class CWVDataFactory:
    """Factory for generating mock CWV data"""

    @staticmethod
    def create_page_metrics(
        page_path: str = "/test-page",
        strategy: str = "mobile",
        property_url: str = "https://test-domain.com"
    ) -> Dict[str, Any]:
        """
        Generate CWV metrics for a single page.

        Args:
            page_path: Page path
            strategy: Device strategy (mobile/desktop)
            property_url: Property URL

        Returns:
            CWV metrics dictionary
        """
        # Generate realistic CWV scores
        perf_base = 70 if strategy == "mobile" else 80

        return {
            "property": property_url,
            "page_path": page_path,
            "strategy": strategy,
            "check_date": datetime.now().date().isoformat(),
            "performance_score": perf_base + random.randint(0, 25),
            "lcp": random.randint(1500, 4000),  # ms
            "fid": random.randint(20, 300),     # ms
            "cls": round(random.uniform(0.01, 0.3), 3),
            "ttfb": random.randint(100, 800),   # ms
            "fcp": random.randint(500, 2000),   # ms
            "si": random.randint(1000, 5000),   # Speed Index
            "tbt": random.randint(50, 500)      # Total Blocking Time
        }

    @staticmethod
    def create_historical_metrics(
        page_path: str = "/test-page",
        days: int = 30,
        strategy: str = "mobile",
        property_url: str = "https://test-domain.com"
    ) -> List[Dict[str, Any]]:
        """
        Generate historical CWV data.

        Args:
            page_path: Page path
            days: Number of days
            strategy: Device strategy
            property_url: Property URL

        Returns:
            List of historical CWV metrics
        """
        data = []
        for i in range(days):
            metrics = CWVDataFactory.create_page_metrics(page_path, strategy, property_url)
            metrics["check_date"] = (datetime.now().date() - timedelta(days=i)).isoformat()
            data.append(metrics)
        return data

    @staticmethod
    def create_multi_page_metrics(
        pages: Optional[List[str]] = None,
        days: int = 30,
        property_url: str = "https://test-domain.com"
    ) -> List[Dict[str, Any]]:
        """
        Generate CWV metrics for multiple pages.

        Args:
            pages: List of page paths
            days: Number of days
            property_url: Property URL

        Returns:
            List of CWV metrics for all pages
        """
        if pages is None:
            pages = ["/", "/product/shoes", "/blog/seo-guide", "/about"]

        data = []
        for page in pages:
            for strategy in ["mobile", "desktop"]:
                page_data = CWVDataFactory.create_historical_metrics(
                    page, days, strategy, property_url
                )
                data.extend(page_data)
        return data


class SERPDataFactory:
    """Factory for generating mock SERP data"""

    @staticmethod
    def create_position_history(
        query: str = "test query",
        days: int = 30,
        property_url: str = "https://test-domain.com",
        base_position: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate SERP position history.

        Args:
            query: Search query
            days: Number of days
            property_url: Property URL
            base_position: Starting position (random if not specified)

        Returns:
            List of position history records
        """
        if base_position is None:
            base_position = random.randint(5, 15)

        data = []
        current_pos = base_position

        for i in range(days):
            # Simulate position fluctuation
            current_pos += random.randint(-2, 2)
            current_pos = max(1, min(100, current_pos))  # Clamp to 1-100

            data.append({
                "query": query,
                "property": property_url,
                "position": current_pos,
                "url": f"{property_url}/test-page",
                "domain": property_url.replace("https://", "").replace("http://", ""),
                "check_date": (datetime.now().date() - timedelta(days=i)).isoformat()
            })

        return data

    @staticmethod
    def create_query_tracking(
        queries: Optional[List[str]] = None,
        days: int = 30,
        property_url: str = "https://test-domain.com"
    ) -> Dict[str, Any]:
        """
        Generate query tracking data with position history.

        Args:
            queries: List of queries to track
            days: Number of days
            property_url: Property URL

        Returns:
            Dictionary with queries and their position history
        """
        if queries is None:
            queries = [
                "best running shoes",
                "seo guide 2024",
                "marathon training tips",
                "shoe size guide"
            ]

        result = {"queries": [], "positions": []}

        for query in queries:
            result["queries"].append({
                "query_text": query,
                "property": property_url,
                "target_page_path": "/test-page",
                "is_active": True
            })

            positions = SERPDataFactory.create_position_history(
                query, days, property_url
            )
            result["positions"].extend(positions)

        return result


class InsightDataFactory:
    """Factory for generating mock insight data"""

    @staticmethod
    def create_insight(
        category: str = "risk",
        severity: str = "medium",
        property_url: str = "https://test-domain.com"
    ) -> Dict[str, Any]:
        """
        Generate a single insight.

        Args:
            category: Insight category (risk, opportunity, observation)
            severity: Severity level (high, medium, low)
            property_url: Property URL

        Returns:
            Insight dictionary
        """
        templates = {
            "risk": [
                ("Traffic Drop Detected", "Significant decrease in organic traffic"),
                ("Ranking Loss", "Key pages lost rankings"),
                ("CWV Degradation", "Core Web Vitals scores decreased")
            ],
            "opportunity": [
                ("Ranking Improvement", "Pages close to page 1"),
                ("Content Gap", "Missing content for high-volume keywords"),
                ("Optimization Potential", "Pages with high impressions, low CTR")
            ],
            "observation": [
                ("New Keywords", "New keywords driving traffic"),
                ("Traffic Pattern", "Seasonal traffic pattern detected"),
                ("Competitor Change", "Competitor ranking changes observed")
            ]
        }

        title, description = random.choice(templates.get(category, templates["observation"]))

        return {
            "property": property_url,
            "category": category,
            "severity": severity,
            "title": title,
            "description": description,
            "metric_affected": random.choice(["clicks", "impressions", "position", "ctr"]),
            "percent_change": round(random.uniform(-30, 30), 1) if category != "observation" else None,
            "created_at": datetime.now().isoformat(),
            "status": "active"
        }

    @staticmethod
    def create_insights(
        count: int = 10,
        property_url: str = "https://test-domain.com"
    ) -> List[Dict[str, Any]]:
        """
        Generate multiple insights.

        Args:
            count: Number of insights to generate
            property_url: Property URL

        Returns:
            List of insight dictionaries
        """
        categories = ["risk", "opportunity", "observation"]
        severities = ["high", "medium", "low"]

        return [
            InsightDataFactory.create_insight(
                random.choice(categories),
                random.choice(severities),
                property_url
            )
            for _ in range(count)
        ]


class DashboardMockData:
    """Combined mock data for all dashboard types"""

    @staticmethod
    def create_full_dataset(
        property_url: str = "https://test-domain.com",
        days: int = 30
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Create complete mock dataset for all dashboards.

        Args:
            property_url: Property URL
            days: Number of days

        Returns:
            Dictionary with data for all dashboard types
        """
        return {
            "gsc": GSCDataFactory.create_page_metrics(days=days, property_url=property_url),
            "ga4": GA4DataFactory.create_page_metrics(days=days, property_url=property_url),
            "cwv": CWVDataFactory.create_multi_page_metrics(days=days, property_url=property_url),
            "serp": SERPDataFactory.create_query_tracking(days=days, property_url=property_url),
            "insights": InsightDataFactory.create_insights(count=10, property_url=property_url)
        }

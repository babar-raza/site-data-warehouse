"""
GA4 API Client
Handles authentication and API requests to Google Analytics Data API v1
"""
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    DateRange,
    Dimension,
    Metric,
    FilterExpression,
    Filter,
    RunReportResponse
)
from google.oauth2 import service_account
import time

logger = logging.getLogger(__name__)


class GA4Client:
    """
    GA4 API client wrapper with rate limiting and error handling
    """
    
    def __init__(
        self,
        credentials_path: str,
        property_id: str,
        rate_limit_qps: int = 10
    ):
        """
        Initialize GA4 client
        
        Args:
            credentials_path: Path to service account JSON
            property_id: GA4 property ID (e.g., "12345678")
            rate_limit_qps: Max queries per second
        """
        self.property_id = property_id
        self.rate_limit_qps = rate_limit_qps
        self.last_request_time = 0
        
        # Load credentials
        try:
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/analytics.readonly']
            )
            self.client = BetaAnalyticsDataClient(credentials=credentials)
            logger.info(f"GA4 client initialized for property {property_id}")
        except Exception as e:
            logger.error(f"Failed to initialize GA4 client: {e}")
            raise
    
    def _rate_limit(self):
        """Apply rate limiting"""
        if self.rate_limit_qps > 0:
            min_interval = 1.0 / self.rate_limit_qps
            elapsed = time.time() - self.last_request_time
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def run_report(
        self,
        start_date: str,
        end_date: str,
        dimensions: List[str],
        metrics: List[str],
        dimension_filter: Optional[FilterExpression] = None,
        limit: int = 10000,
        offset: int = 0
    ) -> RunReportResponse:
        """
        Run a report request
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            dimensions: List of dimension names (e.g., ['date', 'pagePath'])
            metrics: List of metric names (e.g., ['sessions', 'conversions'])
            dimension_filter: Optional filter expression
            limit: Max rows to return
            offset: Pagination offset
            
        Returns:
            RunReportResponse object
        """
        self._rate_limit()
        
        request = RunReportRequest(
            property=f"properties/{self.property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimensions=[Dimension(name=d) for d in dimensions],
            metrics=[Metric(name=m) for m in metrics],
            limit=limit,
            offset=offset
        )
        
        if dimension_filter:
            request.dimension_filter = dimension_filter
        
        try:
            response = self.client.run_report(request)
            logger.debug(f"GA4 API request successful: {len(response.rows)} rows")
            return response
        except Exception as e:
            logger.error(f"GA4 API request failed: {e}")
            raise
    
    def get_page_metrics(
        self,
        start_date: str,
        end_date: str,
        page_path_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get page-level metrics for date range
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            page_path_filter: Optional page path filter (e.g., '/blog/*')
            
        Returns:
            List of dicts with page metrics
        """
        dimensions = ['date', 'pagePath']
        metrics = [
            'sessions',
            'engagedSessions',
            'engagementRate',
            'bounceRate',
            'conversions',
            'screenPageViews',
            'averageSessionDuration',
            'userEngagementDuration'
        ]
        
        # Build filter if provided
        dimension_filter = None
        if page_path_filter:
            dimension_filter = FilterExpression(
                filter=Filter(
                    field_name='pagePath',
                    string_filter=Filter.StringFilter(
                        match_type=Filter.StringFilter.MatchType.CONTAINS,
                        value=page_path_filter
                    )
                )
            )
        
        all_rows = []
        offset = 0
        limit = 10000
        
        while True:
            response = self.run_report(
                start_date=start_date,
                end_date=end_date,
                dimensions=dimensions,
                metrics=metrics,
                dimension_filter=dimension_filter,
                limit=limit,
                offset=offset
            )
            
            if not response.rows:
                break
            
            # Parse response
            for row in response.rows:
                data = {
                    'date': row.dimension_values[0].value,
                    'page_path': row.dimension_values[1].value,
                    'sessions': int(row.metric_values[0].value) if row.metric_values[0].value else 0,
                    'engaged_sessions': int(row.metric_values[1].value) if row.metric_values[1].value else 0,
                    'engagement_rate': float(row.metric_values[2].value) if row.metric_values[2].value else 0.0,
                    'bounce_rate': float(row.metric_values[3].value) if row.metric_values[3].value else 0.0,
                    'conversions': int(row.metric_values[4].value) if row.metric_values[4].value else 0,
                    'page_views': int(row.metric_values[5].value) if row.metric_values[5].value else 0,
                    'avg_session_duration': float(row.metric_values[6].value) if row.metric_values[6].value else 0.0,
                    'avg_time_on_page': float(row.metric_values[7].value) / int(row.metric_values[5].value) if row.metric_values[5].value and int(row.metric_values[5].value) > 0 else 0.0,
                }
                
                # Calculate conversion rate
                if data['sessions'] > 0:
                    data['conversion_rate'] = data['conversions'] / data['sessions']
                else:
                    data['conversion_rate'] = 0.0
                
                all_rows.append(data)
            
            # Check if we need to paginate
            if len(response.rows) < limit:
                break
            
            offset += limit
            logger.debug(f"Fetching next page: offset={offset}")
        
        logger.info(f"Fetched {len(all_rows)} rows from GA4 API")
        return all_rows
    
    def get_property_metadata(self) -> Dict[str, Any]:
        """
        Get property metadata
        
        Returns:
            Dict with property info
        """
        try:
            # Get a simple report to validate property access
            response = self.run_report(
                start_date='2025-01-01',
                end_date='2025-01-01',
                dimensions=['date'],
                metrics=['sessions'],
                limit=1
            )
            
            return {
                'property_id': self.property_id,
                'accessible': True,
                'row_count': response.row_count if hasattr(response, 'row_count') else None
            }
        except Exception as e:
            logger.error(f"Failed to get property metadata: {e}")
            return {
                'property_id': self.property_id,
                'accessible': False,
                'error': str(e)
            }
    
    def validate_credentials(self) -> bool:
        """
        Validate that credentials work
        
        Returns:
            True if credentials are valid
        """
        try:
            metadata = self.get_property_metadata()
            return metadata.get('accessible', False)
        except Exception as e:
            logger.error(f"Credential validation failed: {e}")
            return False

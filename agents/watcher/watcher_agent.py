"""Watcher Agent - Monitors GSC+GA4 metrics and detects anomalies."""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import asyncpg
import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base.agent_contract import AgentContract, AgentHealth, AgentStatus
from agents.watcher.alert_manager import Alert, AlertManager
from agents.watcher.anomaly_detector import Anomaly, AnomalyDetector
from agents.watcher.trend_analyzer import Trend, TrendAnalyzer


class WatcherAgent(AgentContract):
    """Agent that monitors metrics and detects anomalies."""

    def __init__(
        self,
        agent_id: str,
        db_config: Dict[str, str],
        config: Optional[Dict[str, any]] = None
    ):
        """Initialize watcher agent.
        
        Args:
            agent_id: Unique agent identifier
            db_config: Database configuration
            config: Optional agent configuration
        """
        super().__init__(agent_id, "watcher", config)
        
        self.db_config = db_config
        self._pool: Optional[asyncpg.Pool] = None
        
        # Initialize components
        self.anomaly_detector = AnomalyDetector(
            sensitivity=config.get('sensitivity', 2.5),
            min_data_points=config.get('min_data_points', 7)
        )
        
        self.trend_analyzer = TrendAnalyzer(
            min_confidence=config.get('min_confidence', 0.7),
            min_duration=config.get('min_duration', 7)
        )
        
        self.alert_manager = AlertManager(db_config)
        
        self._detected_anomalies: List[Anomaly] = []
        self._detected_trends: List[Trend] = []

    async def initialize(self) -> bool:
        """Initialize the watcher agent."""
        try:
            self._start_time = datetime.now()
            
            # Connect to database
            self._pool = await asyncpg.create_pool(
                host=self.db_config.get('host', 'localhost'),
                port=self.db_config.get('port', 5432),
                user=self.db_config.get('user', 'gsc_user'),
                password=self.db_config.get('password', ''),
                database=self.db_config.get('database', 'gsc_warehouse'),
                min_size=2,
                max_size=10
            )
            
            await self.alert_manager.connect()
            
            self._set_status(AgentStatus.RUNNING)
            
            return True
        
        except Exception as e:
            print(f"Error initializing watcher agent: {e}")
            self._set_status(AgentStatus.ERROR)
            self._increment_error_count()
            return False

    async def process(self, input_data: Dict[str, any]) -> Dict[str, any]:
        """Process monitoring request.
        
        Args:
            input_data: Input containing monitoring parameters
            
        Returns:
            Processing results
        """
        try:
            days = input_data.get('days', 7)
            property_filter = input_data.get('property')
            
            # Run anomaly detection
            anomalies = await self.detect_anomalies(days, property_filter)
            
            # Run trend analysis
            trends = await self.detect_trends(days, property_filter)
            
            self._increment_processed_count()
            
            return {
                'status': 'success',
                'anomalies_detected': len(anomalies),
                'trends_detected': len(trends),
                'agent_id': self.agent_id
            }
        
        except Exception as e:
            self._increment_error_count()
            return {
                'status': 'error',
                'error': str(e),
                'agent_id': self.agent_id
            }

    async def detect_anomalies(
        self,
        days: int = 7,
        property_filter: Optional[str] = None
    ) -> List[Anomaly]:
        """Detect anomalies in GSC and GA4 metrics.
        
        Args:
            days: Number of days to analyze
            property_filter: Optional property filter
            
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # Get pages with recent data
        pages = await self._get_active_pages(days, property_filter)
        
        for page in pages:
            page_path = page['page_path']
            
            # Get historical data for this page
            historical = await self._get_page_historical_data(
                page_path,
                days + 30,  # Extra days for baseline
                property_filter
            )
            
            if not historical:
                continue
            
            # Split into baseline and current
            baseline_data = historical[:-days]
            current_data = historical[-days:]
            
            if not current_data:
                continue
            
            # Detect traffic drops
            if len(baseline_data) >= 7:
                current_clicks = current_data[-1].get('clicks', 0)
                historical_clicks = [d.get('clicks', 0) for d in baseline_data]
                
                anomaly = self.anomaly_detector.detect_traffic_drop(
                    current_clicks,
                    historical_clicks,
                    threshold_percent=30.0
                )
                
                if anomaly:
                    anomaly.page_path = page_path
                    anomalies.append(anomaly)
                    
                    # Create alert
                    await self._create_anomaly_alert(anomaly, page)
            
            # Detect position drops
            if len(baseline_data) >= 7:
                current_position = current_data[-1].get('avg_position', 100)
                historical_positions = [d.get('avg_position', 100) for d in baseline_data]
                
                anomaly = self.anomaly_detector.detect_position_drop(
                    current_position,
                    historical_positions,
                    threshold_positions=5.0
                )
                
                if anomaly:
                    anomaly.page_path = page_path
                    anomalies.append(anomaly)
                    await self._create_anomaly_alert(anomaly, page)
            
            # Detect CTR anomalies
            if len(baseline_data) >= 7:
                current_ctr = current_data[-1].get('ctr', 0)
                historical_ctrs = [d.get('ctr', 0) for d in baseline_data if d.get('ctr')]
                
                anomaly = self.anomaly_detector.detect_ctr_anomaly(
                    current_ctr,
                    historical_ctrs
                )
                
                if anomaly:
                    anomaly.page_path = page_path
                    anomalies.append(anomaly)
                    await self._create_anomaly_alert(anomaly, page)
            
            # Detect engagement changes
            if len(baseline_data) >= 7:
                current_engagement = current_data[-1].get('engagement_rate', 0)
                historical_engagement = [
                    d.get('engagement_rate', 0) for d in baseline_data
                    if d.get('engagement_rate')
                ]
                
                if historical_engagement:
                    anomaly = self.anomaly_detector.detect_engagement_change(
                        current_engagement,
                        historical_engagement,
                        threshold_percent=25.0
                    )
                    
                    if anomaly:
                        anomaly.page_path = page_path
                        anomalies.append(anomaly)
                        await self._create_anomaly_alert(anomaly, page)
            
            # Detect conversion drops
            if len(baseline_data) >= 7:
                current_conversion = current_data[-1].get('conversion_rate', 0)
                historical_conversions = [
                    d.get('conversion_rate', 0) for d in baseline_data
                    if d.get('conversion_rate')
                ]
                
                if historical_conversions:
                    anomaly = self.anomaly_detector.detect_conversion_drop(
                        current_conversion,
                        historical_conversions,
                        threshold_percent=20.0
                    )
                    
                    if anomaly:
                        anomaly.page_path = page_path
                        anomalies.append(anomaly)
                        await self._create_anomaly_alert(anomaly, page)
            
            # Detect zero traffic (dead pages)
            if len(baseline_data) >= 7:
                current_clicks = current_data[-1].get('clicks', 0)
                current_impressions = current_data[-1].get('impressions', 0)
                historical_clicks = [d.get('clicks', 0) for d in baseline_data]
                
                anomaly = self.anomaly_detector.detect_zero_traffic(
                    current_clicks,
                    current_impressions,
                    historical_clicks
                )
                
                if anomaly:
                    anomaly.page_path = page_path
                    anomalies.append(anomaly)
                    await self._create_anomaly_alert(anomaly, page)
        
        self._detected_anomalies = anomalies
        
        return anomalies

    async def detect_trends(
        self,
        days: int = 7,
        property_filter: Optional[str] = None
    ) -> List[Trend]:
        """Detect trends in GSC and GA4 metrics.
        
        Args:
            days: Number of days to analyze
            property_filter: Optional property filter
            
        Returns:
            List of detected trends
        """
        trends = []
        
        # Get pages with sufficient data
        pages = await self._get_active_pages(days * 2, property_filter)
        
        for page in pages:
            page_path = page['page_path']
            
            # Get time series data
            time_series = await self._get_page_time_series(
                page_path,
                days * 2,
                property_filter
            )
            
            if not time_series:
                continue
            
            # Detect linear trends in clicks
            clicks_series = [d.get('clicks', 0) for d in time_series]
            trend = self.trend_analyzer.detect_linear_trend(clicks_series)
            
            if trend:
                trend.metric_name = 'clicks'
                trend.page_path = page_path
                trends.append(trend)
                await self._create_trend_alert(trend, page)
            
            # Detect acceleration in impressions
            impressions_series = [d.get('impressions', 0) for d in time_series]
            trend = self.trend_analyzer.detect_acceleration(impressions_series)
            
            if trend:
                trend.metric_name = 'impressions'
                trend.page_path = page_path
                trends.append(trend)
                await self._create_trend_alert(trend, page)
            
            # Detect volatility
            ctr_series = [d.get('ctr', 0) for d in time_series if d.get('ctr')]
            
            if ctr_series:
                trend = self.trend_analyzer.detect_volatility(ctr_series)
                
                if trend:
                    trend.metric_name = 'ctr'
                    trend.page_path = page_path
                    trends.append(trend)
                    await self._create_trend_alert(trend, page)
        
        self._detected_trends = trends
        
        return trends

    async def generate_alerts(self) -> int:
        """Generate and store all pending alerts.
        
        Returns:
            Number of alerts generated
        """
        # Anomaly and trend alerts are created during detection
        # This method can be used for additional alert generation logic
        
        return len(self._detected_anomalies) + len(self._detected_trends)

    async def _create_anomaly_alert(self, anomaly: Anomaly, page_data: Dict):
        """Create alert for detected anomaly."""
        alert = Alert(
            agent_name=self.agent_id,
            finding_type='anomaly',
            severity=anomaly.severity,
            affected_pages=[anomaly.page_path],
            metrics={
                'metric_name': anomaly.metric_name,
                'current_value': anomaly.current_value,
                'expected_value': anomaly.expected_value,
                'deviation_percent': anomaly.deviation_percent,
                'context': anomaly.context
            },
            notes=f"Anomaly detected in {anomaly.metric_name}",
            metadata={
                'detected_at': anomaly.detected_at.isoformat(),
                'page_data': page_data
            }
        )
        
        await self.alert_manager.create_alert(alert)

    async def _create_trend_alert(self, trend: Trend, page_data: Dict):
        """Create alert for detected trend."""
        alert = Alert(
            agent_name=self.agent_id,
            finding_type='trend',
            severity='info' if trend.trend_type in ['stable', 'increasing'] else 'warning',
            affected_pages=[trend.page_path],
            metrics={
                'metric_name': trend.metric_name,
                'trend_type': trend.trend_type,
                'slope': trend.slope,
                'confidence': trend.confidence,
                'magnitude_percent': trend.magnitude_percent,
                'duration_days': trend.duration_days,
                'context': trend.context
            },
            notes=f"{trend.trend_type.title()} trend detected in {trend.metric_name}",
            metadata={
                'detected_at': trend.detected_at.isoformat(),
                'page_data': page_data
            }
        )
        
        await self.alert_manager.create_alert(alert)

    async def _get_active_pages(
        self,
        days: int,
        property_filter: Optional[str]
    ) -> List[Dict]:
        """Get active pages with recent data."""
        query = """
            SELECT DISTINCT page_path,
                   MAX(date) as last_seen
            FROM gsc.mv_unified_page_performance
            WHERE date >= CURRENT_DATE - $1
        """
        
        params = [days]
        
        if property_filter:
            query += " AND property = $2"
            params.append(property_filter)
        
        query += """
            GROUP BY page_path
            HAVING SUM(clicks) > 0 OR SUM(impressions) > 100
            ORDER BY SUM(clicks) DESC
            LIMIT 1000
        """
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        
        return [dict(row) for row in rows]

    async def _get_page_historical_data(
        self,
        page_path: str,
        days: int,
        property_filter: Optional[str]
    ) -> List[Dict]:
        """Get historical data for a page."""
        query = """
            SELECT date, clicks, impressions, ctr, avg_position,
                   engagement_rate, conversion_rate, sessions
            FROM gsc.mv_unified_page_performance
            WHERE page_path = $1
              AND date >= CURRENT_DATE - $2
        """
        
        params = [page_path, days]
        
        if property_filter:
            query += " AND property = $3"
            params.append(property_filter)
        
        query += " ORDER BY date ASC"
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        
        return [dict(row) for row in rows]

    async def _get_page_time_series(
        self,
        page_path: str,
        days: int,
        property_filter: Optional[str]
    ) -> List[Dict]:
        """Get time series data for a page."""
        return await self._get_page_historical_data(page_path, days, property_filter)

    async def health_check(self) -> AgentHealth:
        """Check agent health."""
        uptime = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0
        
        return AgentHealth(
            agent_id=self.agent_id,
            status=self.status,
            uptime_seconds=uptime,
            last_heartbeat=datetime.now(),
            error_count=self._error_count,
            processed_count=self._processed_count,
            memory_usage_mb=100.0,
            cpu_percent=10.0,
            metadata={
                'anomalies_detected': len(self._detected_anomalies),
                'trends_detected': len(self._detected_trends)
            }
        )

    async def shutdown(self) -> bool:
        """Shutdown the agent."""
        try:
            if self._pool:
                await self._pool.close()
            
            await self.alert_manager.disconnect()
            
            self._set_status(AgentStatus.SHUTDOWN)
            
            return True
        
        except Exception as e:
            print(f"Error shutting down: {e}")
            return False


async def main():
    """CLI for watcher agent."""
    parser = argparse.ArgumentParser(description='Watcher Agent')
    parser.add_argument('--initialize', action='store_true', help='Initialize agent')
    parser.add_argument('--detect', action='store_true', help='Run anomaly detection')
    parser.add_argument('--generate-alerts', action='store_true', help='Generate alerts')
    parser.add_argument('--days', type=int, default=7, help='Days to analyze')
    parser.add_argument('--config', default='agents/watcher/config.yaml', help='Config file')
    
    args = parser.parse_args()
    
    # Load configuration
    config_path = Path(args.config)
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
    else:
        config = {
            'database': {
                'host': 'localhost',
                'port': 5432,
                'user': 'gsc_user',
                'password': 'changeme',
                'database': 'gsc_warehouse'
            },
            'sensitivity': 2.5,
            'min_data_points': 7
        }
    
    # Create agent
    agent = WatcherAgent(
        agent_id='watcher_001',
        db_config=config.get('database', {}),
        config=config
    )
    
    if args.initialize:
        print("Initializing watcher agent...")
        success = await agent.initialize()
        if success:
            print("✓ Watcher agent initialized")
        else:
            print("✗ Failed to initialize")
            return
    
    if args.detect:
        print(f"Running anomaly detection (last {args.days} days)...")
        
        if not agent._pool:
            await agent.initialize()
        
        anomalies = await agent.detect_anomalies(args.days)
        trends = await agent.detect_trends(args.days)
        
        print(f"✓ Detected {len(anomalies)} anomalies")
        print(f"✓ Detected {len(trends)} trends")
        
        # Print summary
        if anomalies:
            print("\nAnomalies:")
            for anomaly in anomalies[:10]:
                print(f"  - {anomaly.severity}: {anomaly.metric_name} on {anomaly.page_path}")
                print(f"    Current: {anomaly.current_value:.2f}, Expected: {anomaly.expected_value:.2f}")
        
        if trends:
            print("\nTrends:")
            for trend in trends[:10]:
                print(f"  - {trend.trend_type}: {trend.metric_name} on {trend.page_path}")
                print(f"    Magnitude: {trend.magnitude_percent:.1f}%, Confidence: {trend.confidence:.2f}")
    
    if args.generate_alerts:
        print("Generating alerts...")
        
        if not agent._pool:
            await agent.initialize()
        
        count = await agent.generate_alerts()
        print(f"✓ Generated {count} alerts")
    
    # Shutdown
    await agent.shutdown()


if __name__ == '__main__':
    asyncio.run(main())

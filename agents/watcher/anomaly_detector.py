"""Anomaly detection algorithms for GSC and GA4 metrics."""

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class Anomaly:
    """Represents a detected anomaly."""
    metric_name: str
    page_path: str
    current_value: float
    expected_value: float
    deviation_percent: float
    severity: str  # 'critical', 'warning', 'info'
    detected_at: datetime
    context: Dict[str, any]


class AnomalyDetector:
    """Detects anomalies in time series data using statistical methods."""

    def __init__(
        self,
        sensitivity: float = 2.5,
        min_data_points: int = 7
    ):
        """Initialize anomaly detector.
        
        Args:
            sensitivity: Z-score threshold for anomaly detection
            min_data_points: Minimum historical data points required
        """
        self.sensitivity = sensitivity
        self.min_data_points = min_data_points

    def detect_traffic_drop(
        self,
        current_clicks: int,
        historical_clicks: List[int],
        threshold_percent: float = 30.0
    ) -> Optional[Anomaly]:
        """Detect sudden traffic drops > threshold percent.
        
        Args:
            current_clicks: Current day clicks
            historical_clicks: Historical click counts
            threshold_percent: Drop threshold percentage
            
        Returns:
            Anomaly if detected, None otherwise
        """
        if len(historical_clicks) < self.min_data_points:
            return None
        
        avg_historical = statistics.mean(historical_clicks)
        
        if avg_historical == 0:
            return None
        
        drop_percent = ((avg_historical - current_clicks) / avg_historical) * 100
        
        if drop_percent > threshold_percent:
            severity = 'critical' if drop_percent > 50 else 'warning'
            
            return Anomaly(
                metric_name='clicks',
                page_path='',
                current_value=current_clicks,
                expected_value=avg_historical,
                deviation_percent=drop_percent,
                severity=severity,
                detected_at=datetime.now(),
                context={
                    'threshold': threshold_percent,
                    'historical_avg': avg_historical,
                    'historical_min': min(historical_clicks),
                    'historical_max': max(historical_clicks)
                }
            )
        
        return None

    def detect_position_drop(
        self,
        current_position: float,
        historical_positions: List[float],
        threshold_positions: float = 5.0
    ) -> Optional[Anomaly]:
        """Detect position drops > threshold positions.
        
        Args:
            current_position: Current average position
            historical_positions: Historical positions
            threshold_positions: Drop threshold in positions
            
        Returns:
            Anomaly if detected, None otherwise
        """
        if len(historical_positions) < self.min_data_points:
            return None
        
        avg_historical = statistics.mean(historical_positions)
        
        position_drop = current_position - avg_historical
        
        if position_drop > threshold_positions:
            severity = 'critical' if position_drop > 10 else 'warning'
            
            return Anomaly(
                metric_name='position',
                page_path='',
                current_value=current_position,
                expected_value=avg_historical,
                deviation_percent=(position_drop / avg_historical) * 100,
                severity=severity,
                detected_at=datetime.now(),
                context={
                    'threshold': threshold_positions,
                    'position_drop': position_drop,
                    'historical_avg': avg_historical,
                    'historical_best': min(historical_positions),
                    'historical_worst': max(historical_positions)
                }
            )
        
        return None

    def detect_ctr_anomaly(
        self,
        current_ctr: float,
        historical_ctrs: List[float]
    ) -> Optional[Anomaly]:
        """Detect CTR anomalies using z-score method.
        
        Args:
            current_ctr: Current CTR
            historical_ctrs: Historical CTR values
            
        Returns:
            Anomaly if detected, None otherwise
        """
        if len(historical_ctrs) < self.min_data_points:
            return None
        
        mean_ctr = statistics.mean(historical_ctrs)
        
        try:
            std_ctr = statistics.stdev(historical_ctrs)
        except statistics.StatisticsError:
            return None
        
        if std_ctr == 0:
            return None
        
        z_score = abs((current_ctr - mean_ctr) / std_ctr)
        
        if z_score > self.sensitivity:
            deviation_percent = ((current_ctr - mean_ctr) / mean_ctr) * 100 if mean_ctr > 0 else 0
            
            severity = 'critical' if z_score > self.sensitivity * 1.5 else 'warning'
            
            return Anomaly(
                metric_name='ctr',
                page_path='',
                current_value=current_ctr,
                expected_value=mean_ctr,
                deviation_percent=abs(deviation_percent),
                severity=severity,
                detected_at=datetime.now(),
                context={
                    'z_score': z_score,
                    'std_dev': std_ctr,
                    'historical_mean': mean_ctr,
                    'direction': 'increase' if current_ctr > mean_ctr else 'decrease'
                }
            )
        
        return None

    def detect_engagement_change(
        self,
        current_engagement: float,
        historical_engagement: List[float],
        threshold_percent: float = 25.0
    ) -> Optional[Anomaly]:
        """Detect significant engagement rate changes.
        
        Args:
            current_engagement: Current engagement rate
            historical_engagement: Historical engagement rates
            threshold_percent: Change threshold percentage
            
        Returns:
            Anomaly if detected, None otherwise
        """
        if len(historical_engagement) < self.min_data_points:
            return None
        
        avg_engagement = statistics.mean(historical_engagement)
        
        if avg_engagement == 0:
            return None
        
        change_percent = abs(((current_engagement - avg_engagement) / avg_engagement) * 100)
        
        if change_percent > threshold_percent:
            severity = 'warning' if change_percent < 50 else 'critical'
            
            return Anomaly(
                metric_name='engagement_rate',
                page_path='',
                current_value=current_engagement,
                expected_value=avg_engagement,
                deviation_percent=change_percent,
                severity=severity,
                detected_at=datetime.now(),
                context={
                    'threshold': threshold_percent,
                    'historical_avg': avg_engagement,
                    'direction': 'increase' if current_engagement > avg_engagement else 'decrease'
                }
            )
        
        return None

    def detect_conversion_drop(
        self,
        current_conversion_rate: float,
        historical_conversion_rates: List[float],
        threshold_percent: float = 20.0
    ) -> Optional[Anomaly]:
        """Detect conversion rate drops.
        
        Args:
            current_conversion_rate: Current conversion rate
            historical_conversion_rates: Historical conversion rates
            threshold_percent: Drop threshold percentage
            
        Returns:
            Anomaly if detected, None otherwise
        """
        if len(historical_conversion_rates) < self.min_data_points:
            return None
        
        # Filter out zeros
        valid_rates = [r for r in historical_conversion_rates if r > 0]
        
        if not valid_rates:
            return None
        
        avg_rate = statistics.mean(valid_rates)
        
        if avg_rate == 0:
            return None
        
        drop_percent = ((avg_rate - current_conversion_rate) / avg_rate) * 100
        
        if drop_percent > threshold_percent:
            severity = 'critical' if drop_percent > 40 else 'warning'
            
            return Anomaly(
                metric_name='conversion_rate',
                page_path='',
                current_value=current_conversion_rate,
                expected_value=avg_rate,
                deviation_percent=drop_percent,
                severity=severity,
                detected_at=datetime.now(),
                context={
                    'threshold': threshold_percent,
                    'historical_avg': avg_rate,
                    'historical_data_points': len(valid_rates)
                }
            )
        
        return None

    def detect_multivariate_anomaly(
        self,
        current_metrics: Dict[str, float],
        historical_metrics: List[Dict[str, float]],
        metric_names: List[str]
    ) -> Optional[Anomaly]:
        """Detect anomalies across multiple metrics using Mahalanobis distance.
        
        Args:
            current_metrics: Current metric values
            historical_metrics: Historical metric dictionaries
            metric_names: Names of metrics to analyze
            
        Returns:
            Anomaly if detected, None otherwise
        """
        if len(historical_metrics) < self.min_data_points:
            return None
        
        # Extract metric vectors
        try:
            historical_vectors = []
            for hist in historical_metrics:
                vector = [hist.get(m, 0) for m in metric_names]
                if all(v is not None for v in vector):
                    historical_vectors.append(vector)
            
            if len(historical_vectors) < self.min_data_points:
                return None
            
            current_vector = [current_metrics.get(m, 0) for m in metric_names]
            
            # Calculate means and covariance
            historical_array = np.array(historical_vectors)
            mean_vector = np.mean(historical_array, axis=0)
            cov_matrix = np.cov(historical_array.T)
            
            # Calculate Mahalanobis distance
            diff = current_vector - mean_vector
            inv_cov = np.linalg.pinv(cov_matrix)
            mahal_dist = np.sqrt(diff @ inv_cov @ diff)
            
            # Threshold based on chi-square distribution
            threshold = 3.0
            
            if mahal_dist > threshold:
                return Anomaly(
                    metric_name='multivariate',
                    page_path='',
                    current_value=mahal_dist,
                    expected_value=0,
                    deviation_percent=100 * (mahal_dist / threshold),
                    severity='warning' if mahal_dist < threshold * 1.5 else 'critical',
                    detected_at=datetime.now(),
                    context={
                        'mahalanobis_distance': mahal_dist,
                        'threshold': threshold,
                        'metrics_analyzed': metric_names,
                        'current_metrics': current_metrics
                    }
                )
        
        except (np.linalg.LinAlgError, ValueError):
            # Covariance matrix singular or other numerical issues
            return None
        
        return None

    def detect_zero_traffic(
        self,
        current_clicks: int,
        current_impressions: int,
        historical_clicks: List[int]
    ) -> Optional[Anomaly]:
        """Detect pages that suddenly have zero traffic (dead pages).
        
        Args:
            current_clicks: Current clicks
            current_impressions: Current impressions
            historical_clicks: Historical click counts
            
        Returns:
            Anomaly if detected, None otherwise
        """
        if len(historical_clicks) < self.min_data_points:
            return None
        
        avg_historical = statistics.mean(historical_clicks)
        
        # Page previously had traffic but now has none
        if avg_historical > 10 and current_clicks == 0 and current_impressions == 0:
            return Anomaly(
                metric_name='zero_traffic',
                page_path='',
                current_value=0,
                expected_value=avg_historical,
                deviation_percent=100,
                severity='critical',
                detected_at=datetime.now(),
                context={
                    'historical_avg_clicks': avg_historical,
                    'possible_cause': 'page_deleted_or_deindexed'
                }
            )
        
        return None

    def calculate_baseline(
        self,
        time_series: List[float],
        method: str = 'mean'
    ) -> Tuple[float, float]:
        """Calculate baseline and standard deviation from time series.
        
        Args:
            time_series: Time series data
            method: Baseline calculation method ('mean', 'median')
            
        Returns:
            Tuple of (baseline, standard_deviation)
        """
        if not time_series:
            return 0.0, 0.0
        
        if method == 'median':
            baseline = statistics.median(time_series)
        else:
            baseline = statistics.mean(time_series)
        
        try:
            std_dev = statistics.stdev(time_series)
        except statistics.StatisticsError:
            std_dev = 0.0
        
        return baseline, std_dev

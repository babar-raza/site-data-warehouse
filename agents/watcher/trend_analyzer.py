"""Trend analysis for identifying patterns and opportunities in GSC/GA4 metrics."""

import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class Trend:
    """Represents an identified trend."""
    metric_name: str
    page_path: str
    trend_type: str  # 'increasing', 'decreasing', 'stable', 'volatile'
    slope: float
    confidence: float
    duration_days: int
    magnitude_percent: float
    detected_at: datetime
    context: Dict[str, any]


class TrendAnalyzer:
    """Analyzes trends in time series metrics."""

    def __init__(
        self,
        min_confidence: float = 0.7,
        min_duration: int = 7
    ):
        """Initialize trend analyzer.
        
        Args:
            min_confidence: Minimum confidence level for trend detection
            min_duration: Minimum duration in days for trend
        """
        self.min_confidence = min_confidence
        self.min_duration = min_duration

    def detect_linear_trend(
        self,
        time_series: List[float],
        dates: Optional[List[datetime]] = None
    ) -> Optional[Trend]:
        """Detect linear trends using least squares regression.
        
        Args:
            time_series: Time series data
            dates: Optional dates for each data point
            
        Returns:
            Trend if detected, None otherwise
        """
        if len(time_series) < self.min_duration:
            return None
        
        # Remove None values
        valid_data = [(i, v) for i, v in enumerate(time_series) if v is not None]
        
        if len(valid_data) < self.min_duration:
            return None
        
        x = np.array([d[0] for d in valid_data])
        y = np.array([d[1] for d in valid_data])
        
        # Linear regression
        try:
            coeffs = np.polyfit(x, y, 1)
            slope = coeffs[0]
            intercept = coeffs[1]
            
            # Calculate R-squared
            y_pred = slope * x + intercept
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
            
            # Determine trend type
            if abs(slope) < 0.01 * np.mean(y):
                trend_type = 'stable'
            elif slope > 0:
                trend_type = 'increasing'
            else:
                trend_type = 'decreasing'
            
            # Calculate magnitude
            if len(y) > 1:
                magnitude_percent = abs((y[-1] - y[0]) / y[0] * 100) if y[0] != 0 else 0
            else:
                magnitude_percent = 0
            
            if r_squared >= self.min_confidence:
                return Trend(
                    metric_name='',
                    page_path='',
                    trend_type=trend_type,
                    slope=slope,
                    confidence=r_squared,
                    duration_days=len(time_series),
                    magnitude_percent=magnitude_percent,
                    detected_at=datetime.now(),
                    context={
                        'intercept': intercept,
                        'r_squared': r_squared,
                        'start_value': y[0],
                        'end_value': y[-1],
                        'mean_value': np.mean(y)
                    }
                )
        
        except (np.linalg.LinAlgError, ValueError):
            return None
        
        return None

    def detect_acceleration(
        self,
        time_series: List[float]
    ) -> Optional[Trend]:
        """Detect accelerating trends (exponential growth/decay).
        
        Args:
            time_series: Time series data
            
        Returns:
            Trend if detected, None otherwise
        """
        if len(time_series) < self.min_duration:
            return None
        
        # Filter valid data
        valid_data = [v for v in time_series if v is not None and v > 0]
        
        if len(valid_data) < self.min_duration:
            return None
        
        try:
            # Fit exponential model using log transformation
            x = np.arange(len(valid_data))
            y = np.array(valid_data)
            log_y = np.log(y)
            
            coeffs = np.polyfit(x, log_y, 1)
            growth_rate = coeffs[0]
            
            # Calculate R-squared for exponential fit
            log_y_pred = coeffs[0] * x + coeffs[1]
            ss_res = np.sum((log_y - log_y_pred) ** 2)
            ss_tot = np.sum((log_y - np.mean(log_y)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
            
            # Significant acceleration if growth rate is notable and fit is good
            if abs(growth_rate) > 0.05 and r_squared >= self.min_confidence:
                trend_type = 'exponential_growth' if growth_rate > 0 else 'exponential_decay'
                
                magnitude_percent = abs((y[-1] - y[0]) / y[0] * 100) if y[0] != 0 else 0
                
                return Trend(
                    metric_name='',
                    page_path='',
                    trend_type=trend_type,
                    slope=growth_rate,
                    confidence=r_squared,
                    duration_days=len(time_series),
                    magnitude_percent=magnitude_percent,
                    detected_at=datetime.now(),
                    context={
                        'growth_rate': growth_rate,
                        'r_squared': r_squared,
                        'start_value': y[0],
                        'end_value': y[-1],
                        'compound_growth': (y[-1] / y[0]) if y[0] != 0 else 0
                    }
                )
        
        except (np.linalg.LinAlgError, ValueError, RuntimeWarning):
            return None
        
        return None

    def detect_seasonality(
        self,
        time_series: List[float],
        period: int = 7
    ) -> Optional[Trend]:
        """Detect seasonal patterns (e.g., weekly patterns).
        
        Args:
            time_series: Time series data
            period: Period length (default 7 for weekly)
            
        Returns:
            Trend if detected, None otherwise
        """
        if len(time_series) < period * 3:
            return None
        
        try:
            # Calculate autocorrelation at the period
            data = np.array([v for v in time_series if v is not None])
            
            if len(data) < period * 2:
                return None
            
            mean = np.mean(data)
            
            # Autocorrelation at lag = period
            c0 = np.sum((data - mean) ** 2)
            c_lag = np.sum((data[:-period] - mean) * (data[period:] - mean))
            
            autocorr = c_lag / c0 if c0 != 0 else 0
            
            # Strong seasonality if autocorrelation > threshold
            if autocorr > 0.5:
                # Calculate seasonal amplitude
                period_groups = [data[i::period] for i in range(period)]
                period_means = [np.mean(g) for g in period_groups if len(g) > 0]
                
                if period_means:
                    amplitude = (max(period_means) - min(period_means)) / mean * 100 if mean != 0 else 0
                    
                    return Trend(
                        metric_name='',
                        page_path='',
                        trend_type='seasonal',
                        slope=0,
                        confidence=autocorr,
                        duration_days=len(time_series),
                        magnitude_percent=amplitude,
                        detected_at=datetime.now(),
                        context={
                            'period': period,
                            'autocorrelation': autocorr,
                            'seasonal_amplitude': amplitude,
                            'period_means': period_means
                        }
                    )
        
        except (ValueError, ZeroDivisionError):
            return None
        
        return None

    def detect_volatility(
        self,
        time_series: List[float]
    ) -> Optional[Trend]:
        """Detect high volatility in metrics.
        
        Args:
            time_series: Time series data
            
        Returns:
            Trend if detected, None otherwise
        """
        if len(time_series) < self.min_duration:
            return None
        
        valid_data = [v for v in time_series if v is not None]
        
        if len(valid_data) < self.min_duration:
            return None
        
        try:
            mean = statistics.mean(valid_data)
            std_dev = statistics.stdev(valid_data)
            
            # Coefficient of variation
            cv = (std_dev / mean * 100) if mean != 0 else 0
            
            # High volatility if CV > 30%
            if cv > 30:
                return Trend(
                    metric_name='',
                    page_path='',
                    trend_type='volatile',
                    slope=0,
                    confidence=1.0,
                    duration_days=len(time_series),
                    magnitude_percent=cv,
                    detected_at=datetime.now(),
                    context={
                        'coefficient_of_variation': cv,
                        'mean': mean,
                        'std_dev': std_dev,
                        'min': min(valid_data),
                        'max': max(valid_data)
                    }
                )
        
        except statistics.StatisticsError:
            return None
        
        return None

    def identify_opportunity(
        self,
        impressions: int,
        clicks: int,
        position: float,
        historical_avg_ctr: float
    ) -> Optional[Dict[str, any]]:
        """Identify improvement opportunities based on metrics.
        
        Args:
            impressions: Current impressions
            clicks: Current clicks
            position: Current position
            historical_avg_ctr: Historical average CTR
            
        Returns:
            Opportunity dict if found, None otherwise
        """
        opportunities = []
        
        current_ctr = (clicks / impressions * 100) if impressions > 0 else 0
        
        # High impressions but low CTR - opportunity for better titles/descriptions
        if impressions > 100 and current_ctr < historical_avg_ctr * 0.5:
            opportunities.append({
                'type': 'low_ctr_high_impressions',
                'severity': 'warning',
                'description': 'High impressions but low CTR - optimize title and meta description',
                'current_ctr': current_ctr,
                'expected_ctr': historical_avg_ctr,
                'potential_clicks': int(impressions * (historical_avg_ctr / 100) - clicks)
            })
        
        # Good position but low CTR - branding or snippet issue
        if position <= 5 and current_ctr < 5:
            opportunities.append({
                'type': 'top_position_low_ctr',
                'severity': 'warning',
                'description': 'Top ranking but low CTR - improve snippet appeal',
                'position': position,
                'current_ctr': current_ctr,
                'expected_ctr': 15  # Rough average for top 5
            })
        
        # High position (11-20) with many impressions - opportunity to rank higher
        if 11 <= position <= 20 and impressions > 500:
            opportunities.append({
                'type': 'page_two_opportunity',
                'severity': 'info',
                'description': 'Page 2 ranking with good search volume - target top 10',
                'position': position,
                'impressions': impressions,
                'estimated_clicks_if_top10': int(impressions * 0.02)  # Conservative estimate
            })
        
        if opportunities:
            return {
                'page_path': '',
                'opportunities': opportunities,
                'total_potential_clicks': sum(
                    opp.get('potential_clicks', 0) + opp.get('estimated_clicks_if_top10', 0)
                    for opp in opportunities
                )
            }
        
        return None

    def detect_emerging_trend(
        self,
        recent_data: List[float],
        historical_baseline: float,
        lookback_days: int = 3
    ) -> Optional[Trend]:
        """Detect emerging trends in recent data.
        
        Args:
            recent_data: Most recent data points
            historical_baseline: Historical baseline value
            lookback_days: Days to consider for emerging trend
            
        Returns:
            Trend if detected, None otherwise
        """
        if len(recent_data) < lookback_days:
            return None
        
        recent_avg = statistics.mean(recent_data[-lookback_days:])
        
        if historical_baseline == 0:
            return None
        
        change_percent = ((recent_avg - historical_baseline) / historical_baseline) * 100
        
        # Significant emerging trend if > 20% change
        if abs(change_percent) > 20:
            trend_type = 'emerging_increase' if change_percent > 0 else 'emerging_decrease'
            
            return Trend(
                metric_name='',
                page_path='',
                trend_type=trend_type,
                slope=change_percent / lookback_days,
                confidence=0.8,
                duration_days=lookback_days,
                magnitude_percent=abs(change_percent),
                detected_at=datetime.now(),
                context={
                    'recent_avg': recent_avg,
                    'historical_baseline': historical_baseline,
                    'change_percent': change_percent,
                    'lookback_days': lookback_days
                }
            )
        
        return None

    def calculate_momentum(
        self,
        time_series: List[float],
        period: int = 7
    ) -> float:
        """Calculate momentum (rate of change) over a period.
        
        Args:
            time_series: Time series data
            period: Period for momentum calculation
            
        Returns:
            Momentum value
        """
        if len(time_series) < period + 1:
            return 0.0
        
        current_avg = statistics.mean(time_series[-period:])
        previous_avg = statistics.mean(time_series[-period*2:-period])
        
        if previous_avg == 0:
            return 0.0
        
        momentum = ((current_avg - previous_avg) / previous_avg) * 100
        
        return momentum

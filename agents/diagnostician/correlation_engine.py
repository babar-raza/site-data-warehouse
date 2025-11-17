"""Correlation analysis engine for identifying metric relationships."""

import statistics
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class Correlation:
    """Represents a correlation between metrics."""
    metric1: str
    metric2: str
    correlation_coefficient: float
    p_value: float
    strength: str  # 'strong', 'moderate', 'weak'
    direction: str  # 'positive', 'negative'


class CorrelationEngine:
    """Analyzes correlations between metrics."""

    def __init__(self, min_correlation: float = 0.5):
        """Initialize correlation engine.
        
        Args:
            min_correlation: Minimum correlation coefficient threshold
        """
        self.min_correlation = min_correlation

    def calculate_correlation(
        self,
        series1: List[float],
        series2: List[float]
    ) -> Optional[Correlation]:
        """Calculate correlation between two metric series.
        
        Args:
            series1: First metric series
            series2: Second metric series
            
        Returns:
            Correlation object if significant, None otherwise
        """
        if len(series1) != len(series2) or len(series1) < 3:
            return None
        
        # Filter out None values
        paired_data = [(x, y) for x, y in zip(series1, series2) if x is not None and y is not None]
        
        if len(paired_data) < 3:
            return None
        
        x = np.array([p[0] for p in paired_data])
        y = np.array([p[1] for p in paired_data])
        
        # Calculate Pearson correlation
        try:
            corr_matrix = np.corrcoef(x, y)
            correlation_coef = corr_matrix[0, 1]
            
            # Simple p-value approximation
            n = len(paired_data)
            t_stat = correlation_coef * np.sqrt(n - 2) / np.sqrt(1 - correlation_coef**2)
            p_value = 2 * (1 - self._t_cdf(abs(t_stat), n - 2))
            
            # Determine strength
            abs_corr = abs(correlation_coef)
            if abs_corr >= 0.7:
                strength = 'strong'
            elif abs_corr >= 0.4:
                strength = 'moderate'
            else:
                strength = 'weak'
            
            direction = 'positive' if correlation_coef > 0 else 'negative'
            
            if abs_corr >= self.min_correlation and p_value < 0.05:
                return Correlation(
                    metric1='',
                    metric2='',
                    correlation_coefficient=correlation_coef,
                    p_value=p_value,
                    strength=strength,
                    direction=direction
                )
        
        except (ValueError, ZeroDivisionError):
            return None
        
        return None

    def find_correlations(
        self,
        metric_data: Dict[str, List[float]],
        target_metric: Optional[str] = None
    ) -> List[Correlation]:
        """Find correlations between metrics.
        
        Args:
            metric_data: Dictionary of metric name to series
            target_metric: Optional target metric to correlate against
            
        Returns:
            List of significant correlations
        """
        correlations = []
        
        metric_names = list(metric_data.keys())
        
        if target_metric:
            # Correlate all metrics against target
            target_series = metric_data.get(target_metric, [])
            
            for metric_name in metric_names:
                if metric_name == target_metric:
                    continue
                
                corr = self.calculate_correlation(target_series, metric_data[metric_name])
                
                if corr:
                    corr.metric1 = target_metric
                    corr.metric2 = metric_name
                    correlations.append(corr)
        else:
            # Find all pairwise correlations
            for i, metric1 in enumerate(metric_names):
                for metric2 in metric_names[i+1:]:
                    corr = self.calculate_correlation(
                        metric_data[metric1],
                        metric_data[metric2]
                    )
                    
                    if corr:
                        corr.metric1 = metric1
                        corr.metric2 = metric2
                        correlations.append(corr)
        
        # Sort by absolute correlation coefficient
        correlations.sort(key=lambda c: abs(c.correlation_coefficient), reverse=True)
        
        return correlations

    def detect_leading_indicator(
        self,
        leading_series: List[float],
        lagging_series: List[float],
        max_lag: int = 7
    ) -> Optional[Tuple[int, float]]:
        """Detect if one metric is a leading indicator of another.
        
        Args:
            leading_series: Potential leading indicator series
            lagging_series: Lagging series
            max_lag: Maximum lag to test
            
        Returns:
            Tuple of (optimal_lag, correlation) if found, None otherwise
        """
        if len(leading_series) < max_lag + 3 or len(lagging_series) < max_lag + 3:
            return None
        
        best_lag = 0
        best_corr = 0
        
        for lag in range(1, min(max_lag + 1, len(leading_series))):
            if lag >= len(lagging_series):
                break
            
            # Correlate leading[:-lag] with lagging[lag:]
            lead = leading_series[:-lag]
            lag_series = lagging_series[lag:]
            
            if len(lead) != len(lag_series):
                continue
            
            corr = self.calculate_correlation(lead, lag_series)
            
            if corr and abs(corr.correlation_coefficient) > abs(best_corr):
                best_corr = corr.correlation_coefficient
                best_lag = lag
        
        if abs(best_corr) >= self.min_correlation:
            return (best_lag, best_corr)
        
        return None

    def analyze_metric_impact(
        self,
        independent_metric: List[float],
        dependent_metric: List[float],
        change_threshold: float = 0.2
    ) -> Optional[Dict[str, any]]:
        """Analyze impact of changes in one metric on another.
        
        Args:
            independent_metric: Independent variable series
            dependent_metric: Dependent variable series
            change_threshold: Threshold for significant change
            
        Returns:
            Impact analysis dict if significant, None otherwise
        """
        if len(independent_metric) != len(dependent_metric) or len(independent_metric) < 5:
            return None
        
        # Find periods of significant change in independent metric
        impacts = []
        
        for i in range(1, len(independent_metric)):
            if independent_metric[i-1] == 0:
                continue
            
            change_pct = (independent_metric[i] - independent_metric[i-1]) / independent_metric[i-1]
            
            if abs(change_pct) >= change_threshold:
                # Check impact on dependent metric
                if i < len(dependent_metric) and dependent_metric[i-1] != 0:
                    dep_change_pct = (dependent_metric[i] - dependent_metric[i-1]) / dependent_metric[i-1]
                    
                    impacts.append({
                        'period': i,
                        'independent_change': change_pct,
                        'dependent_change': dep_change_pct,
                        'impact_ratio': dep_change_pct / change_pct if change_pct != 0 else 0
                    })
        
        if impacts:
            avg_impact_ratio = statistics.mean([imp['impact_ratio'] for imp in impacts])
            
            return {
                'impact_count': len(impacts),
                'average_impact_ratio': avg_impact_ratio,
                'impacts': impacts,
                'correlation': 'positive' if avg_impact_ratio > 0 else 'negative'
            }
        
        return None

    def identify_confounding_factors(
        self,
        target_metric: List[float],
        potential_factors: Dict[str, List[float]]
    ) -> List[Dict[str, any]]:
        """Identify potential confounding factors affecting target metric.
        
        Args:
            target_metric: Target metric series
            potential_factors: Dict of factor name to series
            
        Returns:
            List of identified confounding factors
        """
        confounders = []
        
        for factor_name, factor_series in potential_factors.items():
            corr = self.calculate_correlation(target_metric, factor_series)
            
            if corr and abs(corr.correlation_coefficient) >= 0.6:
                # Check for lag
                lag_result = self.detect_leading_indicator(factor_series, target_metric)
                
                confounders.append({
                    'factor': factor_name,
                    'correlation': corr.correlation_coefficient,
                    'strength': corr.strength,
                    'p_value': corr.p_value,
                    'has_lag': lag_result is not None,
                    'lag_days': lag_result[0] if lag_result else 0
                })
        
        # Sort by correlation strength
        confounders.sort(key=lambda c: abs(c['correlation']), reverse=True)
        
        return confounders

    def calculate_variance_explained(
        self,
        independent_metrics: Dict[str, List[float]],
        dependent_metric: List[float]
    ) -> Dict[str, float]:
        """Calculate variance explained by each independent metric.
        
        Args:
            independent_metrics: Dict of metric name to series
            dependent_metric: Dependent metric series
            
        Returns:
            Dict of metric name to R-squared value
        """
        r_squared_values = {}
        
        for metric_name, metric_series in independent_metrics.items():
            if len(metric_series) != len(dependent_metric):
                continue
            
            # Simple linear regression R-squared
            try:
                x = np.array(metric_series)
                y = np.array(dependent_metric)
                
                # Remove NaN
                mask = ~np.isnan(x) & ~np.isnan(y)
                x = x[mask]
                y = y[mask]
                
                if len(x) < 3:
                    continue
                
                # Calculate R-squared
                coeffs = np.polyfit(x, y, 1)
                y_pred = coeffs[0] * x + coeffs[1]
                
                ss_res = np.sum((y - y_pred) ** 2)
                ss_tot = np.sum((y - np.mean(y)) ** 2)
                
                r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
                
                r_squared_values[metric_name] = max(0, r_squared)
            
            except (ValueError, ZeroDivisionError):
                continue
        
        return r_squared_values

    def _t_cdf(self, t: float, df: int) -> float:
        """Approximate t-distribution CDF.
        
        Args:
            t: t-statistic
            df: degrees of freedom
            
        Returns:
            Approximate CDF value
        """
        # Simple approximation using normal distribution for df > 30
        if df > 30:
            return 0.5 * (1 + np.tanh(t / np.sqrt(2)))
        
        # For smaller df, use a rough approximation
        x = df / (df + t**2)
        return 0.5 + 0.5 * np.sign(t) * (1 - x**(df/2))

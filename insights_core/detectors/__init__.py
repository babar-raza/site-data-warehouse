"""
Insight Detectors
"""
from insights_core.detectors.base import BaseDetector
from insights_core.detectors.anomaly import AnomalyDetector
from insights_core.detectors.cannibalization import CannibalizationDetector
from insights_core.detectors.content_quality import ContentQualityDetector
from insights_core.detectors.cwv_quality import CWVQualityDetector
from insights_core.detectors.diagnosis import DiagnosisDetector
from insights_core.detectors.opportunity import OpportunityDetector
from insights_core.detectors.topic_strategy import TopicStrategyDetector
from insights_core.detectors.trend import TrendDetector

__all__ = [
    "BaseDetector",
    "AnomalyDetector",
    "CannibalizationDetector",
    "ContentQualityDetector",
    "CWVQualityDetector",
    "DiagnosisDetector",
    "OpportunityDetector",
    "TopicStrategyDetector",
    "TrendDetector",
]

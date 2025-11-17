"""
Insight Detectors
"""
from insights_core.detectors.base import BaseDetector
from insights_core.detectors.anomaly import AnomalyDetector
from insights_core.detectors.diagnosis import DiagnosisDetector
from insights_core.detectors.opportunity import OpportunityDetector

__all__ = [
    "BaseDetector",
    "AnomalyDetector",
    "DiagnosisDetector",
    "OpportunityDetector",
]

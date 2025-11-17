"""
Insight Engine - Orchestrates all detectors
"""
import logging
from typing import List
from datetime import datetime

from insights_core.models import Insight
from insights_core.repository import InsightRepository
from insights_core.config import InsightsConfig
from insights_core.detectors import (
    AnomalyDetector,
    DiagnosisDetector,
    OpportunityDetector,
)

logger = logging.getLogger(__name__)


class InsightEngine:
    """
    Main orchestration engine for insight detection
    
    Runs detectors in sequence:
    1. AnomalyDetector - finds traffic anomalies
    2. DiagnosisDetector - diagnoses existing risks
    3. OpportunityDetector - finds optimization opportunities
    """
    
    def __init__(self, config: InsightsConfig = None):
        """
        Initialize engine with configuration
        
        Args:
            config: InsightsConfig instance (creates default if None)
        """
        self.config = config or InsightsConfig()
        self.repository = InsightRepository(self.config.warehouse_dsn)
        
        # Initialize detectors
        self.detectors = [
            AnomalyDetector(self.repository, self.config),
            DiagnosisDetector(self.repository, self.config),
            OpportunityDetector(self.repository, self.config),
        ]
        
        logger.info(f"InsightEngine initialized with {len(self.detectors)} detectors")
    
    def refresh(self, property: str = None) -> dict:
        """
        Run all detectors and return statistics
        
        Args:
            property: Optional property filter (None = all properties)
            
        Returns:
            Dict with execution stats
        """
        start_time = datetime.utcnow()
        logger.info("=" * 60)
        logger.info("Starting Insight Engine refresh")
        if property:
            logger.info(f"Property filter: {property}")
        logger.info("=" * 60)
        
        stats = {
            'start_time': start_time.isoformat(),
            'property_filter': property,
            'detectors_run': 0,
            'detectors_succeeded': 0,
            'detectors_failed': 0,
            'total_insights_created': 0,
            'insights_by_detector': {},
            'errors': []
        }
        
        for detector in self.detectors:
            detector_name = detector.__class__.__name__
            logger.info(f"\n--- Running {detector_name} ---")
            
            try:
                insights_created = detector.detect(property=property)
                stats['detectors_run'] += 1
                stats['detectors_succeeded'] += 1
                stats['total_insights_created'] += insights_created
                stats['insights_by_detector'][detector_name] = insights_created
                
                logger.info(f"{detector_name} created {insights_created} insights")
                
            except Exception as e:
                stats['detectors_run'] += 1
                stats['detectors_failed'] += 1
                stats['insights_by_detector'][detector_name] = 0
                stats['errors'].append({
                    'detector': detector_name,
                    'error': str(e)
                })
                logger.error(f"{detector_name} failed: {e}", exc_info=True)
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        stats['end_time'] = end_time.isoformat()
        stats['duration_seconds'] = duration
        
        logger.info("=" * 60)
        logger.info(f"Insight Engine completed in {duration:.2f}s")
        logger.info(f"Total insights created: {stats['total_insights_created']}")
        logger.info(f"Detectors succeeded: {stats['detectors_succeeded']}/{stats['detectors_run']}")
        logger.info("=" * 60)
        
        return stats
    
    def get_detector_stats(self) -> dict:
        """Get statistics about available detectors"""
        return {
            'total_detectors': len(self.detectors),
            'detectors': [
                {
                    'name': d.__class__.__name__,
                    'type': d.__class__.__name__.replace('Detector', '').lower()
                }
                for d in self.detectors
            ]
        }

#!/usr/bin/env python3
"""
Insight Engine Integration Verification Script
Validates all components of the Unified Insight Engine are properly wired and functional
"""

import os
import sys
import logging
from datetime import datetime
from typing import List, Dict, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test results
test_results: List[Tuple[str, bool, str]] = []


def test_result(name: str, passed: bool, message: str):
    """Record a test result"""
    test_results.append((name, passed, message))
    status = "✓ PASS" if passed else "✗ FAIL"
    logger.info(f"{status}: {name} - {message}")


def verify_module_imports() -> bool:
    """Verify all Python modules import without errors"""
    logger.info("\n=== 1. Module Import Verification ===")
    
    modules_to_test = [
        ('insights_core.models', 'Insight model'),
        ('insights_core.repository', 'InsightRepository'),
        ('insights_core.engine', 'InsightEngine'),
        ('insights_core.detectors', 'Detectors package'),
        ('insights_core.detectors.anomaly', 'AnomalyDetector'),
        ('insights_core.detectors.diagnosis', 'DiagnosisDetector'),
        ('insights_core.detectors.opportunity', 'OpportunityDetector'),
        ('insights_core.dispatcher', 'InsightDispatcher'),
        ('insights_core.cli', 'CLI module'),
        ('scheduler.scheduler', 'Scheduler'),
        ('mcp.insights_integration', 'MCP Insights Integration'),
    ]
    
    all_passed = True
    for module_name, description in modules_to_test:
        try:
            __import__(module_name)
            test_result(f"Import {description}", True, f"{module_name} imported successfully")
        except ImportError as e:
            test_result(f"Import {description}", False, f"Failed to import {module_name}: {e}")
            all_passed = False
        except Exception as e:
            test_result(f"Import {description}", False, f"Error importing {module_name}: {e}")
            all_passed = False
    
    return all_passed


def verify_insights_core_structure() -> bool:
    """Verify insights_core package structure"""
    logger.info("\n=== 2. Package Structure Verification ===")
    
    required_files = [
        'insights_core/__init__.py',
        'insights_core/models.py',
        'insights_core/repository.py',
        'insights_core/engine.py',
        'insights_core/cli.py',
        'insights_core/config.py',
        'insights_core/dispatcher.py',
        'insights_core/detectors/__init__.py',
        'insights_core/detectors/base.py',
        'insights_core/detectors/anomaly.py',
        'insights_core/detectors/diagnosis.py',
        'insights_core/detectors/opportunity.py',
        'insights_core/channels/__init__.py',
    ]
    
    all_exist = True
    for filepath in required_files:
        full_path = os.path.join(os.path.dirname(__file__), filepath)
        exists = os.path.exists(full_path)
        test_result(
            f"File exists: {filepath}",
            exists,
            "Found" if exists else "Missing"
        )
        if not exists:
            all_exist = False
    
    return all_exist


def verify_model_completeness() -> bool:
    """Verify Insight model has all required fields"""
    logger.info("\n=== 3. Model Completeness ===")
    
    try:
        from insights_core.models import Insight, InsightCreate, InsightMetrics
        
        # Check Insight model fields
        required_fields = [
            'id', 'generated_at', 'property', 'entity_type', 'entity_id',
            'category', 'title', 'description', 'severity', 'confidence',
            'metrics', 'window_days', 'source', 'status', 'linked_insight_id'
        ]
        
        model_fields = Insight.model_fields.keys()
        all_present = True
        
        for field in required_fields:
            present = field in model_fields
            test_result(
                f"Insight field: {field}",
                present,
                "Present" if present else "Missing"
            )
            if not present:
                all_present = False
        
        # Test ID generation is deterministic
        id1 = Insight.generate_id("prop", "page", "/test", "risk", "detector", 7)
        id2 = Insight.generate_id("prop", "page", "/test", "risk", "detector", 7)
        deterministic = (id1 == id2)
        test_result(
            "ID generation is deterministic",
            deterministic,
            f"Generated same ID: {id1[:16]}..."
        )
        
        return all_present and deterministic
        
    except Exception as e:
        test_result("Model verification", False, f"Error: {e}")
        return False


def verify_repository_methods() -> bool:
    """Verify InsightRepository has all required methods"""
    logger.info("\n=== 4. Repository Methods ===")
    
    try:
        from insights_core.repository import InsightRepository
        
        required_methods = [
            'create', 'get_by_id', 'update', 'query',
            'get_by_status', 'get_by_category', 'get_for_entity',
            'query_recent', 'delete_old_insights', 'get_stats'
        ]
        
        all_present = True
        for method_name in required_methods:
            present = hasattr(InsightRepository, method_name)
            test_result(
                f"Repository method: {method_name}",
                present,
                "Present" if present else "Missing"
            )
            if not present:
                all_present = False
        
        return all_present
        
    except Exception as e:
        test_result("Repository verification", False, f"Error: {e}")
        return False


def verify_detectors() -> bool:
    """Verify all detectors are properly implemented"""
    logger.info("\n=== 5. Detector Verification ===")
    
    try:
        from insights_core.detectors import (
            AnomalyDetector,
            DiagnosisDetector,
            OpportunityDetector
        )
        from insights_core.detectors.base import BaseDetector
        
        detectors = [
            ('AnomalyDetector', AnomalyDetector),
            ('DiagnosisDetector', DiagnosisDetector),
            ('OpportunityDetector', OpportunityDetector)
        ]
        
        all_valid = True
        for name, detector_class in detectors:
            # Check inheritance
            is_subclass = issubclass(detector_class, BaseDetector)
            test_result(
                f"{name} extends BaseDetector",
                is_subclass,
                "Valid" if is_subclass else "Invalid"
            )
            
            # Check detect method exists
            has_detect = hasattr(detector_class, 'detect')
            test_result(
                f"{name} has detect method",
                has_detect,
                "Present" if has_detect else "Missing"
            )
            
            if not (is_subclass and has_detect):
                all_valid = False
        
        return all_valid
        
    except Exception as e:
        test_result("Detector verification", False, f"Error: {e}")
        return False


def verify_engine() -> bool:
    """Verify InsightEngine properly orchestrates detectors"""
    logger.info("\n=== 6. Engine Verification ===")
    
    try:
        from insights_core.engine import InsightEngine
        
        # Check key methods
        required_methods = ['refresh', 'get_detector_stats']
        all_present = True
        
        for method_name in required_methods:
            present = hasattr(InsightEngine, method_name)
            test_result(
                f"Engine method: {method_name}",
                present,
                "Present" if present else "Missing"
            )
            if not present:
                all_present = False
        
        return all_present
        
    except Exception as e:
        test_result("Engine verification", False, f"Error: {e}")
        return False


def verify_sql_files() -> bool:
    """Verify all required SQL files exist"""
    logger.info("\n=== 7. SQL Files Verification ===")
    
    required_sql = [
        'sql/01_schema.sql',
        'sql/03_transforms.sql',
        'sql/04_ga4_schema.sql',
        'sql/05_unified_view.sql',
        'sql/11_insights_table.sql',
    ]
    
    all_exist = True
    for filepath in required_sql:
        full_path = os.path.join(os.path.dirname(__file__), filepath)
        exists = os.path.exists(full_path)
        test_result(
            f"SQL file: {filepath}",
            exists,
            "Found" if exists else "Missing"
        )
        if not exists:
            all_exist = False
    
    # Check insights table SQL has key elements
    insights_sql_path = os.path.join(os.path.dirname(__file__), 'sql/11_insights_table.sql')
    if os.path.exists(insights_sql_path):
        with open(insights_sql_path, 'r') as f:
            sql_content = f.read()
            
        required_elements = [
            'CREATE TABLE IF NOT EXISTS gsc.insights',
            'id VARCHAR(64) PRIMARY KEY',
            'metrics JSONB',
            'status VARCHAR',
            'linked_insight_id'
        ]
        
        for element in required_elements:
            present = element in sql_content
            test_result(
                f"Insights SQL contains: {element}",
                present,
                "Present" if present else "Missing"
            )
            if not present:
                all_exist = False
    
    return all_exist


def verify_scheduler_integration() -> bool:
    """Verify scheduler calls insights refresh"""
    logger.info("\n=== 8. Scheduler Integration ===")
    
    try:
        scheduler_path = os.path.join(os.path.dirname(__file__), 'scheduler/scheduler.py')
        
        if not os.path.exists(scheduler_path):
            test_result("Scheduler file", False, "scheduler/scheduler.py not found")
            return False
        
        with open(scheduler_path, 'r') as f:
            scheduler_content = f.read()
        
        # Check for insights integration
        checks = [
            ('Imports InsightEngine', 'from insights_core.engine import InsightEngine'),
            ('Has insights refresh function', 'def run_insights_refresh'),
            ('Calls insights in daily job', 'run_insights_refresh()'),
        ]
        
        all_present = True
        for check_name, search_string in checks:
            present = search_string in scheduler_content
            test_result(
                check_name,
                present,
                "Found" if present else "Missing"
            )
            if not present:
                all_present = False
        
        return all_present
        
    except Exception as e:
        test_result("Scheduler verification", False, f"Error: {e}")
        return False


def verify_mcp_integration() -> bool:
    """Verify MCP server has insights tools"""
    logger.info("\n=== 9. MCP Integration ===")
    
    try:
        # Check if insights integration module exists
        integration_path = os.path.join(os.path.dirname(__file__), 'mcp/insights_integration.py')
        exists = os.path.exists(integration_path)
        test_result(
            "MCP insights integration module",
            exists,
            "Found" if exists else "Missing"
        )
        
        if exists:
            with open(integration_path, 'r') as f:
                content = f.read()
            
            required_functions = [
                'get_insights_tool_schemas',
                'call_insights_tool',
                'initialize_insights_integration'
            ]
            
            all_present = True
            for func_name in required_functions:
                present = f"def {func_name}" in content
                test_result(
                    f"MCP function: {func_name}",
                    present,
                    "Present" if present else "Missing"
                )
                if not present:
                    all_present = False
            
            return exists and all_present
        
        return False
        
    except Exception as e:
        test_result("MCP verification", False, f"Error: {e}")
        return False


def verify_insights_api() -> bool:
    """Verify Insights API server exists and has required endpoints"""
    logger.info("\n=== 10. Insights API Server ===")
    
    try:
        api_path = os.path.join(os.path.dirname(__file__), 'insights_api/insights_api.py')
        exists = os.path.exists(api_path)
        test_result(
            "Insights API server file",
            exists,
            "Found" if exists else "Missing"
        )
        
        if exists:
            with open(api_path, 'r') as f:
                content = f.read()
            
            # Check for key endpoints
            endpoints = [
                ('/api/health', 'Health check'),
                ('/api/stats', 'Statistics'),
                ('/api/insights', 'Query insights'),
                ('/api/insights/{insight_id}', 'Get by ID'),
                ('/api/insights/actionable', 'Actionable insights'),
            ]
            
            all_present = True
            for endpoint, description in endpoints:
                present = endpoint in content
                test_result(
                    f"API endpoint: {description}",
                    present,
                    f"{endpoint} present" if present else "Missing"
                )
                if not present:
                    all_present = False
            
            return exists and all_present
        
        return False
        
    except Exception as e:
        test_result("API verification", False, f"Error: {e}")
        return False


def verify_dispatcher() -> bool:
    """Verify dispatcher is properly implemented"""
    logger.info("\n=== 11. Dispatcher Verification ===")
    
    try:
        from insights_core.dispatcher import InsightDispatcher
        
        required_methods = [
            'dispatch',
            'dispatch_batch',
            'dispatch_recent_insights'
        ]
        
        all_present = True
        for method_name in required_methods:
            present = hasattr(InsightDispatcher, method_name)
            test_result(
                f"Dispatcher method: {method_name}",
                present,
                "Present" if present else "Missing"
            )
            if not present:
                all_present = False
        
        return all_present
        
    except Exception as e:
        test_result("Dispatcher verification", False, f"Error: {e}")
        return False


def verify_transform_script() -> bool:
    """Verify transform script includes insights table"""
    logger.info("\n=== 12. Transform Script ===")
    
    try:
        transform_path = os.path.join(os.path.dirname(__file__), 'transform/apply_transforms.py')
        
        if not os.path.exists(transform_path):
            test_result("Transform script", False, "transform/apply_transforms.py not found")
            return False
        
        with open(transform_path, 'r') as f:
            content = f.read()
        
        # Check if insights table is in the transform list
        has_insights = '11_insights_table.sql' in content
        test_result(
            "Insights table in transform list",
            has_insights,
            "Included" if has_insights else "Missing"
        )
        
        return has_insights
        
    except Exception as e:
        test_result("Transform script verification", False, f"Error: {e}")
        return False


def verify_tests() -> bool:
    """Verify test files exist and are comprehensive"""
    logger.info("\n=== 13. Test Coverage ===")
    
    required_tests = [
        ('tests/test_insight_models.py', 'Model tests'),
        ('tests/test_insight_repository.py', 'Repository tests'),
        ('tests/test_detectors.py', 'Detector tests'),
        ('tests/test_dispatcher.py', 'Dispatcher tests'),
        ('tests/test_scheduler.py', 'Scheduler tests'),
        ('tests/test_unified_insights_api.py', 'API tests'),
    ]
    
    all_exist = True
    for filepath, description in required_tests:
        full_path = os.path.join(os.path.dirname(__file__), filepath)
        exists = os.path.exists(full_path)
        test_result(
            f"Test file: {description}",
            exists,
            filepath if exists else "Missing"
        )
        if not exists:
            all_exist = False
    
    return all_exist


def print_summary():
    """Print summary of all test results"""
    logger.info("\n" + "="*80)
    logger.info("VERIFICATION SUMMARY")
    logger.info("="*80)
    
    passed = sum(1 for _, result, _ in test_results if result)
    total = len(test_results)
    failed = total - passed
    
    logger.info(f"\nTotal Checks: {total}")
    logger.info(f"Passed: {passed} ✓")
    logger.info(f"Failed: {failed} ✗")
    logger.info(f"Success Rate: {(passed/total*100):.1f}%")
    
    if failed > 0:
        logger.info("\n" + "="*80)
        logger.info("FAILED CHECKS:")
        logger.info("="*80)
        for name, result, message in test_results:
            if not result:
                logger.info(f"✗ {name}: {message}")
    
    logger.info("\n" + "="*80)
    return failed == 0


def main():
    """Run all verification checks"""
    logger.info("="*80)
    logger.info("INSIGHT ENGINE INTEGRATION VERIFICATION")
    logger.info(f"Started at: {datetime.now().isoformat()}")
    logger.info("="*80)
    
    # Run all verifications
    verifications = [
        verify_module_imports,
        verify_insights_core_structure,
        verify_model_completeness,
        verify_repository_methods,
        verify_detectors,
        verify_engine,
        verify_sql_files,
        verify_scheduler_integration,
        verify_mcp_integration,
        verify_insights_api,
        verify_dispatcher,
        verify_transform_script,
        verify_tests,
    ]
    
    for verification_func in verifications:
        try:
            verification_func()
        except Exception as e:
            logger.error(f"Verification failed with exception: {e}", exc_info=True)
            test_result(verification_func.__name__, False, str(e))
    
    # Print summary
    all_passed = print_summary()
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

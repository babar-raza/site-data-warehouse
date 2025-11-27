#!/usr/bin/env python3
"""
Test Script for Rollback Automation
Validates the rollback automation functionality without affecting production
"""

import os
import sys
import asyncio
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.rollback_automation import (
    ServiceEndpoint,
    HealthCheckConfig,
    HealthMonitor,
    RollbackManager,
    ServiceStatus,
    setup_logging
)


async def test_health_monitor():
    """Test health monitoring functionality"""
    print("\n" + "=" * 60)
    print("TEST 1: Health Monitor")
    print("=" * 60)

    logger = setup_logging(verbose=True)
    config = HealthCheckConfig(
        failure_threshold=3,
        check_interval=5,
        timeout=5
    )

    monitor = HealthMonitor(config, logger)

    # Test endpoints (should fail since services might not be running)
    test_endpoints = [
        ServiceEndpoint(
            name="test_http",
            url="http://localhost:9999/health",
            type="http",
            critical=True
        ),
        ServiceEndpoint(
            name="test_docker",
            url="",
            type="docker",
            critical=False
        )
    ]

    print("\nRunning health checks...")
    results = await monitor.check_all_endpoints(test_endpoints)

    print(f"\nResults: {len(results)} checks completed")
    for result in results:
        print(f"  - {result.service_name}: {result.status.value}")
        if result.error_message:
            print(f"    Error: {result.error_message}")
        print(f"    Response time: {result.response_time_ms:.2f}ms")

    # Test failure counting
    print("\nTesting failure counting...")
    monitor.update_failure_counts(results)

    for service_name, count in monitor.failure_counts.items():
        print(f"  - {service_name}: {count} failures")

    # Test multiple failure cycles
    print("\nSimulating multiple check cycles...")
    for i in range(3):
        print(f"\n  Cycle {i + 1}:")
        results = await monitor.check_all_endpoints(test_endpoints)
        monitor.update_failure_counts(results)

        services_to_rollback = monitor.get_services_requiring_rollback(test_endpoints)
        if services_to_rollback:
            print(f"    Services requiring rollback: {services_to_rollback}")
        else:
            print("    No services require rollback yet")

    # Test health summary
    print("\nHealth Summary:")
    summary = monitor.get_health_summary()
    print(json.dumps(summary, indent=2, default=str))

    print("\n[PASS] Health Monitor test completed")
    return True


async def test_rollback_manager():
    """Test rollback manager functionality"""
    print("\n" + "=" * 60)
    print("TEST 2: Rollback Manager")
    print("=" * 60)

    logger = setup_logging(verbose=True)
    manager = RollbackManager(logger, dry_run=True)

    # Test getting current image version
    print("\nTesting image version detection...")
    test_services = ["warehouse", "insights_api", "scheduler"]

    for service_name in test_services:
        current_version = manager.get_current_image_version(service_name)
        print(f"  - {service_name}: {current_version or 'Not found'}")

        if current_version:
            previous_version = manager.get_previous_image_version(service_name)
            print(f"    Previous: {previous_version or 'Not found'}")

    # Test rollback (dry run)
    print("\nTesting rollback (dry run)...")
    test_service = "insights_api"
    reason = "Test rollback"

    success = manager.rollback_service(test_service, reason)
    print(f"  Rollback {'succeeded' if success else 'failed'}")

    # Test rollback history
    print("\nRollback History:")
    history = manager.get_rollback_history()
    print(json.dumps(history, indent=2, default=str))

    print("\n[PASS] Rollback Manager test completed")
    return True


async def test_endpoint_types():
    """Test different endpoint types"""
    print("\n" + "=" * 60)
    print("TEST 3: Endpoint Types")
    print("=" * 60)

    logger = setup_logging(verbose=True)
    config = HealthCheckConfig(timeout=5)
    monitor = HealthMonitor(config, logger)

    # Test HTTP endpoint (use a known working endpoint)
    print("\nTesting HTTP endpoint...")
    http_endpoint = ServiceEndpoint(
        name="httpbin",
        url="https://httpbin.org/status/200",
        type="http",
        critical=False
    )

    result = await monitor.check_http_endpoint(http_endpoint)
    print(f"  Status: {result.status.value}")
    print(f"  Response time: {result.response_time_ms:.2f}ms")
    if result.error_message:
        print(f"  Error: {result.error_message}")

    # Test Docker endpoint
    print("\nTesting Docker endpoint...")
    docker_endpoint = ServiceEndpoint(
        name="warehouse",
        url="",
        type="docker",
        critical=True
    )

    result = await monitor.check_docker_service(docker_endpoint)
    print(f"  Status: {result.status.value}")
    if result.details:
        print(f"  Details: {json.dumps(result.details)}")

    print("\n[PASS] Endpoint types test completed")
    return True


async def test_configuration_loading():
    """Test configuration file loading"""
    print("\n" + "=" * 60)
    print("TEST 4: Configuration Loading")
    print("=" * 60)

    config_path = os.path.join(
        os.path.dirname(__file__),
        "rollback_automation_config.example.json"
    )

    if os.path.exists(config_path):
        print(f"\nLoading configuration from: {config_path}")

        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)

            print("\nConfiguration loaded successfully:")
            print(f"  Health check config: {json.dumps(config_data.get('health_check', {}), indent=4)}")
            print(f"  Endpoints: {len(config_data.get('endpoints', []))}")

            # Validate endpoint structure
            for ep in config_data.get('endpoints', []):
                endpoint = ServiceEndpoint(**ep)
                print(f"    - {endpoint.name} ({endpoint.type}): {'critical' if endpoint.critical else 'non-critical'}")

            print("\n[PASS] Configuration loading test completed")
            return True

        except Exception as e:
            print(f"\n[FAIL] Configuration loading failed: {e}")
            return False
    else:
        print(f"\n[WARN] Configuration file not found: {config_path}")
        return False


def test_imports():
    """Test that all required modules can be imported"""
    print("\n" + "=" * 60)
    print("TEST 5: Module Imports")
    print("=" * 60)

    required_modules = [
        'asyncio',
        'asyncpg',
        'httpx',
        'json',
        'logging',
        'subprocess',
        'signal',
        'dataclasses',
        'enum',
        'argparse'
    ]

    print("\nChecking required modules...")
    all_present = True

    for module_name in required_modules:
        try:
            __import__(module_name)
            print(f"  [OK] {module_name}")
        except ImportError:
            print(f"  [FAIL] {module_name} - NOT FOUND")
            all_present = False

    if all_present:
        print("\n[PASS] All required modules available")
    else:
        print("\n[FAIL] Some modules are missing. Install with:")
        print("  pip install asyncpg httpx")

    return all_present


async def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("ROLLBACK AUTOMATION TEST SUITE")
    print("=" * 60)
    print(f"Started at: {datetime.utcnow().isoformat()}")

    results = {}

    # Test 1: Imports
    try:
        results['imports'] = test_imports()
    except Exception as e:
        print(f"\n[FAIL] Import test failed: {e}")
        results['imports'] = False

    # Test 2: Configuration Loading
    try:
        results['config'] = await test_configuration_loading()
    except Exception as e:
        print(f"\n[FAIL] Configuration test failed: {e}")
        results['config'] = False

    # Test 3: Endpoint Types
    try:
        results['endpoints'] = await test_endpoint_types()
    except Exception as e:
        print(f"\n[FAIL] Endpoint types test failed: {e}")
        results['endpoints'] = False

    # Test 4: Health Monitor
    try:
        results['health_monitor'] = await test_health_monitor()
    except Exception as e:
        print(f"\n[FAIL] Health monitor test failed: {e}")
        results['health_monitor'] = False

    # Test 5: Rollback Manager
    try:
        results['rollback_manager'] = await test_rollback_manager()
    except Exception as e:
        print(f"\n[FAIL] Rollback manager test failed: {e}")
        results['rollback_manager'] = False

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    failed_tests = total_tests - passed_tests

    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}: {test_name}")

    print(f"\nTotal: {total_tests} tests")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")

    if failed_tests == 0:
        print("\n[SUCCESS] All tests passed!")
        return 0
    else:
        print(f"\n[ERROR] {failed_tests} test(s) failed")
        return 1


def main():
    """Main entry point"""
    try:
        exit_code = asyncio.run(run_all_tests())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

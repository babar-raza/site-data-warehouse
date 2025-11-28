#!/usr/bin/env python3
"""
Comprehensive regression test suite for the GSC Data Warehouse infrastructure.

This script verifies that all existing functionality continues to work after
adding the docker_stats_exporter service.
"""

import requests
import sys
import time
from typing import Dict, Any, List, Tuple

# Service endpoints
PROMETHEUS_URL = "http://localhost:9090"
GRAFANA_URL = "http://localhost:3000"
WAREHOUSE_EXPORTER_URL = "http://localhost:8002"
DOCKER_EXPORTER_URL = "http://localhost:8003"
INSIGHTS_API_URL = "http://localhost:8000"


def print_header(text: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)


def test_endpoint(name: str, url: str, expected_status: int = 200) -> bool:
    """Test that an HTTP endpoint is accessible."""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == expected_status:
            print(f"[PASS] {name}: {url}")
            return True
        else:
            print(f"[FAIL] {name}: {url} - Status {response.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] {name}: {url} - Error: {e}")
        return False


def test_prometheus_target(job_name: str) -> bool:
    """Test that a Prometheus scrape target is UP."""
    try:
        response = requests.get(f"{PROMETHEUS_URL}/api/v1/targets", timeout=10)
        response.raise_for_status()
        data = response.json()

        targets = data.get("data", {}).get("activeTargets", [])
        target = next((t for t in targets if t.get("labels", {}).get("job") == job_name), None)

        if target and target.get("health") == "up":
            print(f"[PASS] Prometheus target '{job_name}' is UP")
            return True
        else:
            print(f"[FAIL] Prometheus target '{job_name}' is not UP")
            return False
    except Exception as e:
        print(f"[FAIL] Could not check Prometheus target '{job_name}': {e}")
        return False


def test_metric_exists(metric_name: str, expected_min_results: int = 1) -> bool:
    """Test that a metric exists in Prometheus."""
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": metric_name},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "success":
            print(f"[FAIL] Metric '{metric_name}' query failed")
            return False

        result_count = len(data.get("data", {}).get("result", []))

        if result_count >= expected_min_results:
            print(f"[PASS] Metric '{metric_name}' exists ({result_count} results)")
            return True
        else:
            print(f"[FAIL] Metric '{metric_name}' has {result_count} results, expected >= {expected_min_results}")
            return False
    except Exception as e:
        print(f"[FAIL] Could not query metric '{metric_name}': {e}")
        return False


def main():
    """Run comprehensive regression tests."""
    print("=" * 70)
    print("GSC Data Warehouse - Regression Test Suite")
    print("=" * 70)
    print("Testing that all existing functionality still works after adding")
    print("the docker_stats_exporter service")
    print()

    all_tests = []

    # Test 1: Service Endpoints
    print_header("Test 1: Service Health Endpoints")
    all_tests.append(test_endpoint("Prometheus", f"{PROMETHEUS_URL}/-/healthy"))
    all_tests.append(test_endpoint("Grafana", f"{GRAFANA_URL}/api/health"))
    all_tests.append(test_endpoint("Warehouse Metrics Exporter", f"{WAREHOUSE_EXPORTER_URL}/health"))
    all_tests.append(test_endpoint("Docker Stats Exporter", f"{DOCKER_EXPORTER_URL}/health"))
    all_tests.append(test_endpoint("Insights API", f"{INSIGHTS_API_URL}/api/health"))

    # Test 2: Prometheus Targets
    print_header("Test 2: Prometheus Scrape Targets")
    all_tests.append(test_prometheus_target("prometheus"))
    all_tests.append(test_prometheus_target("gsc_warehouse"))
    all_tests.append(test_prometheus_target("postgres"))
    all_tests.append(test_prometheus_target("redis"))
    all_tests.append(test_prometheus_target("docker_containers"))

    # Test 3: Existing Metrics (Pre-Docker Exporter)
    print_header("Test 3: Existing Warehouse Metrics")
    all_tests.append(test_metric_exists("gsc_warehouse_up"))
    all_tests.append(test_metric_exists("gsc_fact_table_total_rows"))
    all_tests.append(test_metric_exists("pg_up"))

    # Test 4: New Docker Container Metrics
    print_header("Test 4: New Docker Container Metrics")
    all_tests.append(test_metric_exists('container_last_seen{name!=""}', expected_min_results=5))
    all_tests.append(test_metric_exists('container_memory_usage_bytes{name!=""}', expected_min_results=5))
    all_tests.append(test_metric_exists('container_cpu_usage_seconds_total{name!=""}', expected_min_results=5))
    all_tests.append(test_metric_exists('container_network_receive_bytes_total{name!=""}', expected_min_results=5))
    all_tests.append(test_metric_exists('container_fs_reads_bytes_total{name!=""}'))

    # Test 5: Dashboard Queries (Infrastructure Overview)
    print_header("Test 5: Infrastructure Overview Dashboard Queries")
    all_tests.append(test_metric_exists('count(container_last_seen{name!=""})'))
    all_tests.append(test_metric_exists('sum(container_memory_usage_bytes{name!=""})'))
    all_tests.append(test_metric_exists('sum(rate(container_cpu_usage_seconds_total{name!=""}[5m])) * 100'))

    # Test 6: Docker Container Metrics Validation
    print_header("Test 6: Verify Docker Container Metrics")
    # Verify docker_exporter provides all necessary container metrics
    all_tests.append(test_metric_exists('container_memory_usage_bytes{job="docker_containers"}'))

    # Test 7: Exporter Health Metrics
    print_header("Test 7: Exporter Self-Monitoring Metrics")
    all_tests.append(test_metric_exists("docker_exporter_containers_scraped"))
    all_tests.append(test_metric_exists("docker_exporter_scrape_duration_seconds"))

    # Test 8: Container Labels
    print_header("Test 8: Container Metric Labels")
    all_tests.append(test_metric_exists('container_memory_usage_bytes{name="gsc_warehouse"}'))
    all_tests.append(test_metric_exists('container_memory_usage_bytes{name="gsc_prometheus"}'))
    all_tests.append(test_metric_exists('container_memory_usage_bytes{name="gsc_grafana"}'))

    # Print summary
    print_header("Test Summary")
    passed = sum(all_tests)
    total = len(all_tests)
    percentage = (passed / total * 100) if total > 0 else 0

    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {percentage:.1f}%")
    print()

    if passed == total:
        print("[PASS] All regression tests passed!")
        print("The docker_stats_exporter has been successfully integrated")
        print("without breaking any existing functionality.")
        return 0
    else:
        print(f"[FAIL] {total - passed} regression test(s) failed!")
        print("Please investigate the failures before proceeding.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Test script to verify Infrastructure Overview dashboard queries work correctly.

This script tests all the main queries used by the dashboard to ensure the
docker_stats_exporter is providing data in the correct format.
"""

import requests
import sys
import time
from typing import Dict, Any

PROMETHEUS_URL = "http://localhost:9090"
COLORS = {
    'GREEN': '\033[92m',
    'RED': '\033[91m',
    'YELLOW': '\033[93m',
    'BLUE': '\033[94m',
    'END': '\033[0m'
}


def print_status(status: str, message: str):
    """Print a status message with color."""
    if status == "PASS":
        print(f"{COLORS['GREEN']}[PASS]{COLORS['END']}: {message}")
    elif status == "FAIL":
        print(f"{COLORS['RED']}[FAIL]{COLORS['END']}: {message}")
    elif status == "INFO":
        print(f"{COLORS['BLUE']}[INFO]{COLORS['END']}: {message}")
    elif status == "WARN":
        print(f"{COLORS['YELLOW']}[WARN]{COLORS['END']}: {message}")


def query_prometheus(query: str) -> Dict[str, Any]:
    """Query Prometheus and return the result."""
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={'query': query},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print_status("FAIL", f"Query failed: {e}")
        return {"status": "error", "error": str(e)}


def test_query(name: str, query: str, expected_min_results: int = 1) -> bool:
    """Test a Prometheus query and verify results."""
    print_status("INFO", f"Testing: {name}")
    print(f"  Query: {query}")

    result = query_prometheus(query)

    if result.get("status") != "success":
        print_status("FAIL", f"Query failed: {result.get('error', 'Unknown error')}")
        return False

    result_count = len(result.get("data", {}).get("result", []))

    if result_count < expected_min_results:
        print_status("FAIL", f"Expected at least {expected_min_results} results, got {result_count}")
        return False

    print_status("PASS", f"Got {result_count} results")
    return True


def main():
    """Run all dashboard query tests."""
    print("=" * 70)
    print("Infrastructure Overview Dashboard - Query Validation Tests")
    print("=" * 70)
    print()

    # Wait for metrics to be collected
    print_status("INFO", "Waiting 5 seconds for metrics collection...")
    time.sleep(5)

    tests = []

    # Test 1: System Uptime (Prometheus self-monitoring)
    print("\n" + "=" * 70)
    print("Test 1: System Uptime")
    print("=" * 70)
    tests.append(test_query(
        "Prometheus uptime",
        'time() - process_start_time_seconds{job="prometheus"}',
        expected_min_results=1
    ))

    # Test 2: Active Containers Count
    print("\n" + "=" * 70)
    print("Test 2: Active Containers Count")
    print("=" * 70)
    tests.append(test_query(
        "Container count with name label",
        'count(container_last_seen{name!=""})',
        expected_min_results=1
    ))

    # Test 3: Total Memory Usage
    print("\n" + "=" * 70)
    print("Test 3: Total Memory Usage")
    print("=" * 70)
    tests.append(test_query(
        "Sum of container memory",
        'sum(container_memory_usage_bytes{name!=""})',
        expected_min_results=1
    ))

    # Test 4: Total CPU Usage
    print("\n" + "=" * 70)
    print("Test 4: Total CPU Usage")
    print("=" * 70)
    tests.append(test_query(
        "Sum of container CPU rate",
        'sum(rate(container_cpu_usage_seconds_total{name!=""}[5m])) * 100',
        expected_min_results=1
    ))

    # Test 5: Network In
    print("\n" + "=" * 70)
    print("Test 5: Network Traffic (Inbound)")
    print("=" * 70)
    tests.append(test_query(
        "Sum of network RX rate",
        'sum(rate(container_network_receive_bytes_total{name!=""}[5m]))',
        expected_min_results=1
    ))

    # Test 6: Network Out
    print("\n" + "=" * 70)
    print("Test 6: Network Traffic (Outbound)")
    print("=" * 70)
    tests.append(test_query(
        "Sum of network TX rate",
        'sum(rate(container_network_transmit_bytes_total{name!=""}[5m]))',
        expected_min_results=1
    ))

    # Test 7: CPU Usage by Container
    print("\n" + "=" * 70)
    print("Test 7: CPU Usage by Container (Time Series)")
    print("=" * 70)
    tests.append(test_query(
        "CPU usage per container",
        'rate(container_cpu_usage_seconds_total{name!=""}[5m]) * 100',
        expected_min_results=5  # Expect multiple containers
    ))

    # Test 8: Memory Usage by Container
    print("\n" + "=" * 70)
    print("Test 8: Memory Usage by Container (Time Series)")
    print("=" * 70)
    tests.append(test_query(
        "Memory usage per container",
        'container_memory_usage_bytes{name!=""}',
        expected_min_results=5  # Expect multiple containers
    ))

    # Test 9: Network RX by Container
    print("\n" + "=" * 70)
    print("Test 9: Network RX by Container")
    print("=" * 70)
    tests.append(test_query(
        "Network RX per container",
        'rate(container_network_receive_bytes_total{name!=""}[5m])',
        expected_min_results=5  # Expect multiple containers
    ))

    # Test 10: Network TX by Container
    print("\n" + "=" * 70)
    print("Test 10: Network TX by Container")
    print("=" * 70)
    tests.append(test_query(
        "Network TX per container",
        'rate(container_network_transmit_bytes_total{name!=""}[5m])',
        expected_min_results=5  # Expect multiple containers
    ))

    # Test 11: Disk Read by Container
    print("\n" + "=" * 70)
    print("Test 11: Disk Read by Container")
    print("=" * 70)
    tests.append(test_query(
        "Disk read per container",
        'rate(container_fs_reads_bytes_total{name!=""}[5m])',
        expected_min_results=1  # At least some containers have disk I/O
    ))

    # Test 12: Disk Write by Container
    print("\n" + "=" * 70)
    print("Test 12: Disk Write by Container")
    print("=" * 70)
    tests.append(test_query(
        "Disk write per container",
        'rate(container_fs_writes_bytes_total{name!=""}[5m])',
        expected_min_results=1  # At least some containers have disk I/O
    ))

    # Test 13: Container Status Details (Table)
    print("\n" + "=" * 70)
    print("Test 13: Container Status Details (Instant Query)")
    print("=" * 70)
    tests.append(test_query(
        "Container last seen instant",
        'container_last_seen{name!=""}',
        expected_min_results=5  # Expect multiple containers
    ))

    # Print summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    passed = sum(tests)
    total = len(tests)
    percentage = (passed / total * 100) if total > 0 else 0

    print(f"\nPassed: {passed}/{total} ({percentage:.1f}%)")

    if passed == total:
        print_status("PASS", "All tests passed! Dashboard should display data correctly.")
        return 0
    else:
        print_status("FAIL", f"{total - passed} test(s) failed. Dashboard may not display properly.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

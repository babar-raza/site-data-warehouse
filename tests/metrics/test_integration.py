#!/usr/bin/env python3
"""
Integration tests for metrics exporter
Run these tests against a running metrics exporter
"""
import requests
import sys
import time


def test_metrics_endpoint():
    """Test that metrics endpoint is accessible"""
    print("Testing metrics endpoint...")
    try:
        response = requests.get("http://localhost:9090/metrics", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Metrics endpoint accessible")
        return True
    except Exception as e:
        print(f"✗ Metrics endpoint test failed: {e}")
        return False


def test_warehouse_up_metric():
    """Test that warehouse_up metric is present"""
    print("Testing warehouse_up metric...")
    try:
        response = requests.get("http://localhost:9090/metrics", timeout=5)
        text = response.text
        assert "gsc_warehouse_up" in text, "gsc_warehouse_up metric not found"
        print("✓ warehouse_up metric present")
        return True
    except Exception as e:
        print(f"✗ warehouse_up metric test failed: {e}")
        return False


def test_fact_table_metrics():
    """Test that fact table metrics are present"""
    print("Testing fact table metrics...")
    try:
        response = requests.get("http://localhost:9090/metrics", timeout=5)
        text = response.text
        assert "gsc_fact_table_total_rows" in text, "fact_table_total_rows metric not found"
        print("✓ Fact table metrics present")
        return True
    except Exception as e:
        print(f"✗ Fact table metrics test failed: {e}")
        return False


def test_prometheus_format():
    """Test that metrics are in valid Prometheus format"""
    print("Testing Prometheus format...")
    try:
        response = requests.get("http://localhost:9090/metrics", timeout=5)
        text = response.text
        lines = text.split('\n')
        
        # Check for TYPE and HELP comments
        has_type = any(line.startswith('# TYPE') for line in lines)
        has_help = any(line.startswith('# HELP') for line in lines)
        
        assert has_type, "No TYPE declarations found"
        assert has_help, "No HELP declarations found"
        
        print("✓ Prometheus format valid")
        return True
    except Exception as e:
        print(f"✗ Prometheus format test failed: {e}")
        return False


def test_prometheus_ui():
    """Test that Prometheus UI is accessible"""
    print("Testing Prometheus UI...")
    try:
        response = requests.get("http://localhost:9091", timeout=5)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Prometheus UI accessible")
        return True
    except Exception as e:
        print(f"✗ Prometheus UI test failed: {e}")
        return False


def main():
    """Run all integration tests"""
    print("=" * 60)
    print("GSC Warehouse Metrics Exporter - Integration Tests")
    print("=" * 60)
    print()
    
    tests = [
        test_metrics_endpoint,
        test_warehouse_up_metric,
        test_fact_table_metrics,
        test_prometheus_format,
        test_prometheus_ui,
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
        time.sleep(1)
    
    print()
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)
    
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""
Verification script for Docker test services setup.

This script verifies that:
1. docker-compose.test.yml is valid
2. All required files exist
3. Test fixtures can be imported
4. Services can start and become healthy
5. Connections work properly

Run this script to validate the TASK-025 implementation.

Usage:
    python tests/verify_test_setup.py
    python tests/verify_test_setup.py --full  # Include service start/stop
"""
import sys
import subprocess
from pathlib import Path
import argparse

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
DOCKER_COMPOSE_FILE = PROJECT_ROOT / "docker-compose.test.yml"


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}\n")


def print_success(text: str):
    """Print a success message."""
    print(f"{Colors.GREEN}[OK] {text}{Colors.RESET}")


def print_error(text: str):
    """Print an error message."""
    print(f"{Colors.RED}[FAIL] {text}{Colors.RESET}")


def print_warning(text: str):
    """Print a warning message."""
    print(f"{Colors.YELLOW}[WARN] {text}{Colors.RESET}")


def print_info(text: str):
    """Print an info message."""
    print(f"  {text}")


def verify_files():
    """Verify all required files exist."""
    print_header("1. File Existence Check")

    required_files = [
        "docker-compose.test.yml",
        "tests/fixtures/docker_services.py",
        "tests/fixtures/prometheus.yml",
        "tests/test_docker_services.py",
        ".env.test",
        "tests/fixtures/README.md",
        "docs/testing/DOCKER_TESTING.md",
        "tests/Makefile",
    ]

    all_exist = True
    for file_path in required_files:
        full_path = PROJECT_ROOT / file_path
        if full_path.exists():
            print_success(f"{file_path}")
        else:
            print_error(f"{file_path} - MISSING")
            all_exist = False

    return all_exist


def verify_docker_compose():
    """Verify docker-compose.test.yml is valid."""
    print_header("2. Docker Compose Configuration Check")

    try:
        result = subprocess.run(
            ["docker-compose", "-f", str(DOCKER_COMPOSE_FILE), "config"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        if result.returncode == 0:
            print_success("docker-compose.test.yml is valid")
            return True
        else:
            print_error("docker-compose.test.yml validation failed")
            print_info(f"Error: {result.stderr}")
            return False
    except FileNotFoundError:
        print_error("docker-compose not found. Is Docker installed?")
        return False


def verify_service_configuration():
    """Verify service configuration matches requirements."""
    print_header("3. Service Configuration Check")

    try:
        result = subprocess.run(
            ["docker-compose", "-f", str(DOCKER_COMPOSE_FILE), "config"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        if result.returncode != 0:
            print_error("Cannot verify configuration")
            return False

        config = result.stdout

        checks = [
            ("PostgreSQL 15 with pgvector", "pgvector/pgvector:pg15" in config),
            ("Redis 7", "redis:7-alpine" in config),
            ("Grafana latest", "grafana/grafana:latest" in config),
            ("Prometheus latest", "prom/prometheus:latest" in config),
            ("Test network", "test_network" in config),
            ("PostgreSQL container name", "test_gsc_warehouse" in config),
            ("Redis container name", "test_gsc_redis" in config),
            ("Test port 5433", "5433" in config),
            ("Test port 6380", "6380" in config),
        ]

        all_passed = True
        for check_name, check_result in checks:
            if check_result:
                print_success(check_name)
            else:
                print_error(check_name)
                all_passed = False

        return all_passed
    except Exception as e:
        print_error(f"Configuration verification failed: {e}")
        return False


def verify_imports():
    """Verify test fixtures can be imported."""
    print_header("4. Python Import Check")

    try:
        # Try importing fixtures
        sys.path.insert(0, str(PROJECT_ROOT))

        import tests.fixtures.docker_services
        print_success("tests.fixtures.docker_services")

        # Check key functions/fixtures exist
        required_fixtures = [
            "docker_services",
            "postgres_container",
            "redis_container",
            "postgres_connection",
            "redis_client",
            "clean_database",
        ]

        all_exist = True
        for fixture_name in required_fixtures:
            if hasattr(tests.fixtures.docker_services, fixture_name):
                print_success(f"  - {fixture_name}")
            else:
                print_error(f"  - {fixture_name} - MISSING")
                all_exist = False

        return all_exist
    except ImportError as e:
        print_error(f"Import failed: {e}")
        print_info("Make sure psycopg2 and redis are installed:")
        print_info("  pip install psycopg2-binary redis")
        return False


def verify_docker_running():
    """Verify Docker daemon is running."""
    print_header("5. Docker Daemon Check")

    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print_success("Docker daemon is running")
            return True
        else:
            print_error("Docker daemon not responding")
            return False
    except FileNotFoundError:
        print_error("Docker not found. Is Docker installed?")
        return False


def verify_services_start(quick_check: bool = True):
    """Verify services can start and become healthy."""
    print_header("6. Service Startup Check")

    if quick_check:
        print_warning("Skipping service startup check (use --full to enable)")
        return True

    print_info("Starting test services (this may take a minute)...")

    try:
        # Stop any existing services
        subprocess.run(
            ["docker-compose", "-f", str(DOCKER_COMPOSE_FILE), "down", "-v"],
            capture_output=True,
            cwd=PROJECT_ROOT,
        )

        # Start services
        result = subprocess.run(
            ["docker-compose", "-f", str(DOCKER_COMPOSE_FILE), "up", "-d"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        if result.returncode != 0:
            print_error("Failed to start services")
            print_info(result.stderr)
            return False

        print_success("Services started")

        # Wait and check health
        import time
        print_info("Waiting for services to become healthy (30s)...")
        time.sleep(30)

        # Check service health
        services_to_check = [
            ("PostgreSQL", "test_gsc_warehouse"),
            ("Redis", "test_gsc_redis"),
        ]

        all_healthy = True
        for service_name, container_name in services_to_check:
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Health.Status}}", container_name],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                status = result.stdout.strip()
                if status == "healthy":
                    print_success(f"{service_name} is healthy")
                else:
                    print_error(f"{service_name} is {status}")
                    all_healthy = False
            else:
                print_error(f"{service_name} container not found")
                all_healthy = False

        # Stop services
        print_info("Stopping services...")
        subprocess.run(
            ["docker-compose", "-f", str(DOCKER_COMPOSE_FILE), "down", "-v"],
            capture_output=True,
            cwd=PROJECT_ROOT,
        )

        return all_healthy
    except Exception as e:
        print_error(f"Service startup check failed: {e}")
        return False


def main():
    """Run all verification checks."""
    parser = argparse.ArgumentParser(description="Verify Docker test services setup")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full verification including service startup (slower)"
    )
    args = parser.parse_args()

    print(f"\n{Colors.BOLD}Docker Test Services Verification{Colors.RESET}")
    print(f"{Colors.BOLD}TASK-025 Implementation Check{Colors.RESET}")

    results = []

    # Run checks
    results.append(("File Existence", verify_files()))
    results.append(("Docker Compose Config", verify_docker_compose()))
    results.append(("Service Configuration", verify_service_configuration()))
    results.append(("Python Imports", verify_imports()))
    results.append(("Docker Daemon", verify_docker_running()))
    results.append(("Service Startup", verify_services_start(not args.full)))

    # Summary
    print_header("Verification Summary")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for check_name, result in results:
        if result:
            print_success(f"{check_name}")
        else:
            print_error(f"{check_name}")

    print(f"\n{Colors.BOLD}Results: {passed}/{total} checks passed{Colors.RESET}")

    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}[SUCCESS] All checks passed! Setup is complete.{Colors.RESET}\n")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}[FAILED] Some checks failed. Please review errors above.{Colors.RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

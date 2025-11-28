#!/usr/bin/env python3
"""
Screenshot Capture Script for SEO Intelligence Platform
========================================================
Captures screenshots of all UI components using Playwright.

This script automatically discovers and captures screenshots of:
- All Grafana dashboards (auto-discovered from JSON files)
- Insights API endpoints and documentation
- MCP Server endpoints and documentation
- Prometheus UI and targets
- cAdvisor container metrics
- All metrics exporters (PostgreSQL, Redis, custom)

Usage:
    python scripts/take_screenshots.py

    # Or with custom options:
    python scripts/take_screenshots.py --headless --output screenshots/

Requirements:
    - Playwright installed: pip install playwright
    - Browsers installed: python -m playwright install chromium
    - Docker services running: docker-compose up -d

Output:
    Screenshots are saved to screenshots/ directory with timestamp prefixes.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    # Try to set UTF-8 encoding for Windows console
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        # If that fails, disable emojis
        pass


class UIScreenshotter:
    """Captures screenshots of all UI components in the SEO Intelligence Platform."""

    def __init__(self, screenshots_dir: str = "screenshots", headless: bool = True):
        """
        Initialize the screenshotter.

        Args:
            screenshots_dir: Directory to save screenshots
            headless: Run browser in headless mode
        """
        self.screenshots_dir = Path(screenshots_dir)
        self.screenshots_dir.mkdir(exist_ok=True)
        self.headless = headless

        # Timestamp for this run
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Grafana credentials
        self.grafana_user = os.getenv("GRAFANA_USER", "admin")
        self.grafana_password = os.getenv("GRAFANA_PASSWORD", "admin")

        # Base UI endpoints (non-dashboard)
        self.base_endpoints = {
            "01_grafana_home": {
                "url": "http://localhost:3000",
                "description": "Grafana Home Page",
                "wait_for": "body",
                "needs_auth": True,
                "category": "Grafana"
            },
            "02_grafana_dashboards_list": {
                "url": "http://localhost:3000/dashboards",
                "description": "Grafana Dashboards List",
                "wait_for": "body",
                "needs_auth": True,
                "category": "Grafana"
            },
            "03_grafana_explore": {
                "url": "http://localhost:3000/explore",
                "description": "Grafana Explore",
                "wait_for": "body",
                "needs_auth": True,
                "category": "Grafana"
            },
            "04_grafana_alerting": {
                "url": "http://localhost:3000/alerting/list",
                "description": "Grafana Alerting",
                "wait_for": "body",
                "needs_auth": True,
                "category": "Grafana"
            },
            "10_prometheus_home": {
                "url": "http://localhost:9090",
                "description": "Prometheus Home",
                "wait_for": "body",
                "category": "Monitoring"
            },
            "11_prometheus_targets": {
                "url": "http://localhost:9090/targets",
                "description": "Prometheus Targets",
                "wait_for": "body",
                "category": "Monitoring"
            },
            "12_prometheus_alerts": {
                "url": "http://localhost:9090/alerts",
                "description": "Prometheus Alerts",
                "wait_for": "body",
                "category": "Monitoring"
            },
            "13_prometheus_config": {
                "url": "http://localhost:9090/config",
                "description": "Prometheus Configuration",
                "wait_for": "body",
                "category": "Monitoring"
            },
            "14_prometheus_graph": {
                "url": "http://localhost:9090/graph",
                "description": "Prometheus Graph",
                "wait_for": "body",
                "category": "Monitoring"
            },
            "20_cadvisor_containers": {
                "url": "http://localhost:8080/containers/",
                "description": "cAdvisor Container Metrics",
                "wait_for": "body",
                "category": "Monitoring"
            },
            "21_cadvisor_docker": {
                "url": "http://localhost:8080/docker/",
                "description": "cAdvisor Docker Overview",
                "wait_for": "body",
                "category": "Monitoring"
            },
            "30_insights_api_docs": {
                "url": "http://localhost:8000/api/docs",
                "description": "Insights API Documentation (Swagger)",
                "wait_for": "#swagger-ui",
                "extra_wait": 5000,
                "category": "APIs"
            },
            "31_insights_api_redoc": {
                "url": "http://localhost:8000/api/redoc",
                "description": "Insights API Documentation (ReDoc)",
                "wait_for": "[role='main']",
                "extra_wait": 5000,
                "category": "APIs"
            },
            "33_insights_api_home": {
                "url": "http://localhost:8000/",
                "description": "Insights API Home Page",
                "wait_for": ".container",
                "category": "APIs"
            },
            "32_insights_api_health": {
                "url": "http://localhost:8000/api/health",
                "description": "Insights API Health Check",
                "wait_for": "body",
                "category": "APIs"
            },
            "40_mcp_docs": {
                "url": "http://localhost:8001/docs",
                "description": "MCP Server Documentation (Swagger)",
                "wait_for": "#swagger-ui",
                "extra_wait": 5000,
                "category": "APIs"
            },
            "41_mcp_redoc": {
                "url": "http://localhost:8001/redoc",
                "description": "MCP Server Documentation (ReDoc)",
                "wait_for": "[role='main']",
                "extra_wait": 5000,
                "category": "APIs"
            },
            "42_mcp_health": {
                "url": "http://localhost:8001/health",
                "description": "MCP Server Health Check",
                "wait_for": "body",
                "category": "APIs"
            },
            "50_metrics_exporter": {
                "url": "http://localhost:8002/metrics",
                "description": "Custom Application Metrics",
                "wait_for": "body",
                "category": "Metrics Exporters",
                "is_text": True
            },
            "51_postgres_exporter": {
                "url": "http://localhost:9187/metrics",
                "description": "PostgreSQL Database Metrics",
                "wait_for": "body",
                "category": "Metrics Exporters",
                "is_text": True
            },
            "52_redis_exporter": {
                "url": "http://localhost:9121/metrics",
                "description": "Redis Cache Metrics",
                "wait_for": "body",
                "category": "Metrics Exporters",
                "is_text": True
            }
        }

        # Dashboard endpoints will be populated from JSON files
        self.dashboard_endpoints = {}

    def discover_grafana_dashboards(self) -> Dict[str, Dict]:
        """
        Discover all Grafana dashboards from JSON files.

        Returns:
            Dictionary of dashboard endpoints
        """
        dashboards = {}
        dashboard_dir = Path("grafana/provisioning/dashboards")

        if not dashboard_dir.exists():
            print(f"⚠️  Dashboard directory not found: {dashboard_dir}")
            return dashboards

        # Find all JSON dashboard files
        json_files = list(dashboard_dir.glob("*.json"))
        print(f"\n📂 Discovering Grafana dashboards from {len(json_files)} JSON files...")

        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    dashboard_data = json.load(f)

                    # Extract dashboard info
                    uid = dashboard_data.get('uid', '')
                    title = dashboard_data.get('title', json_file.stem)
                    description = dashboard_data.get('description', '')
                    tags = dashboard_data.get('tags', [])

                    if uid:
                        # Create endpoint name from file name
                        name = f"dashboard_{json_file.stem.replace('-', '_')}"

                        dashboards[name] = {
                            "url": f"http://localhost:3000/d/{uid}",
                            "description": f"Dashboard: {title}",
                            "wait_for": "body",
                            "needs_auth": True,
                            "category": "Dashboards",
                            "uid": uid,
                            "title": title,
                            "tags": tags,
                            "dashboard_description": description
                        }

                        print(f"   ✓ Found: {title} (uid: {uid})")

            except json.JSONDecodeError as e:
                print(f"   ⚠️  Error parsing {json_file.name}: {e}")
            except Exception as e:
                print(f"   ⚠️  Error reading {json_file.name}: {e}")

        print(f"✅ Discovered {len(dashboards)} Grafana dashboards")
        return dashboards

    async def authenticate_grafana(self, page):
        """
        Authenticate with Grafana if needed.

        Args:
            page: Playwright page object
        """
        try:
            # Wait for either login form or main content
            await page.wait_for_selector('input[name="user"], .main-view, [aria-label="Skip change password button"]', timeout=3000)

            # Check if we're on the login page
            if await page.locator('input[name="user"]').count() > 0:
                print("   🔐 Logging in to Grafana...")
                await page.fill('input[name="user"]', self.grafana_user)
                await page.fill('input[name="password"]', self.grafana_password)
                await page.click('button[type="submit"]')

                # Wait for navigation
                await page.wait_for_load_state("networkidle", timeout=10000)

                # Check for password change prompt and skip if present
                if await page.locator('[aria-label="Skip change password button"]').count() > 0:
                    await page.click('[aria-label="Skip change password button"]')
                    await page.wait_for_load_state("networkidle", timeout=5000)

                print("   ✓ Logged in successfully")
                return True

        except Exception as e:
            print(f"   ⚠️  Auth check: {str(e)}")

        return False

    async def capture_screenshot(self, page, name: str, config: dict, authenticated: bool = False) -> bool:
        """
        Capture a screenshot of a specific endpoint.

        Args:
            page: Playwright page object
            name: Name for the screenshot file
            config: Configuration dict with url, description, etc.
            authenticated: Whether Grafana auth is already done

        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"\n📸 [{config.get('category', 'Other')}] {config['description']}")
            print(f"   URL: {config['url']}")

            # Navigate to the URL - use domcontentloaded for pages with continuous polling
            # Prometheus/Grafana/monitoring tools continuously poll so networkidle won't work
            wait_strategy = 'domcontentloaded' if config.get('category') in ['Monitoring', 'Grafana'] else 'networkidle'
            try:
                await page.goto(config['url'], timeout=30000, wait_until=wait_strategy)
            except Exception as e:
                # Fallback to domcontentloaded if networkidle times out
                if 'Timeout' in str(e) and wait_strategy == 'networkidle':
                    print(f"   ⚠️  Network idle timeout, retrying with domcontentloaded...")
                    await page.goto(config['url'], timeout=30000, wait_until='domcontentloaded')
                else:
                    raise

            # Handle authentication if needed (check if we got redirected to login)
            if config.get('needs_auth', False):
                # Check if we're on the login page
                if await page.locator('input[name="user"]').count() > 0:
                    print("   🔐 Authentication required, logging in...")
                    await self.authenticate_grafana(page)
                    # Navigate back to the original URL after authentication
                    print(f"   🔄 Navigating back to: {config['url']}")
                    await page.goto(config['url'], timeout=30000, wait_until='domcontentloaded')

            # Wait for content to load
            try:
                await page.wait_for_selector(config.get('wait_for', 'body'), timeout=15000)
            except:
                print(f"   ⚠️  Selector timeout, continuing anyway...")

            # Additional wait for dynamic content
            base_wait = config.get('extra_wait', 3000)
            await page.wait_for_timeout(base_wait)

            # For dashboards, wait a bit longer for panels to render
            if config.get('category') == 'Dashboards':
                await page.wait_for_timeout(5000)

            # Scroll to bottom and back to top to trigger lazy loading
            if config.get('category') in ['APIs', 'Dashboards']:
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(1000)
                await page.evaluate('window.scrollTo(0, 0)')
                await page.wait_for_timeout(500)

            # Take screenshot
            screenshot_path = self.screenshots_dir / f"{self.timestamp}_{name}.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)

            file_size = screenshot_path.stat().st_size / 1024  # KB
            print(f"   ✅ Saved: {screenshot_path.name} ({file_size:.1f} KB)")
            return True

        except PlaywrightTimeoutError as e:
            print(f"   ❌ Timeout: {str(e)[:100]}")
            return False
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}")
            return False

    async def capture_all(self):
        """Capture screenshots of all configured endpoints."""
        print("=" * 80)
        print("SEO Intelligence Platform - UI Screenshot Capture")
        print("=" * 80)
        print(f"Timestamp: {self.timestamp}")
        print(f"Output directory: {self.screenshots_dir.absolute()}")
        print(f"Headless mode: {self.headless}")

        # Discover Grafana dashboards
        self.dashboard_endpoints = self.discover_grafana_dashboards()

        # Combine all endpoints
        all_endpoints = {**self.base_endpoints, **self.dashboard_endpoints}
        print(f"\n📊 Total endpoints to capture: {len(all_endpoints)}")
        print(f"   - Base endpoints: {len(self.base_endpoints)}")
        print(f"   - Dashboards: {len(self.dashboard_endpoints)}")
        print("=" * 80)

        async with async_playwright() as p:
            # Launch browser
            print("\n🚀 Launching browser...")
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                ignore_https_errors=True
            )
            page = await context.new_page()

            # Authenticate with Grafana first if needed
            grafana_authenticated = False
            grafana_endpoints = [k for k, v in all_endpoints.items() if v.get('needs_auth')]
            if grafana_endpoints:
                print("\n🔐 Pre-authenticating with Grafana...")
                await page.goto("http://localhost:3000")
                grafana_authenticated = await self.authenticate_grafana(page)

            # Capture each endpoint
            results = {}
            categories = {}

            for name, config in sorted(all_endpoints.items()):
                success = await self.capture_screenshot(page, name, config, grafana_authenticated)
                results[name] = success

                # Track by category
                category = config.get('category', 'Other')
                if category not in categories:
                    categories[category] = {'success': 0, 'failed': 0}
                if success:
                    categories[category]['success'] += 1
                else:
                    categories[category]['failed'] += 1

            # Close browser
            print("\n🔒 Closing browser...")
            await browser.close()

            # Summary
            print("\n" + "=" * 80)
            print("SUMMARY")
            print("=" * 80)

            successful = sum(1 for v in results.values() if v)
            failed = len(results) - successful

            print(f"\n📊 Overall Results:")
            print(f"   ✅ Successful: {successful}/{len(results)} ({successful/len(results)*100:.1f}%)")
            print(f"   ❌ Failed: {failed}/{len(results)}")

            print(f"\n📁 Results by Category:")
            for category in sorted(categories.keys()):
                stats = categories[category]
                total = stats['success'] + stats['failed']
                print(f"   {category}: {stats['success']}/{total} successful")

            if failed > 0:
                print(f"\n❌ Failed Endpoints ({failed}):")
                for name, success in results.items():
                    if not success:
                        config = all_endpoints[name]
                        print(f"   - {name}")
                        print(f"     {config['description']}")
                        print(f"     {config['url']}")

            print("\n" + "=" * 80)
            print(f"📁 Screenshots saved to: {self.screenshots_dir.absolute()}")
            print(f"🕐 Timestamp: {self.timestamp}")
            print("=" * 80)

            return results


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Capture screenshots of SEO Intelligence Platform UIs"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="screenshots",
        help="Output directory for screenshots (default: screenshots/)"
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser in non-headless mode (visible)"
    )

    args = parser.parse_args()

    screenshotter = UIScreenshotter(
        screenshots_dir=args.output,
        headless=not args.no_headless
    )
    await screenshotter.capture_all()


if __name__ == "__main__":
    asyncio.run(main())

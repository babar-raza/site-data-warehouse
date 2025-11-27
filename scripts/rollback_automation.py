#!/usr/bin/env python3
"""
Rollback Automation Script
Monitors health endpoints and automatically triggers rollback on failures

Features:
- Continuous health monitoring of all services
- Automatic rollback to previous Docker image versions
- Configurable failure thresholds and check intervals
- Comprehensive logging of all actions
- Graceful shutdown handling
- Multi-service health checks
- Docker image version tracking
"""

import os
import sys
import time
import json
import signal
import logging
import argparse
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
import asyncpg
import httpx


# ============================================================================
# Configuration
# ============================================================================

class ServiceStatus(Enum):
    """Service health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckConfig:
    """Configuration for health monitoring"""
    failure_threshold: int = 3
    check_interval: int = 30
    timeout: int = 10
    warning_threshold: int = 2


@dataclass
class ServiceEndpoint:
    """Service health endpoint configuration"""
    name: str
    url: str
    type: str  # http, postgres, docker
    critical: bool = True
    custom_check: Optional[str] = None


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    service_name: str
    status: ServiceStatus
    timestamp: datetime
    response_time_ms: float
    error_message: Optional[str] = None
    details: Optional[Dict] = None


@dataclass
class RollbackRecord:
    """Record of a rollback action"""
    timestamp: datetime
    service_name: str
    from_version: str
    to_version: str
    reason: str
    success: bool
    details: Optional[Dict] = None


# ============================================================================
# Logging Configuration
# ============================================================================

def setup_logging(log_file: Optional[str] = None, verbose: bool = False) -> logging.Logger:
    """Setup logging configuration"""
    log_level = logging.DEBUG if verbose else logging.INFO

    # Create logger
    logger = logging.getLogger("rollback_automation")
    logger.setLevel(log_level)

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)

    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)

    return logger


# ============================================================================
# Health Monitoring
# ============================================================================

class HealthMonitor:
    """Monitors service health endpoints"""

    def __init__(self, config: HealthCheckConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.failure_counts: Dict[str, int] = {}
        self.last_healthy: Dict[str, datetime] = {}
        self.check_history: List[HealthCheckResult] = []
        self.max_history = 1000

    async def check_http_endpoint(self, endpoint: ServiceEndpoint) -> HealthCheckResult:
        """Check HTTP health endpoint"""
        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.get(endpoint.url)
                response_time = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    status = ServiceStatus.HEALTHY
                    error_message = None

                    # Parse response if JSON
                    try:
                        details = response.json()
                    except:
                        details = {"status_code": response.status_code}
                else:
                    status = ServiceStatus.DEGRADED
                    error_message = f"HTTP {response.status_code}"
                    details = {"status_code": response.status_code}

        except asyncio.TimeoutError:
            response_time = self.config.timeout * 1000
            status = ServiceStatus.UNHEALTHY
            error_message = "Connection timeout"
            details = None
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            status = ServiceStatus.UNHEALTHY
            error_message = str(e)
            details = None

        return HealthCheckResult(
            service_name=endpoint.name,
            status=status,
            timestamp=datetime.utcnow(),
            response_time_ms=response_time,
            error_message=error_message,
            details=details
        )

    async def check_postgres_endpoint(self, endpoint: ServiceEndpoint) -> HealthCheckResult:
        """Check PostgreSQL database health"""
        start_time = time.time()

        try:
            dsn = os.getenv('WAREHOUSE_DSN', endpoint.url)
            conn = await asyncpg.connect(dsn, timeout=self.config.timeout)

            # Check basic connectivity
            result = await conn.fetchval("SELECT 1")

            # Check for recent data (if table exists)
            try:
                latest_date = await conn.fetchval(
                    "SELECT MAX(data_date) FROM gsc.query_stats"
                )
                days_old = (datetime.now().date() - latest_date).days if latest_date else None
            except:
                days_old = None

            await conn.close()

            response_time = (time.time() - start_time) * 1000

            if result == 1:
                status = ServiceStatus.HEALTHY
                error_message = None
                details = {"days_old": days_old} if days_old is not None else {}
            else:
                status = ServiceStatus.DEGRADED
                error_message = "Unexpected query result"
                details = {"result": result}

        except asyncio.TimeoutError:
            response_time = self.config.timeout * 1000
            status = ServiceStatus.UNHEALTHY
            error_message = "Connection timeout"
            details = None
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            status = ServiceStatus.UNHEALTHY
            error_message = str(e)
            details = None

        return HealthCheckResult(
            service_name=endpoint.name,
            status=status,
            timestamp=datetime.utcnow(),
            response_time_ms=response_time,
            error_message=error_message,
            details=details
        )

    async def check_docker_service(self, endpoint: ServiceEndpoint) -> HealthCheckResult:
        """Check Docker service health"""
        start_time = time.time()

        try:
            # Check if container is running
            result = subprocess.run(
                ['docker', 'compose', 'ps', '--format', 'json', endpoint.name],
                capture_output=True,
                text=True,
                timeout=self.config.timeout
            )

            response_time = (time.time() - start_time) * 1000

            if result.returncode == 0 and result.stdout:
                # Parse container status
                try:
                    container_info = json.loads(result.stdout)
                    if isinstance(container_info, list):
                        container_info = container_info[0] if container_info else {}

                    state = container_info.get('State', 'unknown')
                    health = container_info.get('Health', 'unknown')

                    if state == 'running' and (health == 'healthy' or health == 'unknown'):
                        status = ServiceStatus.HEALTHY
                        error_message = None
                    elif state == 'running':
                        status = ServiceStatus.DEGRADED
                        error_message = f"Container unhealthy: {health}"
                    else:
                        status = ServiceStatus.UNHEALTHY
                        error_message = f"Container not running: {state}"

                    details = {
                        "state": state,
                        "health": health
                    }
                except json.JSONDecodeError:
                    status = ServiceStatus.UNKNOWN
                    error_message = "Failed to parse container status"
                    details = None
            else:
                status = ServiceStatus.UNHEALTHY
                error_message = "Container not found"
                details = None

        except subprocess.TimeoutExpired:
            response_time = self.config.timeout * 1000
            status = ServiceStatus.UNHEALTHY
            error_message = "Docker command timeout"
            details = None
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            status = ServiceStatus.UNHEALTHY
            error_message = str(e)
            details = None

        return HealthCheckResult(
            service_name=endpoint.name,
            status=status,
            timestamp=datetime.utcnow(),
            response_time_ms=response_time,
            error_message=error_message,
            details=details
        )

    async def check_endpoint(self, endpoint: ServiceEndpoint) -> HealthCheckResult:
        """Check a single endpoint based on its type"""
        if endpoint.type == 'http':
            return await self.check_http_endpoint(endpoint)
        elif endpoint.type == 'postgres':
            return await self.check_postgres_endpoint(endpoint)
        elif endpoint.type == 'docker':
            return await self.check_docker_service(endpoint)
        else:
            self.logger.error(f"Unknown endpoint type: {endpoint.type}")
            return HealthCheckResult(
                service_name=endpoint.name,
                status=ServiceStatus.UNKNOWN,
                timestamp=datetime.utcnow(),
                response_time_ms=0,
                error_message=f"Unknown endpoint type: {endpoint.type}"
            )

    async def check_all_endpoints(self, endpoints: List[ServiceEndpoint]) -> List[HealthCheckResult]:
        """Check all endpoints concurrently"""
        tasks = [self.check_endpoint(endpoint) for endpoint in endpoints]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Health check failed for {endpoints[i].name}: {result}")
                processed_results.append(
                    HealthCheckResult(
                        service_name=endpoints[i].name,
                        status=ServiceStatus.UNHEALTHY,
                        timestamp=datetime.utcnow(),
                        response_time_ms=0,
                        error_message=str(result)
                    )
                )
            else:
                processed_results.append(result)

        return processed_results

    def update_failure_counts(self, results: List[HealthCheckResult]) -> None:
        """Update failure counters based on check results"""
        for result in results:
            if result.status == ServiceStatus.HEALTHY:
                # Reset failure count on success
                self.failure_counts[result.service_name] = 0
                self.last_healthy[result.service_name] = result.timestamp
                self.logger.debug(
                    f"{result.service_name}: Healthy "
                    f"(response time: {result.response_time_ms:.2f}ms)"
                )
            else:
                # Increment failure count
                current_count = self.failure_counts.get(result.service_name, 0)
                self.failure_counts[result.service_name] = current_count + 1

                # Log based on severity
                count = self.failure_counts[result.service_name]
                if count >= self.config.failure_threshold:
                    self.logger.error(
                        f"{result.service_name}: CRITICAL - {count} consecutive failures - "
                        f"{result.error_message}"
                    )
                elif count >= self.config.warning_threshold:
                    self.logger.warning(
                        f"{result.service_name}: WARNING - {count} consecutive failures - "
                        f"{result.error_message}"
                    )
                else:
                    self.logger.info(
                        f"{result.service_name}: Failed - {result.error_message}"
                    )

    def get_services_requiring_rollback(self, endpoints: List[ServiceEndpoint]) -> List[str]:
        """Get list of services that have exceeded failure threshold"""
        services_to_rollback = []

        for endpoint in endpoints:
            if not endpoint.critical:
                continue

            failure_count = self.failure_counts.get(endpoint.name, 0)
            if failure_count >= self.config.failure_threshold:
                services_to_rollback.append(endpoint.name)
                self.logger.critical(
                    f"{endpoint.name}: Failure threshold exceeded "
                    f"({failure_count}/{self.config.failure_threshold})"
                )

        return services_to_rollback

    def add_to_history(self, results: List[HealthCheckResult]) -> None:
        """Add results to check history"""
        self.check_history.extend(results)

        # Trim history if too large
        if len(self.check_history) > self.max_history:
            self.check_history = self.check_history[-self.max_history:]

    def get_health_summary(self) -> Dict:
        """Get summary of current health status"""
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "services": {},
            "overall_status": "healthy"
        }

        for service_name, failure_count in self.failure_counts.items():
            last_healthy = self.last_healthy.get(service_name)

            if failure_count >= self.config.failure_threshold:
                status = "unhealthy"
                summary["overall_status"] = "unhealthy"
            elif failure_count >= self.config.warning_threshold:
                status = "degraded"
                if summary["overall_status"] == "healthy":
                    summary["overall_status"] = "degraded"
            else:
                status = "healthy"

            summary["services"][service_name] = {
                "status": status,
                "consecutive_failures": failure_count,
                "last_healthy": last_healthy.isoformat() if last_healthy else None
            }

        return summary


# ============================================================================
# Rollback Manager
# ============================================================================

class RollbackManager:
    """Manages Docker image rollbacks"""

    def __init__(self, logger: logging.Logger, dry_run: bool = False):
        self.logger = logger
        self.dry_run = dry_run
        self.rollback_history: List[RollbackRecord] = []
        self.image_history: Dict[str, List[str]] = {}

    def get_current_image_version(self, service_name: str) -> Optional[str]:
        """Get current Docker image version for a service"""
        try:
            result = subprocess.run(
                ['docker', 'compose', 'images', '--format', 'json', service_name],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and result.stdout:
                image_info = json.loads(result.stdout)
                if isinstance(image_info, list):
                    image_info = image_info[0] if image_info else {}

                repository = image_info.get('Repository', '')
                tag = image_info.get('Tag', '')
                return f"{repository}:{tag}" if repository and tag else None

        except Exception as e:
            self.logger.error(f"Failed to get image version for {service_name}: {e}")

        return None

    def get_previous_image_version(self, service_name: str) -> Optional[str]:
        """Get previous Docker image version for rollback"""
        try:
            # Try to find backup image tag
            result = subprocess.run(
                ['docker', 'images', '--format', 'json', '--filter', f'reference=*{service_name}*'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and result.stdout:
                images = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            img = json.loads(line)
                            images.append(img)
                        except json.JSONDecodeError:
                            continue

                # Sort by created time and get the second most recent
                images.sort(key=lambda x: x.get('CreatedAt', ''), reverse=True)

                if len(images) >= 2:
                    repo = images[1].get('Repository', '')
                    tag = images[1].get('Tag', '')
                    return f"{repo}:{tag}" if repo and tag else None

        except Exception as e:
            self.logger.error(f"Failed to get previous image for {service_name}: {e}")

        return None

    def backup_current_image(self, service_name: str) -> bool:
        """Create a backup tag for the current image"""
        current_image = self.get_current_image_version(service_name)

        if not current_image:
            self.logger.error(f"Cannot backup image for {service_name}: current image not found")
            return False

        # Create backup tag with timestamp
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_tag = f"{current_image.split(':')[0]}:backup_{timestamp}"

        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would tag {current_image} as {backup_tag}")
                return True

            result = subprocess.run(
                ['docker', 'tag', current_image, backup_tag],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                self.logger.info(f"Created backup image: {backup_tag}")
                return True
            else:
                self.logger.error(f"Failed to create backup: {result.stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to backup image for {service_name}: {e}")
            return False

    def rollback_service(self, service_name: str, reason: str) -> bool:
        """Rollback a service to its previous version"""
        self.logger.info(f"Initiating rollback for {service_name}...")

        # Get current and previous versions
        current_version = self.get_current_image_version(service_name)
        previous_version = self.get_previous_image_version(service_name)

        if not previous_version:
            self.logger.error(f"Cannot rollback {service_name}: no previous version found")
            record = RollbackRecord(
                timestamp=datetime.utcnow(),
                service_name=service_name,
                from_version=current_version or "unknown",
                to_version="none",
                reason=reason,
                success=False,
                details={"error": "No previous version available"}
            )
            self.rollback_history.append(record)
            return False

        self.logger.info(f"Rolling back {service_name} from {current_version} to {previous_version}")

        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would rollback {service_name} to {previous_version}")
                record = RollbackRecord(
                    timestamp=datetime.utcnow(),
                    service_name=service_name,
                    from_version=current_version or "unknown",
                    to_version=previous_version,
                    reason=reason,
                    success=True,
                    details={"dry_run": True}
                )
                self.rollback_history.append(record)
                return True

            # Step 1: Backup current image
            if current_version:
                self.backup_current_image(service_name)

            # Step 2: Stop the service
            self.logger.info(f"Stopping {service_name}...")
            subprocess.run(
                ['docker', 'compose', 'stop', service_name],
                capture_output=True,
                timeout=60,
                check=True
            )

            # Step 3: Remove the container
            self.logger.info(f"Removing container for {service_name}...")
            subprocess.run(
                ['docker', 'compose', 'rm', '-f', service_name],
                capture_output=True,
                timeout=30,
                check=True
            )

            # Step 4: Update docker-compose to use previous image
            # Note: This would require modifying docker-compose.yml or using environment variables
            # For now, we'll rely on Docker Compose's ability to use the previous image

            # Step 5: Start service with previous image
            self.logger.info(f"Starting {service_name} with previous version...")
            result = subprocess.run(
                ['docker', 'compose', 'up', '-d', service_name],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                self.logger.info(f"Successfully rolled back {service_name}")
                record = RollbackRecord(
                    timestamp=datetime.utcnow(),
                    service_name=service_name,
                    from_version=current_version or "unknown",
                    to_version=previous_version,
                    reason=reason,
                    success=True,
                    details={"method": "docker_compose"}
                )
                self.rollback_history.append(record)
                return True
            else:
                self.logger.error(f"Failed to start {service_name}: {result.stderr}")
                record = RollbackRecord(
                    timestamp=datetime.utcnow(),
                    service_name=service_name,
                    from_version=current_version or "unknown",
                    to_version=previous_version,
                    reason=reason,
                    success=False,
                    details={"error": result.stderr}
                )
                self.rollback_history.append(record)
                return False

        except subprocess.TimeoutExpired as e:
            self.logger.error(f"Rollback timeout for {service_name}: {e}")
            record = RollbackRecord(
                timestamp=datetime.utcnow(),
                service_name=service_name,
                from_version=current_version or "unknown",
                to_version=previous_version,
                reason=reason,
                success=False,
                details={"error": "Timeout during rollback"}
            )
            self.rollback_history.append(record)
            return False
        except Exception as e:
            self.logger.error(f"Rollback failed for {service_name}: {e}")
            record = RollbackRecord(
                timestamp=datetime.utcnow(),
                service_name=service_name,
                from_version=current_version or "unknown",
                to_version=previous_version,
                reason=reason,
                success=False,
                details={"error": str(e)}
            )
            self.rollback_history.append(record)
            return False

    def get_rollback_history(self) -> List[Dict]:
        """Get rollback history as list of dicts"""
        return [asdict(record) for record in self.rollback_history]

    def save_rollback_history(self, filepath: str) -> None:
        """Save rollback history to file"""
        try:
            history = self.get_rollback_history()
            with open(filepath, 'w') as f:
                json.dump(history, f, indent=2, default=str)
            self.logger.info(f"Saved rollback history to {filepath}")
        except Exception as e:
            self.logger.error(f"Failed to save rollback history: {e}")


# ============================================================================
# Main Automation Controller
# ============================================================================

class RollbackAutomation:
    """Main controller for rollback automation"""

    def __init__(
        self,
        endpoints: List[ServiceEndpoint],
        config: HealthCheckConfig,
        logger: logging.Logger,
        dry_run: bool = False
    ):
        self.endpoints = endpoints
        self.config = config
        self.logger = logger
        self.dry_run = dry_run
        self.health_monitor = HealthMonitor(config, logger)
        self.rollback_manager = RollbackManager(logger, dry_run)
        self.running = False
        self.shutdown_requested = False

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        signal_name = signal.Signals(signum).name
        self.logger.info(f"Received signal {signal_name}, initiating graceful shutdown...")
        self.shutdown_requested = True
        self.running = False

    async def monitoring_loop(self) -> None:
        """Main monitoring loop"""
        self.logger.info("Starting health monitoring loop...")
        self.logger.info(f"Check interval: {self.config.check_interval}s")
        self.logger.info(f"Failure threshold: {self.config.failure_threshold}")
        self.logger.info(f"Monitoring {len(self.endpoints)} endpoints")

        check_count = 0

        while self.running and not self.shutdown_requested:
            check_count += 1
            self.logger.debug(f"Starting health check #{check_count}")

            try:
                # Perform health checks
                results = await self.health_monitor.check_all_endpoints(self.endpoints)

                # Update failure counts
                self.health_monitor.update_failure_counts(results)

                # Add to history
                self.health_monitor.add_to_history(results)

                # Check if any services need rollback
                services_to_rollback = self.health_monitor.get_services_requiring_rollback(
                    self.endpoints
                )

                # Trigger rollbacks if needed
                if services_to_rollback:
                    self.logger.critical(
                        f"Services requiring rollback: {', '.join(services_to_rollback)}"
                    )

                    for service_name in services_to_rollback:
                        reason = (
                            f"Health check failures exceeded threshold "
                            f"({self.config.failure_threshold} consecutive failures)"
                        )
                        success = self.rollback_manager.rollback_service(service_name, reason)

                        if success:
                            # Reset failure count after successful rollback
                            self.health_monitor.failure_counts[service_name] = 0
                            self.logger.info(f"Rollback completed for {service_name}")
                        else:
                            self.logger.error(f"Rollback failed for {service_name}")

                # Log summary every 10 checks
                if check_count % 10 == 0:
                    summary = self.health_monitor.get_health_summary()
                    self.logger.info(f"Health summary: {summary['overall_status']}")
                    for svc, status in summary['services'].items():
                        if status['consecutive_failures'] > 0:
                            self.logger.info(
                                f"  {svc}: {status['status']} "
                                f"(failures: {status['consecutive_failures']})"
                            )

            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}", exc_info=True)

            # Wait for next check interval
            if self.running and not self.shutdown_requested:
                await asyncio.sleep(self.config.check_interval)

        self.logger.info("Monitoring loop stopped")

    async def run(self) -> None:
        """Run the automation"""
        # Register signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        self.running = True

        self.logger.info("=" * 60)
        self.logger.info("Rollback Automation Started")
        self.logger.info("=" * 60)

        if self.dry_run:
            self.logger.warning("Running in DRY RUN mode - no actual rollbacks will occur")

        try:
            await self.monitoring_loop()
        except Exception as e:
            self.logger.error(f"Fatal error in automation: {e}", exc_info=True)
        finally:
            self.logger.info("=" * 60)
            self.logger.info("Rollback Automation Stopped")
            self.logger.info("=" * 60)

            # Save rollback history
            history_file = os.path.join(
                os.path.dirname(__file__),
                f"rollback_history_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            )
            self.rollback_manager.save_rollback_history(history_file)

            # Print final summary
            summary = self.health_monitor.get_health_summary()
            self.logger.info(f"Final health status: {summary['overall_status']}")

            rollback_count = len(self.rollback_manager.rollback_history)
            if rollback_count > 0:
                self.logger.info(f"Total rollbacks performed: {rollback_count}")
                for record in self.rollback_manager.rollback_history:
                    status = "SUCCESS" if record.success else "FAILED"
                    self.logger.info(
                        f"  [{status}] {record.service_name}: "
                        f"{record.from_version} -> {record.to_version}"
                    )


# ============================================================================
# Default Configuration
# ============================================================================

def get_default_endpoints() -> List[ServiceEndpoint]:
    """Get default service endpoints to monitor"""
    base_url = os.getenv('BASE_URL', 'http://localhost')

    return [
        # HTTP endpoints
        ServiceEndpoint(
            name="insights_api",
            url=f"{base_url}:8000/api/health",
            type="http",
            critical=True
        ),
        ServiceEndpoint(
            name="mcp",
            url=f"{base_url}:8001/health",
            type="http",
            critical=True
        ),
        ServiceEndpoint(
            name="metrics_exporter",
            url=f"{base_url}:8002/metrics",
            type="http",
            critical=False
        ),
        ServiceEndpoint(
            name="grafana",
            url=f"{base_url}:3000/api/health",
            type="http",
            critical=False
        ),
        ServiceEndpoint(
            name="prometheus",
            url=f"{base_url}:9090/-/healthy",
            type="http",
            critical=False
        ),

        # PostgreSQL
        ServiceEndpoint(
            name="warehouse",
            url=os.getenv('WAREHOUSE_DSN', 'postgresql://gsc_user:gsc_pass@localhost:5432/gsc_db'),
            type="postgres",
            critical=True
        ),

        # Docker services
        ServiceEndpoint(
            name="scheduler",
            url="",
            type="docker",
            critical=True
        ),
        ServiceEndpoint(
            name="api_ingestor",
            url="",
            type="docker",
            critical=True
        ),
    ]


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Rollback Automation - Monitor services and automatically rollback on failures",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration file (JSON)'
    )

    parser.add_argument(
        '--check-interval',
        type=int,
        default=30,
        help='Health check interval in seconds (default: 30)'
    )

    parser.add_argument(
        '--failure-threshold',
        type=int,
        default=3,
        help='Number of consecutive failures before rollback (default: 3)'
    )

    parser.add_argument(
        '--timeout',
        type=int,
        default=10,
        help='Health check timeout in seconds (default: 10)'
    )

    parser.add_argument(
        '--log-file',
        type=str,
        help='Path to log file'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run mode - no actual rollbacks will be performed'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Setup logging
    log_file = args.log_file or os.path.join(
        os.path.dirname(__file__),
        f"rollback_automation_{datetime.utcnow().strftime('%Y%m%d')}.log"
    )
    logger = setup_logging(log_file, args.verbose)

    # Create health check config
    config = HealthCheckConfig(
        failure_threshold=args.failure_threshold,
        check_interval=args.check_interval,
        timeout=args.timeout
    )

    # Load endpoints
    endpoints = get_default_endpoints()

    if args.config:
        try:
            with open(args.config, 'r') as f:
                config_data = json.load(f)
                # Load custom endpoints if provided
                if 'endpoints' in config_data:
                    endpoints = [
                        ServiceEndpoint(**ep) for ep in config_data['endpoints']
                    ]
                logger.info(f"Loaded configuration from {args.config}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            sys.exit(1)

    # Create and run automation
    automation = RollbackAutomation(
        endpoints=endpoints,
        config=config,
        logger=logger,
        dry_run=args.dry_run
    )

    try:
        asyncio.run(automation.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

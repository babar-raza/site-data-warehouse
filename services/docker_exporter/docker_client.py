"""
Docker API Client for collecting container statistics.

This module provides a wrapper around the Docker SDK to collect container
statistics in a format compatible with Prometheus metrics.
"""

import logging
import time
from typing import Dict, List, Optional, Any
import docker
from docker.errors import DockerException, APIError, NotFound

logger = logging.getLogger(__name__)


class DockerStatsCollector:
    """Collects statistics from Docker containers using the Docker API."""

    def __init__(self, socket_path: Optional[str] = None):
        """
        Initialize the Docker client.

        Args:
            socket_path: Optional path to Docker socket. If None, uses default.
        """
        try:
            if socket_path:
                self.client = docker.DockerClient(base_url=socket_path)
            else:
                self.client = docker.from_env()

            # Test connection
            self.client.ping()
            logger.info("Successfully connected to Docker daemon")
        except DockerException as e:
            logger.error(f"Failed to connect to Docker daemon: {e}")
            raise

    def get_all_containers(self, include_stopped: bool = False) -> List[docker.models.containers.Container]:
        """
        Get all containers.

        Args:
            include_stopped: If True, includes stopped containers.

        Returns:
            List of Container objects.
        """
        try:
            containers = self.client.containers.list(all=include_stopped)
            logger.debug(f"Found {len(containers)} containers")
            return containers
        except DockerException as e:
            logger.error(f"Failed to list containers: {e}")
            return []

    def get_container_stats(self, container: docker.models.containers.Container) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a specific container.

        Args:
            container: Docker container object.

        Returns:
            Dictionary containing parsed stats, or None if stats unavailable.
        """
        try:
            # Get stats (stream=False returns a single snapshot)
            # Note: decode parameter is only valid with stream=True
            stats = container.stats(stream=False)

            # Parse the stats into our format
            parsed_stats = self._parse_stats(stats)
            return parsed_stats
        except NotFound:
            logger.warning(f"Container {container.name} not found")
            return None
        except APIError as e:
            logger.warning(f"Failed to get stats for {container.name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting stats for {container.name}: {e}")
            return None

    def _parse_stats(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw Docker stats into a simplified format.

        Args:
            stats: Raw stats from Docker API.

        Returns:
            Dictionary with parsed metrics.
        """
        parsed = {
            'timestamp': time.time(),
            'cpu': self._parse_cpu_stats(stats),
            'memory': self._parse_memory_stats(stats),
            'network': self._parse_network_stats(stats),
            'blkio': self._parse_blkio_stats(stats),
        }
        return parsed

    def _parse_cpu_stats(self, stats: Dict[str, Any]) -> Dict[str, float]:
        """
        Parse CPU statistics.

        Args:
            stats: Raw stats from Docker API.

        Returns:
            Dictionary with CPU metrics.
        """
        try:
            cpu_stats = stats.get('cpu_stats', {})
            precpu_stats = stats.get('precpu_stats', {})

            # Total CPU usage in nanoseconds
            cpu_usage = cpu_stats.get('cpu_usage', {})
            total_usage = cpu_usage.get('total_usage', 0)

            # Convert nanoseconds to seconds
            total_usage_seconds = total_usage / 1e9

            # Calculate CPU delta for percentage calculation
            cpu_delta = total_usage - precpu_stats.get('cpu_usage', {}).get('total_usage', 0)
            system_delta = cpu_stats.get('system_cpu_usage', 0) - precpu_stats.get('system_cpu_usage', 0)

            # Number of CPUs
            online_cpus = cpu_stats.get('online_cpus', 1)
            if online_cpus == 0:
                online_cpus = len(cpu_usage.get('percpu_usage', [1]))

            # CPU percentage
            cpu_percent = 0.0
            if system_delta > 0 and cpu_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * online_cpus * 100.0

            return {
                'total_usage_seconds': total_usage_seconds,
                'usage_percent': cpu_percent,
                'online_cpus': online_cpus,
            }
        except (KeyError, TypeError, ZeroDivisionError) as e:
            logger.debug(f"Error parsing CPU stats: {e}")
            return {
                'total_usage_seconds': 0.0,
                'usage_percent': 0.0,
                'online_cpus': 1,
            }

    def _parse_memory_stats(self, stats: Dict[str, Any]) -> Dict[str, int]:
        """
        Parse memory statistics.

        Args:
            stats: Raw stats from Docker API.

        Returns:
            Dictionary with memory metrics in bytes.
        """
        try:
            memory_stats = stats.get('memory_stats', {})

            # Current memory usage
            usage = memory_stats.get('usage', 0)

            # Memory limit
            limit = memory_stats.get('limit', 0)

            # Cache memory (should be subtracted from usage for accurate usage)
            cache = memory_stats.get('stats', {}).get('cache', 0)

            # Actual usage (excluding cache)
            actual_usage = usage - cache if usage > cache else usage

            return {
                'usage_bytes': usage,
                'actual_usage_bytes': actual_usage,
                'limit_bytes': limit,
                'cache_bytes': cache,
            }
        except (KeyError, TypeError) as e:
            logger.debug(f"Error parsing memory stats: {e}")
            return {
                'usage_bytes': 0,
                'actual_usage_bytes': 0,
                'limit_bytes': 0,
                'cache_bytes': 0,
            }

    def _parse_network_stats(self, stats: Dict[str, Any]) -> Dict[str, int]:
        """
        Parse network statistics.

        Args:
            stats: Raw stats from Docker API.

        Returns:
            Dictionary with network metrics in bytes.
        """
        try:
            networks = stats.get('networks', {})

            total_rx_bytes = 0
            total_tx_bytes = 0
            total_rx_packets = 0
            total_tx_packets = 0

            # Sum across all network interfaces
            for interface, net_stats in networks.items():
                total_rx_bytes += net_stats.get('rx_bytes', 0)
                total_tx_bytes += net_stats.get('tx_bytes', 0)
                total_rx_packets += net_stats.get('rx_packets', 0)
                total_tx_packets += net_stats.get('tx_packets', 0)

            return {
                'rx_bytes': total_rx_bytes,
                'tx_bytes': total_tx_bytes,
                'rx_packets': total_rx_packets,
                'tx_packets': total_tx_packets,
            }
        except (KeyError, TypeError) as e:
            logger.debug(f"Error parsing network stats: {e}")
            return {
                'rx_bytes': 0,
                'tx_bytes': 0,
                'rx_packets': 0,
                'tx_packets': 0,
            }

    def _parse_blkio_stats(self, stats: Dict[str, Any]) -> Dict[str, int]:
        """
        Parse block I/O statistics.

        Args:
            stats: Raw stats from Docker API.

        Returns:
            Dictionary with block I/O metrics in bytes.
        """
        try:
            blkio_stats = stats.get('blkio_stats', {})

            # Get I/O service bytes
            io_service_bytes = blkio_stats.get('io_service_bytes_recursive', [])

            total_read_bytes = 0
            total_write_bytes = 0

            # Sum read and write operations
            for entry in io_service_bytes:
                op = entry.get('op', '')
                value = entry.get('value', 0)

                if op.lower() == 'read':
                    total_read_bytes += value
                elif op.lower() == 'write':
                    total_write_bytes += value

            return {
                'read_bytes': total_read_bytes,
                'write_bytes': total_write_bytes,
            }
        except (KeyError, TypeError) as e:
            logger.debug(f"Error parsing blkio stats: {e}")
            return {
                'read_bytes': 0,
                'write_bytes': 0,
            }

    def get_container_labels(self, container: docker.models.containers.Container) -> Dict[str, str]:
        """
        Get container metadata for Prometheus labels.

        Args:
            container: Docker container object.

        Returns:
            Dictionary with container metadata.
        """
        try:
            # Get container name (remove leading / if present)
            name = container.name
            if name.startswith('/'):
                name = name[1:]

            # Get image name
            image = 'unknown'
            if container.image and container.image.tags:
                image = container.image.tags[0]
            elif hasattr(container.image, 'id'):
                image = container.image.id[:12]

            # Get short container ID
            container_id = container.id[:12] if container.id else 'unknown'

            return {
                'name': name,
                'image': image,
                'id': container_id,
            }
        except Exception as e:
            logger.error(f"Error getting container labels: {e}")
            return {
                'name': 'unknown',
                'image': 'unknown',
                'id': 'unknown',
            }

    def close(self):
        """Close the Docker client connection."""
        try:
            self.client.close()
            logger.info("Docker client connection closed")
        except Exception as e:
            logger.error(f"Error closing Docker client: {e}")

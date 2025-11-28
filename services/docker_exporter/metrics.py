"""
Prometheus metrics definitions for Docker container statistics.

This module defines all Prometheus metrics that will be exposed by the exporter,
matching the format expected by the Infrastructure Overview dashboard.
"""

from prometheus_client import Counter, Gauge, Info


# Container lifecycle metric
# Stores the timestamp when the container was last seen
container_last_seen = Gauge(
    'container_last_seen',
    'Timestamp when the container was last seen',
    ['name', 'image', 'id']
)

# CPU metrics
# Total CPU time consumed by the container in seconds (cumulative counter)
container_cpu_usage_seconds_total = Counter(
    'container_cpu_usage_seconds_total',
    'Total CPU time consumed in seconds',
    ['name', 'image', 'id']
)

# Memory metrics
# Current memory usage in bytes
container_memory_usage_bytes = Gauge(
    'container_memory_usage_bytes',
    'Current memory usage in bytes',
    ['name', 'image', 'id']
)

# Network metrics - Receive
# Total bytes received by the container (cumulative counter)
container_network_receive_bytes_total = Counter(
    'container_network_receive_bytes_total',
    'Total bytes received',
    ['name', 'image', 'id']
)

# Network metrics - Transmit
# Total bytes transmitted by the container (cumulative counter)
container_network_transmit_bytes_total = Counter(
    'container_network_transmit_bytes_total',
    'Total bytes transmitted',
    ['name', 'image', 'id']
)

# Disk I/O metrics - Read
# Total bytes read from disk (cumulative counter)
container_fs_reads_bytes_total = Counter(
    'container_fs_reads_bytes_total',
    'Total bytes read from disk',
    ['name', 'image', 'id']
)

# Disk I/O metrics - Write
# Total bytes written to disk (cumulative counter)
container_fs_writes_bytes_total = Counter(
    'container_fs_writes_bytes_total',
    'Total bytes written to disk',
    ['name', 'image', 'id']
)

# Additional useful metrics (not required by dashboard but good to have)

# Container state (0 = exited, 1 = running)
container_state = Gauge(
    'container_state',
    'Container state (0=exited, 1=running)',
    ['name', 'image', 'id']
)

# Exporter health metrics
exporter_scrape_duration_seconds = Gauge(
    'docker_exporter_scrape_duration_seconds',
    'Time taken to scrape Docker stats'
)

exporter_containers_scraped = Gauge(
    'docker_exporter_containers_scraped',
    'Number of containers successfully scraped'
)

exporter_scrape_errors_total = Counter(
    'docker_exporter_scrape_errors_total',
    'Total number of scrape errors',
    ['error_type']
)


class MetricsTracker:
    """
    Tracks previous metric values to calculate deltas for Counter metrics.

    Since Prometheus Counters should only increase, we need to track previous
    values and only update when there's a positive delta.
    """

    def __init__(self):
        self._previous_values = {}

    def _get_key(self, container_id: str, metric_name: str) -> str:
        """Generate a unique key for tracking metric values."""
        return f"{container_id}:{metric_name}"

    def update_counter_metric(self, counter, labels: dict, current_value: float, metric_name: str):
        """
        Update a Prometheus Counter metric with proper delta calculation.

        Args:
            counter: Prometheus Counter object
            labels: Label dictionary for the metric
            current_value: Current cumulative value
            metric_name: Name of the metric for tracking
        """
        container_id = labels['id']
        key = self._get_key(container_id, metric_name)

        # Get previous value
        previous_value = self._previous_values.get(key, 0)

        # Calculate delta
        delta = current_value - previous_value

        # Only update if delta is positive (handle container restarts)
        if delta > 0:
            counter.labels(**labels).inc(delta)
        elif delta < 0:
            # Container was likely restarted, reset our tracking
            # Note: Prometheus counters can't decrease, so we just track the new value
            pass

        # Store current value for next iteration
        self._previous_values[key] = current_value

    def update_gauge_metric(self, gauge, labels: dict, value: float):
        """
        Update a Prometheus Gauge metric.

        Args:
            gauge: Prometheus Gauge object
            labels: Label dictionary for the metric
            value: Current value
        """
        gauge.labels(**labels).set(value)

    def remove_container_metrics(self, container_id: str):
        """
        Remove tracked metrics for a container (when it stops).

        Args:
            container_id: Container ID
        """
        keys_to_remove = [k for k in self._previous_values.keys() if k.startswith(f"{container_id}:")]
        for key in keys_to_remove:
            del self._previous_values[key]

    def clear_stale_containers(self, active_container_ids: set):
        """
        Clear metrics for containers that no longer exist.

        Args:
            active_container_ids: Set of currently active container IDs
        """
        all_tracked = {k.split(':')[0] for k in self._previous_values.keys()}
        stale_containers = all_tracked - active_container_ids

        for container_id in stale_containers:
            self.remove_container_metrics(container_id)

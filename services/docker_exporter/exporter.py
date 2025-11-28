"""
Main Docker Stats Exporter application.

This module implements the HTTP server and metrics collection loop that
exposes Docker container statistics in Prometheus format.
"""

import os
import sys
import time
import logging
import threading
import signal
from typing import Optional

from flask import Flask, Response
from prometheus_client import generate_latest, REGISTRY, CONTENT_TYPE_LATEST
from docker.errors import DockerException

from docker_exporter.docker_client import DockerStatsCollector
from docker_exporter import metrics
from docker_exporter.metrics import MetricsTracker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class DockerMetricsExporter:
    """Main exporter class that collects and exposes Docker metrics."""

    def __init__(
        self,
        poll_interval: int = 15,
        port: int = 8003,
        socket_path: Optional[str] = None
    ):
        """
        Initialize the Docker metrics exporter.

        Args:
            poll_interval: Seconds between metric collection cycles
            port: HTTP port to expose metrics on
            socket_path: Optional Docker socket path
        """
        self.poll_interval = poll_interval
        self.port = port
        self.socket_path = socket_path
        self.running = False
        self.collection_thread = None
        self.docker_client = None
        self.metrics_tracker = MetricsTracker()

        # Flask app for HTTP server
        self.app = Flask(__name__)
        self._setup_routes()

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _setup_routes(self):
        """Setup Flask routes."""

        @self.app.route('/metrics')
        def metrics_endpoint():
            """Prometheus metrics endpoint."""
            return Response(generate_latest(REGISTRY), mimetype=CONTENT_TYPE_LATEST)

        @self.app.route('/health')
        def health():
            """Health check endpoint."""
            if self.docker_client:
                try:
                    self.docker_client.client.ping()
                    return {'status': 'healthy', 'docker': 'connected'}, 200
                except DockerException:
                    return {'status': 'unhealthy', 'docker': 'disconnected'}, 503
            return {'status': 'initializing'}, 503

        @self.app.route('/')
        def root():
            """Root endpoint with information."""
            return {
                'name': 'Docker Stats Exporter',
                'version': '1.0.0',
                'endpoints': {
                    '/metrics': 'Prometheus metrics',
                    '/health': 'Health check'
                }
            }

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
        sys.exit(0)

    def start(self):
        """Start the exporter."""
        logger.info("Starting Docker Stats Exporter...")
        logger.info(f"Poll interval: {self.poll_interval} seconds")
        logger.info(f"HTTP port: {self.port}")

        # Initialize Docker client
        try:
            self.docker_client = DockerStatsCollector(self.socket_path)
        except DockerException as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            logger.error("Make sure Docker socket is mounted and accessible")
            sys.exit(1)

        # Start collection thread
        self.running = True
        self.collection_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self.collection_thread.start()
        logger.info("Metrics collection thread started")

        # Start HTTP server
        logger.info(f"Starting HTTP server on port {self.port}...")
        try:
            self.app.run(host='0.0.0.0', port=self.port, threaded=True)
        except Exception as e:
            logger.error(f"Failed to start HTTP server: {e}")
            self.stop()
            sys.exit(1)

    def stop(self):
        """Stop the exporter."""
        logger.info("Stopping Docker Stats Exporter...")
        self.running = False

        if self.collection_thread:
            self.collection_thread.join(timeout=5)

        if self.docker_client:
            self.docker_client.close()

        logger.info("Exporter stopped")

    def _collection_loop(self):
        """Main metrics collection loop."""
        logger.info("Metrics collection loop started")

        while self.running:
            try:
                start_time = time.time()
                self._collect_metrics()
                duration = time.time() - start_time

                # Update exporter metrics
                metrics.exporter_scrape_duration_seconds.set(duration)

                logger.debug(f"Metrics collection completed in {duration:.2f} seconds")

                # Sleep until next collection
                sleep_time = max(0, self.poll_interval - duration)
                time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Error in collection loop: {e}", exc_info=True)
                metrics.exporter_scrape_errors_total.labels(error_type='collection_loop').inc()
                time.sleep(self.poll_interval)

    def _collect_metrics(self):
        """Collect metrics from all containers."""
        try:
            # Get all containers
            containers = self.docker_client.get_all_containers(include_stopped=False)
            logger.debug(f"Collecting metrics for {len(containers)} containers")

            containers_scraped = 0
            active_container_ids = set()

            for container in containers:
                try:
                    # Get container labels
                    labels = self.docker_client.get_container_labels(container)
                    container_id = labels['id']
                    active_container_ids.add(container_id)

                    # Get container stats
                    stats = self.docker_client.get_container_stats(container)

                    if stats is None:
                        logger.warning(f"No stats available for container {labels['name']}")
                        continue

                    # Update metrics
                    self._update_metrics(labels, stats)
                    containers_scraped += 1

                except Exception as e:
                    logger.error(f"Error collecting metrics for container: {e}")
                    metrics.exporter_scrape_errors_total.labels(error_type='container_stats').inc()

            # Update exporter metrics
            metrics.exporter_containers_scraped.set(containers_scraped)

            # Clean up stale container metrics
            self.metrics_tracker.clear_stale_containers(active_container_ids)

            logger.info(f"Successfully scraped {containers_scraped}/{len(containers)} containers")

        except Exception as e:
            logger.error(f"Error collecting metrics: {e}", exc_info=True)
            metrics.exporter_scrape_errors_total.labels(error_type='docker_api').inc()

    def _update_metrics(self, labels: dict, stats: dict):
        """
        Update Prometheus metrics with container stats.

        Args:
            labels: Container label dictionary
            stats: Parsed stats dictionary
        """
        # Update last seen timestamp
        self.metrics_tracker.update_gauge_metric(
            metrics.container_last_seen,
            labels,
            stats['timestamp']
        )

        # Update container state (1 = running)
        self.metrics_tracker.update_gauge_metric(
            metrics.container_state,
            labels,
            1.0
        )

        # Update CPU metrics
        cpu_stats = stats.get('cpu', {})
        self.metrics_tracker.update_counter_metric(
            metrics.container_cpu_usage_seconds_total,
            labels,
            cpu_stats.get('total_usage_seconds', 0),
            'cpu_usage_seconds'
        )

        # Update memory metrics
        memory_stats = stats.get('memory', {})
        self.metrics_tracker.update_gauge_metric(
            metrics.container_memory_usage_bytes,
            labels,
            memory_stats.get('usage_bytes', 0)
        )

        # Update network metrics
        network_stats = stats.get('network', {})
        self.metrics_tracker.update_counter_metric(
            metrics.container_network_receive_bytes_total,
            labels,
            network_stats.get('rx_bytes', 0),
            'network_rx_bytes'
        )
        self.metrics_tracker.update_counter_metric(
            metrics.container_network_transmit_bytes_total,
            labels,
            network_stats.get('tx_bytes', 0),
            'network_tx_bytes'
        )

        # Update disk I/O metrics
        blkio_stats = stats.get('blkio', {})
        self.metrics_tracker.update_counter_metric(
            metrics.container_fs_reads_bytes_total,
            labels,
            blkio_stats.get('read_bytes', 0),
            'fs_read_bytes'
        )
        self.metrics_tracker.update_counter_metric(
            metrics.container_fs_writes_bytes_total,
            labels,
            blkio_stats.get('write_bytes', 0),
            'fs_write_bytes'
        )


def main():
    """Main entry point."""
    # Get configuration from environment variables
    poll_interval = int(os.getenv('POLL_INTERVAL', '15'))
    port = int(os.getenv('EXPORTER_PORT', '8003'))
    socket_path = os.getenv('DOCKER_SOCKET_PATH')

    logger.info("Docker Stats Exporter v1.0.0")
    logger.info(f"Configuration: poll_interval={poll_interval}s, port={port}")

    # Create and start exporter
    exporter = DockerMetricsExporter(
        poll_interval=poll_interval,
        port=port,
        socket_path=socket_path
    )

    try:
        exporter.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
        exporter.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        exporter.stop()
        sys.exit(1)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Prometheus Metrics Exporter for GSC Warehouse

Exposes metrics at /metrics endpoint for Prometheus scraping
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from flask import Flask, Response
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
WAREHOUSE_DSN = os.environ.get('WAREHOUSE_DSN', 'postgresql://gsc_user:gsc_pass@warehouse:5432/gsc_db')
SCHEDULER_METRICS_FILE = '/logs/scheduler_metrics.json'

def get_db_connection():
    """Get database connection"""
    try:
        return psycopg2.connect(WAREHOUSE_DSN)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def get_warehouse_metrics():
    """Get warehouse metrics from database"""
    metrics = {}
    conn = get_db_connection()
    if not conn:
        return metrics
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Total rows in fact table
            cur.execute("SELECT COUNT(*) as total_rows FROM fact_gsc_daily")
            metrics['fact_table_total_rows'] = cur.fetchone()['total_rows']
            
            # Rows by date range
            cur.execute("""
                SELECT 
                    COUNT(*) as last_7d_rows
                FROM fact_gsc_daily
                WHERE date >= CURRENT_DATE - INTERVAL '7 days'
            """)
            metrics['fact_table_last_7d_rows'] = cur.fetchone()['last_7d_rows']
            
            cur.execute("""
                SELECT 
                    COUNT(*) as last_30d_rows
                FROM fact_gsc_daily
                WHERE date >= CURRENT_DATE - INTERVAL '30 days'
            """)
            metrics['fact_table_last_30d_rows'] = cur.fetchone()['last_30d_rows']
            
            # Property count
            cur.execute("SELECT COUNT(DISTINCT property) as property_count FROM fact_gsc_daily")
            metrics['total_properties'] = cur.fetchone()['property_count']
            
            # Latest data date
            cur.execute("SELECT MAX(date) as latest_date FROM fact_gsc_daily")
            latest = cur.fetchone()['latest_date']
            if latest:
                days_old = (datetime.now().date() - latest).days
                metrics['data_freshness_days'] = days_old
            
            # Watermark metrics
            cur.execute("""
                SELECT 
                    COUNT(*) as watermark_count,
                    AVG(CURRENT_DATE - last_date) as avg_days_behind
                FROM ingest_watermarks
            """)
            wm = cur.fetchone()
            metrics['watermark_count'] = wm['watermark_count']
            metrics['watermark_avg_days_behind'] = float(wm['avg_days_behind'] or 0)
            
    except Exception as e:
        logger.error(f"Error fetching warehouse metrics: {e}")
    finally:
        conn.close()
    
    return metrics

def get_scheduler_metrics():
    """Get scheduler metrics from file"""
    metrics = {}
    try:
        if os.path.exists(SCHEDULER_METRICS_FILE):
            with open(SCHEDULER_METRICS_FILE, 'r') as f:
                data = json.load(f)
                metrics['daily_runs_count'] = data.get('daily_runs_count', 0)
                metrics['weekly_runs_count'] = data.get('weekly_runs_count', 0)
                
                # Task success counts
                tasks = data.get('tasks', {})
                for task_name, task_data in tasks.items():
                    safe_name = task_name.replace(' ', '_').replace('-', '_').lower()
                    if task_data['status'] == 'success':
                        metrics[f'task_{safe_name}_success'] = 1
                    else:
                        metrics[f'task_{safe_name}_success'] = 0
                    
                    if task_data.get('duration_seconds'):
                        metrics[f'task_{safe_name}_duration_seconds'] = task_data['duration_seconds']
    except Exception as e:
        logger.error(f"Error reading scheduler metrics: {e}")
    
    return metrics

def format_prometheus_metrics(metrics):
    """Format metrics in Prometheus exposition format"""
    lines = []
    
    # Add metadata
    lines.append("# HELP gsc_warehouse_up Warehouse health status (1=up, 0=down)")
    lines.append("# TYPE gsc_warehouse_up gauge")
    
    # Check if we have any metrics (indicates warehouse is up)
    if metrics:
        lines.append("gsc_warehouse_up 1")
    else:
        lines.append("gsc_warehouse_up 0")
    
    # Format each metric
    for key, value in metrics.items():
        # Skip None values
        if value is None:
            continue
        
        # Add metric
        metric_name = f"gsc_{key}"
        lines.append(f"# TYPE {metric_name} gauge")
        lines.append(f"{metric_name} {value}")
    
    # Add timestamp
    lines.append(f"# Generated at {datetime.utcnow().isoformat()}")
    
    return '\n'.join(lines) + '\n'

@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint"""
    try:
        # Gather all metrics
        warehouse_metrics = get_warehouse_metrics()
        scheduler_metrics = get_scheduler_metrics()
        
        all_metrics = {**warehouse_metrics, **scheduler_metrics}
        
        # Format for Prometheus
        output = format_prometheus_metrics(all_metrics)
        
        return Response(output, mimetype='text/plain')
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        return Response(f"# Error: {str(e)}\n", mimetype='text/plain', status=500)

@app.route('/health')
def health():
    """Health check endpoint"""
    conn = get_db_connection()
    if conn:
        conn.close()
        return {'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}
    else:
        return {'status': 'unhealthy', 'timestamp': datetime.utcnow().isoformat()}, 503

@app.route('/')
def index():
    """Root endpoint"""
    return {
        'service': 'GSC Warehouse Metrics Exporter',
        'endpoints': {
            '/metrics': 'Prometheus metrics',
            '/health': 'Health check'
        }
    }

if __name__ == '__main__':
    logger.info("Starting GSC Warehouse Metrics Exporter")
    app.run(host='0.0.0.0', port=9090, debug=False)

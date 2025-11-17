FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY metrics_exporter/requirements.txt /app/metrics_exporter/
RUN pip install --no-cache-dir -r /app/metrics_exporter/requirements.txt

# Copy exporter code
COPY metrics_exporter/ /app/metrics_exporter/

# Expose metrics port
EXPOSE 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:9090/metrics || exit 1

# Run exporter
CMD ["python", "/app/metrics_exporter/exporter.py"]

FROM prom/prometheus:latest

# Copy Prometheus configuration
COPY prometheus/prometheus.yml /etc/prometheus/prometheus.yml

# Expose Prometheus port
EXPOSE 9091

# Run Prometheus with custom config
CMD ["--config.file=/etc/prometheus/prometheus.yml", \
     "--storage.tsdb.path=/prometheus", \
     "--web.console.libraries=/usr/share/prometheus/console_libraries", \
     "--web.console.templates=/usr/share/prometheus/consoles", \
     "--web.listen-address=:9091"]

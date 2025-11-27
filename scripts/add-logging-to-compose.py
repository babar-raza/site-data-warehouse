#!/usr/bin/env python3
"""
Add logging configuration to all services in docker-compose.yml
"""

import yaml
import sys
from pathlib import Path

def add_logging_config(service_config):
    """Add logging configuration if not present"""
    if 'logging' not in service_config:
        service_config['logging'] = {
            'driver': 'json-file',
            'options': {
                'max-size': '10m',
                'max-file': '3'
            }
        }
    return service_config

def add_tmpfs(service_config, size='64M'):
    """Add tmpfs mount if not present"""
    if 'tmpfs' not in service_config:
        service_config['tmpfs'] = [f'/tmp:size={size}']
    return service_config

def main():
    compose_file = Path('docker-compose.yml')

    if not compose_file.exists():
        print("Error: docker-compose.yml not found")
        sys.exit(1)

    print("Reading docker-compose.yml...")
    with open(compose_file, 'r') as f:
        compose_data = yaml.safe_load(f)

    if 'services' not in compose_data:
        print("Error: No services found in docker-compose.yml")
        sys.exit(1)

    # Tmpfs size mapping
    tmpfs_sizes = {
        'warehouse': '256M',
        'ollama': '512M',
        'celery_worker': '256M',
        'insights_engine': '256M',
        'scheduler': '256M',
    }

    print(f"Processing {len(compose_data['services'])} services...")

    for service_name, service_config in compose_data['services'].items():
        print(f"  - {service_name}")

        # Add logging
        service_config = add_logging_config(service_config)

        # Add tmpfs with appropriate size
        size = tmpfs_sizes.get(service_name, '64M')
        service_config = add_tmpfs(service_config, size)

        compose_data['services'][service_name] = service_config

    # Backup original
    backup_file = compose_file.with_suffix('.yml.bak')
    print(f"\nBacking up to {backup_file}...")
    with open(backup_file, 'w') as f:
        f.write(compose_file.read_text())

    # Write updated file
    print("Writing updated docker-compose.yml...")
    with open(compose_file, 'w') as f:
        yaml.dump(compose_data, f, default_flow_style=False, sort_keys=False)

    print("\n✓ Successfully updated docker-compose.yml")
    print("  - Added logging configuration to all services")
    print("  - Added tmpfs mounts to all services")
    print(f"  - Backup saved to {backup_file}")

if __name__ == '__main__':
    main()

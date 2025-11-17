#!/bin/bash
# View service logs
if [ -z "$1" ]; then
    echo "Usage: ./logs.sh <service-name>"
    echo "Services: warehouse, insights_engine, mcp, dispatcher"
    echo "Or: ./logs.sh all"
    exit 1
fi

if [ "$1" == "all" ]; then
    docker-compose logs -f
else
    docker-compose logs -f $1
fi

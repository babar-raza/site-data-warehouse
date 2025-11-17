@echo off
REM Stop all services
echo Stopping services...
docker-compose down
echo ✅ Services stopped

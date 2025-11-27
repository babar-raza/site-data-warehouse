@echo off
setlocal EnableDelayedExpansion

REM ============================================================================
REM Service Wait Script - Windows
REM ============================================================================
REM Wait for all critical services to be healthy before proceeding
REM
REM Usage:
REM   wait-for-services.bat [--timeout SECONDS] [--verbose]
REM
REM Options:
REM   --timeout SECONDS   Maximum time to wait (default: 120)
REM   --verbose          Show detailed status information
REM   --help             Display this help message
REM
REM Exit Codes:
REM   0 - All services healthy
REM   1 - Timeout reached or service check failed
REM
REM Services Monitored:
REM   - PostgreSQL (port 5432)
REM   - Redis (port 6379, optional)
REM   - Insights API (port 8000)
REM   - Grafana (port 3000)
REM   - Prometheus (port 9090)
REM ============================================================================

REM ============================================================================
REM CONFIGURATION
REM ============================================================================

REM Default values
set "TIMEOUT=120"
set "VERBOSE=false"

REM Service configuration (with defaults)
if not defined DB_HOST set "DB_HOST=localhost"
if not defined POSTGRES_PORT set "POSTGRES_PORT=5432"
if not defined POSTGRES_USER set "POSTGRES_USER=gsc_user"
if not defined POSTGRES_DB set "POSTGRES_DB=gsc_db"

if not defined REDIS_HOST set "REDIS_HOST=localhost"
if not defined REDIS_PORT set "REDIS_PORT=6379"

if not defined API_HOST set "API_HOST=localhost"
if not defined API_PORT set "API_PORT=8000"

if not defined GRAFANA_HOST set "GRAFANA_HOST=localhost"
if not defined GRAFANA_PORT set "GRAFANA_PORT=3000"

if not defined PROMETHEUS_HOST set "PROMETHEUS_HOST=localhost"
if not defined PROMETHEUS_PORT set "PROMETHEUS_PORT=9090"

REM ============================================================================
REM PARSE ARGUMENTS
REM ============================================================================

goto parse_args

:parse_args
if "%~1"=="" goto start_checks
if /i "%~1"=="--timeout" (
    set "TIMEOUT=%~2"
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--verbose" (
    set "VERBOSE=true"
    shift
    goto parse_args
)
if /i "%~1"=="--help" (
    call :show_help
    exit /b 0
)
echo Unknown option: %~1
echo Use --help for usage information
exit /b 1

:start_checks

REM Validate timeout is a number
echo %TIMEOUT%| findstr /r "^[0-9][0-9]*$" >nul
if errorlevel 1 (
    call :print_error "Invalid timeout value: %TIMEOUT%"
    exit /b 1
)

REM ============================================================================
REM MAIN LOGIC
REM ============================================================================

call :print_info "Waiting for services to be healthy (timeout: %TIMEOUT%s)..."
echo.

REM Get start time
set START_TIME=%TIME%
set /a ELAPSED=0

:wait_loop
    REM Check all services
    call :check_all_services
    if !ERRORLEVEL! equ 0 (
        echo.
        call :print_success "All services are healthy!"
        echo.
        echo Service Status:
        echo   PostgreSQL  : http://%DB_HOST%:%POSTGRES_PORT%
        echo   Insights API: http://%API_HOST%:%API_PORT%
        echo   Grafana     : http://%GRAFANA_HOST%:%GRAFANA_PORT%
        echo   Prometheus  : http://%PROMETHEUS_HOST%:%PROMETHEUS_PORT%

        REM Check if Redis is running
        call :check_port %REDIS_HOST% %REDIS_PORT% >nul 2>&1
        if !ERRORLEVEL! equ 0 (
            echo   Redis       : %REDIS_HOST%:%REDIS_PORT%
        )
        echo.
        exit /b 0
    )

    REM Wait 2 seconds before next check
    timeout /t 2 /nobreak >nul

    REM Calculate elapsed time
    call :get_elapsed_time

    REM Show progress every 10 seconds
    set /a "MOD=!ELAPSED! %% 10"
    if !MOD! equ 0 if !ELAPSED! gtr 0 (
        set /a "REMAINING=!TIMEOUT! - !ELAPSED!"
        call :print_info "Still waiting... (!ELAPSED!s elapsed, !REMAINING!s remaining)"
    )

    REM Check timeout
    if !ELAPSED! geq %TIMEOUT% goto timeout_reached

    goto wait_loop

:timeout_reached
echo.
call :print_error "Timeout reached after %TIMEOUT%s"
echo.
echo Service status:

REM Show final status for each service
call :check_port %DB_HOST% %POSTGRES_PORT% >nul 2>&1
if !ERRORLEVEL! equ 0 (
    echo   PostgreSQL  : REACHABLE
) else (
    echo   PostgreSQL  : NOT REACHABLE
)

call :check_port %API_HOST% %API_PORT% >nul 2>&1
if !ERRORLEVEL! equ 0 (
    echo   Insights API: REACHABLE
) else (
    echo   Insights API: NOT REACHABLE
)

call :check_port %GRAFANA_HOST% %GRAFANA_PORT% >nul 2>&1
if !ERRORLEVEL! equ 0 (
    echo   Grafana     : REACHABLE
) else (
    echo   Grafana     : NOT REACHABLE
)

call :check_port %PROMETHEUS_HOST% %PROMETHEUS_PORT% >nul 2>&1
if !ERRORLEVEL! equ 0 (
    echo   Prometheus  : REACHABLE
) else (
    echo   Prometheus  : NOT REACHABLE
)

echo.
echo Troubleshooting:
echo   1. Check if services are running: docker-compose ps
echo   2. Check service logs: docker-compose logs [service-name]
echo   3. Verify environment variables are set correctly
echo   4. Ensure ports are not blocked by firewall
echo.
exit /b 1

REM ============================================================================
REM FUNCTIONS
REM ============================================================================

:show_help
echo Service Wait Script - Windows
echo.
echo Wait for all critical services to be healthy before proceeding.
echo.
echo Usage:
echo     %~nx0 [OPTIONS]
echo.
echo Options:
echo     --timeout SECONDS   Maximum time to wait in seconds (default: 120)
echo     --verbose          Show detailed status information
echo     --help             Display this help message
echo.
echo Environment Variables:
echo     DB_HOST            PostgreSQL host (default: localhost)
echo     POSTGRES_PORT      PostgreSQL port (default: 5432)
echo     POSTGRES_USER      PostgreSQL user (default: gsc_user)
echo     POSTGRES_DB        PostgreSQL database (default: gsc_db)
echo     REDIS_HOST         Redis host (default: localhost)
echo     REDIS_PORT         Redis port (default: 6379)
echo     API_HOST           API host (default: localhost)
echo     API_PORT           API port (default: 8000)
echo     GRAFANA_HOST       Grafana host (default: localhost)
echo     GRAFANA_PORT       Grafana port (default: 3000)
echo     PROMETHEUS_HOST    Prometheus host (default: localhost)
echo     PROMETHEUS_PORT    Prometheus port (default: 9090)
echo.
echo Exit Codes:
echo     0                  All services healthy
echo     1                  Timeout reached or service check failed
echo.
echo Examples:
echo     REM Wait with default timeout (120s)
echo     %~nx0
echo.
echo     REM Wait with custom timeout
echo     %~nx0 --timeout 60
echo.
echo     REM Wait with verbose output
echo     %~nx0 --verbose --timeout 180
echo.
exit /b 0

:print_info
echo [INFO] %~1
exit /b 0

:print_success
echo [SUCCESS] %~1
exit /b 0

:print_waiting
echo [WAITING] %~1
exit /b 0

:print_error
echo [ERROR] %~1
exit /b 0

:verbose
if /i "%VERBOSE%"=="true" (
    call :print_info "%~1"
)
exit /b 0

:check_port
REM Check if a port is open using PowerShell
REM Usage: call :check_port HOST PORT
set "host=%~1"
set "port=%~2"

powershell -Command "try { $tcp = New-Object System.Net.Sockets.TcpClient('%host%', %port%); $tcp.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
exit /b %ERRORLEVEL%

:check_postgres
call :verbose "Checking PostgreSQL at %DB_HOST%:%POSTGRES_PORT%..."

REM Check if port is open
call :check_port %DB_HOST% %POSTGRES_PORT%
if !ERRORLEVEL! neq 0 (
    call :verbose "PostgreSQL port not reachable"
    exit /b 1
)

REM Try to connect using psql if available
where psql >nul 2>&1
if !ERRORLEVEL! equ 0 (
    set "PGPASSWORD=%POSTGRES_PASSWORD%"
    if not defined POSTGRES_PASSWORD set "PGPASSWORD=gsc_pass"

    psql -h %DB_HOST% -p %POSTGRES_PORT% -U %POSTGRES_USER% -d %POSTGRES_DB% -c "SELECT 1" >nul 2>&1
    exit /b !ERRORLEVEL!
)

REM If psql not available, port check is sufficient
exit /b 0

:check_redis
call :verbose "Checking Redis at %REDIS_HOST%:%REDIS_PORT%..."

REM Check if port is open
call :check_port %REDIS_HOST% %REDIS_PORT%
if !ERRORLEVEL! neq 0 (
    call :verbose "Redis port not reachable (optional service)"
    exit /b 0
)

REM Try to ping Redis if redis-cli is available
where redis-cli >nul 2>&1
if !ERRORLEVEL! equ 0 (
    redis-cli -h %REDIS_HOST% -p %REDIS_PORT% ping >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        exit /b 0
    ) else (
        call :verbose "Redis ping failed (optional service)"
        exit /b 0
    )
)

exit /b 0

:check_api
call :verbose "Checking Insights API at %API_HOST%:%API_PORT%..."

REM Check if port is open
call :check_port %API_HOST% %API_PORT%
if !ERRORLEVEL! neq 0 (
    call :verbose "API port not reachable"
    exit /b 1
)

REM Try health endpoint using curl or PowerShell
where curl >nul 2>&1
if !ERRORLEVEL! equ 0 (
    curl -s -f -m 5 "http://%API_HOST%:%API_PORT%/health" >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        call :verbose "API health check passed"
        exit /b 0
    ) else (
        call :verbose "API health endpoint not responding"
        exit /b 1
    )
)

REM Fallback to PowerShell
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://%API_HOST%:%API_PORT%/health' -TimeoutSec 5 -UseBasicParsing; exit 0 } catch { exit 1 }" >nul 2>&1
if !ERRORLEVEL! equ 0 (
    call :verbose "API health check passed"
    exit /b 0
)

REM If health check fails but port is open, return success (service might not have /health endpoint yet)
exit /b 0

:check_grafana
call :verbose "Checking Grafana at %GRAFANA_HOST%:%GRAFANA_PORT%..."

REM Check if port is open
call :check_port %GRAFANA_HOST% %GRAFANA_PORT%
if !ERRORLEVEL! neq 0 (
    call :verbose "Grafana port not reachable"
    exit /b 1
)

REM Try API endpoint using curl or PowerShell
where curl >nul 2>&1
if !ERRORLEVEL! equ 0 (
    curl -s -f -m 5 "http://%GRAFANA_HOST%:%GRAFANA_PORT%/api/health" >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        call :verbose "Grafana health check passed"
        exit /b 0
    )
)

REM Fallback to PowerShell
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://%GRAFANA_HOST%:%GRAFANA_PORT%/api/health' -TimeoutSec 5 -UseBasicParsing; exit 0 } catch { exit 1 }" >nul 2>&1
if !ERRORLEVEL! equ 0 (
    call :verbose "Grafana health check passed"
    exit /b 0
)

REM Try root endpoint
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://%GRAFANA_HOST%:%GRAFANA_PORT%/' -TimeoutSec 5 -UseBasicParsing; exit 0 } catch { exit 1 }" >nul 2>&1
exit /b !ERRORLEVEL!

:check_prometheus
call :verbose "Checking Prometheus at %PROMETHEUS_HOST%:%PROMETHEUS_PORT%..."

REM Check if port is open
call :check_port %PROMETHEUS_HOST% %PROMETHEUS_PORT%
if !ERRORLEVEL! neq 0 (
    call :verbose "Prometheus port not reachable"
    exit /b 1
)

REM Try health endpoint using curl or PowerShell
where curl >nul 2>&1
if !ERRORLEVEL! equ 0 (
    curl -s -f -m 5 "http://%PROMETHEUS_HOST%:%PROMETHEUS_PORT%/-/healthy" >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        call :verbose "Prometheus health check passed"
        exit /b 0
    )
)

REM Fallback to PowerShell
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://%PROMETHEUS_HOST%:%PROMETHEUS_PORT%/-/healthy' -TimeoutSec 5 -UseBasicParsing; exit 0 } catch { exit 1 }" >nul 2>&1
if !ERRORLEVEL! equ 0 (
    call :verbose "Prometheus health check passed"
    exit /b 0
)

REM Try root endpoint
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://%PROMETHEUS_HOST%:%PROMETHEUS_PORT%/' -TimeoutSec 5 -UseBasicParsing; exit 0 } catch { exit 1 }" >nul 2>&1
exit /b !ERRORLEVEL!

:check_all_services
set "all_healthy=true"

REM PostgreSQL (required)
call :check_postgres
if !ERRORLEVEL! equ 0 (
    call :verbose "PostgreSQL: HEALTHY"
) else (
    call :print_waiting "PostgreSQL not ready"
    set "all_healthy=false"
)

REM Redis (optional)
call :check_redis

REM API (required)
call :check_api
if !ERRORLEVEL! equ 0 (
    call :verbose "Insights API: HEALTHY"
) else (
    call :print_waiting "Insights API not ready"
    set "all_healthy=false"
)

REM Grafana (required)
call :check_grafana
if !ERRORLEVEL! equ 0 (
    call :verbose "Grafana: HEALTHY"
) else (
    call :print_waiting "Grafana not ready"
    set "all_healthy=false"
)

REM Prometheus (required)
call :check_prometheus
if !ERRORLEVEL! equ 0 (
    call :verbose "Prometheus: HEALTHY"
) else (
    call :print_waiting "Prometheus not ready"
    set "all_healthy=false"
)

if /i "%all_healthy%"=="true" (
    exit /b 0
) else (
    exit /b 1
)

:get_elapsed_time
REM Calculate elapsed time in seconds
set END_TIME=%TIME%

REM Convert times to seconds
call :time_to_seconds %START_TIME% START_SECONDS
call :time_to_seconds %END_TIME% END_SECONDS

REM Calculate difference
set /a ELAPSED=END_SECONDS - START_SECONDS

REM Handle midnight rollover
if !ELAPSED! lss 0 set /a ELAPSED=86400 + ELAPSED

exit /b 0

:time_to_seconds
REM Convert HH:MM:SS.MS to seconds
set "time_str=%~1"
set "return_var=%~2"

REM Extract hours, minutes, seconds
for /f "tokens=1-4 delims=:., " %%a in ("%time_str%") do (
    set /a "hours=10%%a %% 100"
    set /a "minutes=10%%b %% 100"
    set /a "seconds=10%%c %% 100"
)

REM Calculate total seconds
set /a "total_seconds=(hours * 3600) + (minutes * 60) + seconds"
set "%return_var%=%total_seconds%"

exit /b 0

@echo off
REM
REM Run Playwright Dashboard Tests (Windows)
REM
REM This script runs E2E tests for all 11 Grafana dashboards using Playwright.
REM Tests verify dashboards load correctly, have no errors, and display data.
REM
REM Usage:
REM   scripts\run-dashboard-tests.bat                    Run all tests (headless)
REM   scripts\run-dashboard-tests.bat --headed           Run with visible browser
REM   scripts\run-dashboard-tests.bat --browser firefox  Use Firefox
REM   scripts\run-dashboard-tests.bat --fast             Skip slow tests
REM   scripts\run-dashboard-tests.bat --report           Generate HTML report
REM
REM Environment Variables:
REM   GRAFANA_URL       - Grafana URL (default: http://localhost:3000)
REM   GRAFANA_USER      - Grafana username (default: admin)
REM   GRAFANA_PASSWORD  - Grafana password (default: admin)
REM   HEADLESS          - Run headless (default: true)
REM   BROWSER_TYPE      - Browser: chromium, firefox, webkit (default: chromium)

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

REM Default values
if not defined HEADLESS set "HEADLESS=true"
if not defined BROWSER_TYPE set "BROWSER_TYPE=chromium"
if not defined RECORD_VIDEO set "RECORD_VIDEO=false"
if not defined TRACE_ENABLED set "TRACE_ENABLED=false"
set "GENERATE_REPORT=false"
set "FAST_MODE=false"
set "VERBOSE=-v"

REM Parse arguments
:parse_args
if "%~1"=="" goto :args_done
if "%~1"=="--headed" (
    set "HEADLESS=false"
    shift
    goto :parse_args
)
if "%~1"=="--browser" (
    set "BROWSER_TYPE=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--record" (
    set "RECORD_VIDEO=true"
    shift
    goto :parse_args
)
if "%~1"=="--trace" (
    set "TRACE_ENABLED=true"
    shift
    goto :parse_args
)
if "%~1"=="--report" (
    set "GENERATE_REPORT=true"
    shift
    goto :parse_args
)
if "%~1"=="--fast" (
    set "FAST_MODE=true"
    shift
    goto :parse_args
)
if "%~1"=="--quiet" (
    set "VERBOSE="
    shift
    goto :parse_args
)
if "%~1"=="--help" (
    echo Usage: %~nx0 [OPTIONS]
    echo.
    echo Options:
    echo   --headed           Run with visible browser window
    echo   --browser TYPE     Browser to use: chromium, firefox, webkit
    echo   --record           Record test videos
    echo   --trace            Enable Playwright tracing
    echo   --report           Generate HTML test report
    echo   --fast             Skip slow tests
    echo   --quiet            Reduce output verbosity
    echo   --help             Show this help message
    echo.
    echo Environment Variables:
    echo   GRAFANA_URL        Grafana URL ^(default: http://localhost:3000^)
    echo   GRAFANA_USER       Grafana username ^(default: admin^)
    echo   GRAFANA_PASSWORD   Grafana password ^(default: admin^)
    exit /b 0
)
echo Unknown option: %~1
exit /b 1

:args_done

REM Create test output directories
if not exist "%PROJECT_ROOT%\test-results\screenshots" mkdir "%PROJECT_ROOT%\test-results\screenshots"
if not exist "%PROJECT_ROOT%\test-results\videos" mkdir "%PROJECT_ROOT%\test-results\videos"
if not exist "%PROJECT_ROOT%\test-results\traces" mkdir "%PROJECT_ROOT%\test-results\traces"
if not exist "%PROJECT_ROOT%\test-results\reports" mkdir "%PROJECT_ROOT%\test-results\reports"

echo ==============================================
echo Playwright Dashboard Tests
echo ==============================================
echo Browser:     %BROWSER_TYPE%
echo Headless:    %HEADLESS%
echo Record:      %RECORD_VIDEO%
echo Trace:       %TRACE_ENABLED%
if defined GRAFANA_URL (
    echo Grafana URL: %GRAFANA_URL%
) else (
    echo Grafana URL: http://localhost:3000
)
echo ==============================================

REM Check if Playwright is installed
python -c "import playwright" 2>nul
if errorlevel 1 (
    echo.
    echo Installing Playwright...
    pip install playwright pytest-playwright
    playwright install %BROWSER_TYPE%
)

REM Build pytest command
set "PYTEST_CMD=python -m pytest tests/e2e/test_dashboard_e2e.py %VERBOSE% --no-cov"

if "%FAST_MODE%"=="true" (
    set "PYTEST_CMD=%PYTEST_CMD% -m "not slow""
)

if "%GENERATE_REPORT%"=="true" (
    set "PYTEST_CMD=%PYTEST_CMD% --html=test-results/reports/dashboard_report.html --self-contained-html"
)

REM Change to project root
cd /d "%PROJECT_ROOT%"

echo.
echo Running: %PYTEST_CMD%
echo.

REM Run tests
%PYTEST_CMD%
set "TEST_EXIT_CODE=%errorlevel%"

REM Print summary
echo.
echo ==============================================
echo Test Results Summary
echo ==============================================

if exist "test-results\screenshots\*.png" (
    for /f %%A in ('dir /b /a-d "test-results\screenshots\*.png" 2^>nul ^| find /c /v ""') do (
        if %%A gtr 0 echo Screenshots:  %%A ^(test-results\screenshots\^)
    )
)

if "%RECORD_VIDEO%"=="true" (
    if exist "test-results\videos\*.webm" (
        for /f %%A in ('dir /b /a-d "test-results\videos\*.webm" 2^>nul ^| find /c /v ""') do (
            if %%A gtr 0 echo Videos:       %%A ^(test-results\videos\^)
        )
    )
)

if exist "test-results\reports\dashboard_report.html" (
    echo HTML Report:  test-results\reports\dashboard_report.html
)

echo ==============================================

exit /b %TEST_EXIT_CODE%

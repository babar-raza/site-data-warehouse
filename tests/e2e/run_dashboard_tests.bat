@echo off
REM Dashboard E2E Test Runner (Windows)
REM Usage: run_dashboard_tests.bat [options]

setlocal EnableDelayedExpansion

REM Configuration
set "GRAFANA_URL=http://localhost:3000"
set "GRAFANA_USER=admin"
set "GRAFANA_PASSWORD=admin"
set "HEADLESS=true"
set "BROWSER_TYPE=chromium"

REM Parse command line arguments
set "VERBOSE="
set "SPECIFIC_TEST="

:parse_args
if "%~1"=="" goto :check_env
if /I "%~1"=="-v" set "VERBOSE=-v -s"
if /I "%~1"=="--verbose" set "VERBOSE=-v -s"
if /I "%~1"=="-h" set "HEADLESS=false"
if /I "%~1"=="--headed" set "HEADLESS=false"
if /I "%~1"=="-b" (
    set "BROWSER_TYPE=%~2"
    shift
)
if /I "%~1"=="--browser" (
    set "BROWSER_TYPE=%~2"
    shift
)
if /I "%~1"=="-t" (
    set "SPECIFIC_TEST=-k %~2"
    shift
)
if /I "%~1"=="--test" (
    set "SPECIFIC_TEST=-k %~2"
    shift
)
if /I "%~1"=="--help" goto :show_help
shift
goto :parse_args

:show_help
echo Dashboard E2E Test Runner
echo.
echo Usage: %~nx0 [options]
echo.
echo Options:
echo   -v, --verbose       Verbose output
echo   -h, --headed        Run with visible browser
echo   -b, --browser TYPE  Browser type (chromium, firefox, webkit)
echo   -t, --test NAME     Run specific test
echo   --help              Show this help message
echo.
echo Examples:
echo   %~nx0                                    # Run all tests
echo   %~nx0 -v                                 # Run with verbose output
echo   %~nx0 -h                                 # Run with visible browser
echo   %~nx0 -b firefox                         # Run with Firefox
echo   %~nx0 -t test_ga4_dashboard_loads        # Run specific test
echo.
exit /b 0

:check_env
REM Check if environment variables are overridden
if defined GRAFANA_URL_OVERRIDE set "GRAFANA_URL=%GRAFANA_URL_OVERRIDE%"
if defined GRAFANA_USER_OVERRIDE set "GRAFANA_USER=%GRAFANA_USER_OVERRIDE%"
if defined GRAFANA_PASSWORD_OVERRIDE set "GRAFANA_PASSWORD=%GRAFANA_PASSWORD_OVERRIDE%"

echo ========================================
echo Dashboard E2E Test Suite
echo ========================================
echo.

REM Check prerequisites
echo Checking prerequisites...

REM Check if playwright is installed
python -c "import playwright" 2>nul
if errorlevel 1 (
    echo [ERROR] Playwright not installed
    echo Installing Playwright...
    pip install playwright
    playwright install %BROWSER_TYPE%
)

REM Check if Grafana is running
echo Checking Grafana connection...
curl -f -s "%GRAFANA_URL%/api/health" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Cannot connect to Grafana at %GRAFANA_URL%
    echo Please ensure Grafana is running:
    echo   docker-compose up -d grafana
    exit /b 1
)
echo [OK] Grafana is running

REM Check if browser is installed
echo Checking browser installation...
playwright install %BROWSER_TYPE% --dry-run >nul 2>&1
if errorlevel 1 (
    echo Installing %BROWSER_TYPE% browser...
    playwright install %BROWSER_TYPE%
)
echo [OK] Browser %BROWSER_TYPE% is installed

echo.
echo Test Configuration:
echo   Grafana URL: %GRAFANA_URL%
echo   Browser: %BROWSER_TYPE%
echo   Headless: %HEADLESS%
if defined SPECIFIC_TEST echo   Specific Test: %SPECIFIC_TEST%
echo.

REM Construct pytest command
set "PYTEST_CMD=pytest tests\e2e\test_dashboard_e2e.py"

if defined VERBOSE (
    set "PYTEST_CMD=%PYTEST_CMD% %VERBOSE%"
) else (
    set "PYTEST_CMD=%PYTEST_CMD% -v"
)

REM Add markers
set "PYTEST_CMD=%PYTEST_CMD% -m 'e2e and ui'"

REM Add specific test if provided
if defined SPECIFIC_TEST set "PYTEST_CMD=%PYTEST_CMD% %SPECIFIC_TEST%"

REM Add color output
set "PYTEST_CMD=%PYTEST_CMD% --color=yes"

REM Run tests
echo Running tests...
echo Command: %PYTEST_CMD%
echo.

REM Set environment variables for pytest
set "GRAFANA_URL=%GRAFANA_URL%"
set "GRAFANA_USER=%GRAFANA_USER%"
set "GRAFANA_PASSWORD=%GRAFANA_PASSWORD%"
set "HEADLESS=%HEADLESS%"
set "BROWSER_TYPE=%BROWSER_TYPE%"

call %PYTEST_CMD%
set "EXIT_CODE=%ERRORLEVEL%"

if %EXIT_CODE%==0 (
    echo.
    echo ========================================
    echo [SUCCESS] All tests passed!
    echo ========================================
    exit /b 0
) else (
    echo.
    echo ========================================
    echo [FAILED] Some tests failed
    echo ========================================
    echo.
    echo Check test output above for details
    echo Screenshots saved to: test-results\screenshots\
    exit /b %EXIT_CODE%
)

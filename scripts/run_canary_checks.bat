@echo off
REM Wrapper script for running canary checks on Windows

setlocal enabledelayedexpansion

REM Default values
set ENVIRONMENT=production
set VERBOSE=false
set OUTPUT_DIR=reports

REM Parse arguments
:parse_args
if "%~1"=="" goto end_parse
if /i "%~1"=="-e" set ENVIRONMENT=%~2& shift & shift & goto parse_args
if /i "%~1"=="--environment" set ENVIRONMENT=%~2& shift & shift & goto parse_args
if /i "%~1"=="-v" set VERBOSE=true& shift & goto parse_args
if /i "%~1"=="--verbose" set VERBOSE=true& shift & goto parse_args
if /i "%~1"=="-o" set OUTPUT_DIR=%~2& shift & shift & goto parse_args
if /i "%~1"=="--output" set OUTPUT_DIR=%~2& shift & shift & goto parse_args
if /i "%~1"=="-h" goto show_help
if /i "%~1"=="--help" goto show_help
echo Unknown option: %~1
goto show_help

:end_parse

REM Validate environment
if /i not "%ENVIRONMENT%"=="staging" if /i not "%ENVIRONMENT%"=="production" (
    echo ERROR: Invalid environment '%ENVIRONMENT%'. Use 'staging' or 'production'
    exit /b 2
)

REM Create output directory
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

REM Generate timestamp
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set TIMESTAMP=%dt:~0,8%_%dt:~8,6%

REM Set output file
set OUTPUT_FILE=%OUTPUT_DIR%\canary-report-%ENVIRONMENT%-%TIMESTAMP%.json

REM Print header
echo ========================================
echo   Canary Checks - Site Data Warehouse
echo ========================================
echo Environment:    %ENVIRONMENT%
echo Verbose:        %VERBOSE%
echo Output:         %OUTPUT_FILE%
echo ========================================
echo.

REM Build command
set CMD=python scripts\canary_checks.py --environment %ENVIRONMENT% --output %OUTPUT_FILE%

if "%VERBOSE%"=="true" (
    set CMD=!CMD! --verbose
)

REM Run canary checks
echo Running canary checks...
call !CMD!
set EXIT_CODE=%ERRORLEVEL%

echo.
if %EXIT_CODE%==0 (
    echo ========================================
    echo   All checks passed!
    echo ========================================
) else (
    echo ========================================
    echo   Some checks failed!
    echo ========================================
)

REM Create latest report copy
copy /Y "%OUTPUT_FILE%" "%OUTPUT_DIR%\canary-report-%ENVIRONMENT%-latest.json" >nul 2>&1

echo.
echo Report saved to: %OUTPUT_FILE%
echo Latest report:   %OUTPUT_DIR%\canary-report-%ENVIRONMENT%-latest.json
echo.

exit /b %EXIT_CODE%

:show_help
echo Usage: run_canary_checks.bat [OPTIONS]
echo.
echo Run canary checks for Site Data Warehouse
echo.
echo Options:
echo     -e, --environment ENV    Environment to check (staging^|production) [default: production]
echo     -v, --verbose           Enable verbose logging
echo     -o, --output DIR        Output directory for reports [default: reports]
echo     -h, --help              Show this help message
echo.
echo Environment Variables:
echo     ENVIRONMENT             Environment name (staging^|production)
echo     WAREHOUSE_DSN           PostgreSQL connection string
echo     INSIGHTS_API_URL        Insights API URL
echo     SCHEDULER_METRICS_FILE  Path to scheduler metrics file
echo.
echo Examples:
echo     run_canary_checks.bat --environment production
echo     run_canary_checks.bat -e staging -v
echo.
exit /b 0

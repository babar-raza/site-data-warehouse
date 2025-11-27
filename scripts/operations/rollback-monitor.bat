@echo off
REM Rollback Automation Monitor - Windows Wrapper Script
REM Starts the rollback automation with proper error handling

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..\..
set LOG_DIR=%PROJECT_ROOT%\logs
set PID_FILE=%TEMP%\rollback_automation.pid

REM Parse command line arguments
set ACTION=%1
set MODE=%2

if "%ACTION%"=="" set ACTION=start

REM Create log directory
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

goto %ACTION% 2>nul
if errorlevel 1 goto usage

:start
    echo Starting rollback monitoring...

    REM Check if already running
    if exist "%PID_FILE%" (
        echo Rollback monitoring may already be running
        echo Check with: rollback-monitor.bat status
    )

    REM Build command
    set CMD=python "%PROJECT_ROOT%\scripts\rollback_automation.py"
    set CMD=%CMD% --log-file "%LOG_DIR%\rollback_automation.log"

    if "%MODE%"=="dry-run" (
        echo Running in DRY-RUN mode ^(no actual rollbacks^)
        set CMD=%CMD% --dry-run
    )

    REM Start in background (using start command)
    cd /d "%PROJECT_ROOT%"
    start "Rollback Automation" /MIN %CMD%

    echo.
    echo Rollback monitoring started
    echo.
    echo Logs:
    echo   Main: %LOG_DIR%\rollback_automation.log
    echo.
    echo Commands:
    echo   View logs: type "%LOG_DIR%\rollback_automation.log"
    echo   Stop: rollback-monitor.bat stop
    echo   Status: rollback-monitor.bat status

    goto end

:stop
    echo Stopping rollback monitoring...

    REM Kill Python processes running rollback_automation.py
    for /f "tokens=2" %%i in ('tasklist /fi "imagename eq python.exe" /fo list ^| find "PID:"') do (
        wmic process where "ProcessId=%%i" get CommandLine 2>nul | find "rollback_automation.py" >nul
        if not errorlevel 1 (
            echo Stopping process %%i
            taskkill /PID %%i /T /F >nul 2>&1
        )
    )

    REM Remove PID file
    if exist "%PID_FILE%" del "%PID_FILE%"

    echo Rollback monitoring stopped
    goto end

:status
    echo Checking rollback monitoring status...
    echo.

    REM Check for running processes
    set FOUND=0
    for /f "tokens=2" %%i in ('tasklist /fi "imagename eq python.exe" /fo list ^| find "PID:"') do (
        wmic process where "ProcessId=%%i" get CommandLine 2>nul | find "rollback_automation.py" >nul
        if not errorlevel 1 (
            echo Status: Running ^(PID: %%i^)
            set FOUND=1
        )
    )

    if !FOUND!==0 (
        echo Status: Not running
    )

    echo.
    if exist "%LOG_DIR%\rollback_automation.log" (
        echo Recent log entries:
        powershell -Command "Get-Content '%LOG_DIR%\rollback_automation.log' -Tail 10"
    )

    goto end

:restart
    call :stop
    timeout /t 2 /nobreak >nul
    call :start
    goto end

:test
    echo Running rollback automation tests...
    echo.

    cd /d "%PROJECT_ROOT%"
    python scripts\test_rollback_automation.py

    goto end

:usage
    echo Usage: %~nx0 {start^|stop^|status^|restart^|test} [dry-run]
    echo.
    echo Commands:
    echo   start      Start rollback monitoring
    echo   stop       Stop rollback monitoring
    echo   status     Show monitoring status
    echo   restart    Restart monitoring
    echo   test       Run test suite
    echo.
    echo Options:
    echo   dry-run    Run in dry-run mode ^(no actual rollbacks^)
    echo.
    echo Examples:
    echo   %~nx0 start          # Start monitoring
    echo   %~nx0 start dry-run  # Start in dry-run mode
    echo   %~nx0 test           # Run tests
    echo   %~nx0 status         # Check status

    goto end

:end
    endlocal
    exit /b 0

@echo off
REM =============================================
REM GSC WAREHOUSE - BUILD ALL IMAGES
REM =============================================
REM Enterprise-grade Docker image build script
REM Usage:
REM   build-images.bat [dev|prod] [--gpu] [--no-cache]
REM
REM Examples:
REM   build-images.bat dev              - CPU-only builds (smaller images)
REM   build-images.bat prod             - CPU-only production builds
REM   build-images.bat prod --gpu       - GPU-enabled builds (for NVIDIA systems)
REM   build-images.bat prod --no-cache  - Force rebuild without cache
REM   build-images.bat prod --gpu --no-cache
REM
REM GPU vs CPU PyTorch Selection:
REM   - Default (no --gpu): CPU-only PyTorch (~2.75GB insights_engine)
REM   - With --gpu: CUDA 12.4 PyTorch (~10GB insights_engine)
REM
REM Use --gpu only if you have NVIDIA GPU with CUDA drivers installed

setlocal enabledelayedexpansion

REM Enable BuildKit
set DOCKER_BUILDKIT=1
set COMPOSE_DOCKER_CLI_BUILD=1

REM Default values
set ENV_TYPE=%1
if "%ENV_TYPE%"=="" set ENV_TYPE=dev

set USE_GPU=false
set NO_CACHE_FLAG=
set GPU_BUILD_ARG=

REM Parse additional arguments
:parse_args
shift
if "%1"=="" goto end_parse
if "%1"=="--gpu" (
    set USE_GPU=true
    set GPU_BUILD_ARG=--build-arg USE_GPU=true
    goto parse_args
)
if "%1"=="--no-cache" (
    set NO_CACHE_FLAG=--no-cache
    goto parse_args
)
echo Unknown option: %1
exit /b 1
:end_parse

REM Colors (Windows 10+)
set "GREEN=[92m"
set "YELLOW=[93m"
set "RED=[91m"
set "BLUE=[94m"
set "NC=[0m"

echo.
echo %BLUE%============================================%NC%
echo %BLUE% GSC WAREHOUSE - DOCKER BUILD SCRIPT%NC%
echo %BLUE%============================================%NC%
echo.
echo Environment: %YELLOW%%ENV_TYPE%%NC%
echo BuildKit: %GREEN%Enabled%NC%
if "%USE_GPU%"=="true" (
    echo PyTorch: %YELLOW%GPU (CUDA 12.4)%NC%
) else (
    echo PyTorch: %GREEN%CPU-only (smaller images)%NC%
)
if defined NO_CACHE_FLAG echo Cache: %RED%Disabled%NC%
echo.

REM Check Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo %RED%ERROR: Docker is not running%NC%
    exit /b 1
)

REM Step 1: Build base image
echo.
echo %BLUE%[1/4] Building shared base image...%NC%
echo.

docker build ^
    --target base-runtime ^
    -t gsc-base:latest ^
    -f compose/dockerfiles/Dockerfile.base ^
    %NO_CACHE_FLAG% ^
    .

if errorlevel 1 (
    echo %RED%ERROR: Base image build failed%NC%
    exit /b 1
)

echo %GREEN%Base image build successful%NC%

REM Step 2: Build ML service images with GPU/CPU selection
echo.
echo %BLUE%[2/4] Building ML services (insights_engine, celery)...%NC%
echo.

if "%USE_GPU%"=="true" (
    echo Building with %YELLOW%GPU/CUDA support%NC%...
) else (
    echo Building with %GREEN%CPU-only PyTorch%NC%...
)

REM Build insights_engine
echo %BLUE%  Building insights_engine...%NC%
docker build ^
    --target runtime ^
    %GPU_BUILD_ARG% ^
    -t site-data-warehouse-insights_engine:latest ^
    -f compose/dockerfiles/Dockerfile.insights_engine ^
    %NO_CACHE_FLAG% ^
    .

if errorlevel 1 (
    echo %RED%ERROR: insights_engine build failed%NC%
    exit /b 1
)

REM Build celery worker
echo %BLUE%  Building celery worker...%NC%
docker build ^
    --target runtime ^
    %GPU_BUILD_ARG% ^
    -t site-data-warehouse-celery:latest ^
    -f compose/dockerfiles/Dockerfile.celery ^
    %NO_CACHE_FLAG% ^
    .

if errorlevel 1 (
    echo %RED%ERROR: celery build failed%NC%
    exit /b 1
)

echo %GREEN%ML services build successful%NC%

REM Step 3: Build remaining service images
echo.
echo %BLUE%[3/4] Building remaining services in parallel...%NC%
echo.

if "%ENV_TYPE%"=="prod" (
    docker compose -f docker-compose.yml -f docker-compose.prod.yml build --parallel %NO_CACHE_FLAG%
) else (
    docker compose -f docker-compose.yml -f docker-compose.dev.yml build --parallel %NO_CACHE_FLAG%
)

if errorlevel 1 (
    echo %RED%ERROR: Service builds failed%NC%
    exit /b 1
)

echo %GREEN%Service images build successful%NC%

REM Step 4: Show summary
echo.
echo %BLUE%[4/4] Build Summary%NC%
echo.

echo %BLUE%Base Image:%NC%
docker images gsc-base --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

echo.
echo %BLUE%ML Services (insights_engine, celery):%NC%
docker images site-data-warehouse-insights_engine --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
docker images site-data-warehouse-celery --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" 2>nul

echo.
echo %BLUE%============================================%NC%
echo %GREEN% BUILD COMPLETED SUCCESSFULLY%NC%
echo %BLUE%============================================%NC%
echo.
if "%USE_GPU%"=="true" (
    echo %YELLOW%GPU Mode:%NC% Images include CUDA 12.4 support
    echo   To run with GPU: docker run --gpus all ^<image^>
) else (
    echo %GREEN%CPU Mode:%NC% Smaller images without GPU dependencies
)
echo.
echo Next steps:
if "%ENV_TYPE%"=="dev" (
    echo   1. Start services: docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile core up
    echo   2. View logs: docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f
) else (
    echo   1. Start services: docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile core up -d
    echo   2. View logs: docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f
)
echo   3. Stop services: docker compose down
echo.
echo To rebuild with GPU support: build-images.bat %ENV_TYPE% --gpu
echo.

endlocal

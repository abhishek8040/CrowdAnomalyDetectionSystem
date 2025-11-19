@echo off

echo Starting Crowd Anomaly Detection System...

REM Check if Docker is installed
where docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Docker is not installed. Please install Docker first.
    exit /b 1
)

REM Copy environment files if they don't exist
if not exist .env (
    echo Creating .env file from example...
    copy .env.example .env
)

if not exist frontend\.env (
    echo Creating frontend\.env file from example...
    copy frontend\.env.example frontend\.env
)

REM Build and start containers
echo Building Docker containers...
docker-compose build

echo Starting services...
docker-compose up -d

REM Wait for services to be ready
echo Waiting for services to be ready...
timeout /t 10 /nobreak

echo.
echo System is ready!
echo Access Dashboard: http://localhost:3000
echo Access API: http://localhost:8000
echo.
echo To view logs: docker-compose logs -f
echo To stop: docker-compose down

pause

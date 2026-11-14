@echo off
REM InfraPulse startup script (Windows). Double-click or run: start.bat
setlocal

cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 (
  echo ERROR: Docker is not installed or not on PATH. See MANUAL.md ^(Prerequisites^).
  exit /b 1
)

docker compose version >nul 2>nul
if errorlevel 1 (
  echo ERROR: Docker Compose v2 is not available. See MANUAL.md ^(Prerequisites^).
  exit /b 1
)

echo Starting InfraPulse (this may take a few minutes on first run)...
echo App: http://localhost:8092   API: http://localhost:8003/api/docs
docker compose up --build
set STATUS=%ERRORLEVEL%
if not %STATUS%==0 (
  echo ERROR: InfraPulse failed to start ^(exit %STATUS%^). See MANUAL.md ^(Troubleshooting^).
)
exit /b %STATUS%

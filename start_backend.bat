@echo off
title EV Battery AI - Backend Launcher
color 0A
echo ==========================================
echo   EV Battery AI - Backend Startup
echo ==========================================
echo.

:: Kill any stale Flask on port 5000
echo [1/2] Stopping any existing processes on port 5000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5000" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 >nul

:: Start Flask backend in a new window
echo [2/2] Starting Flask AI Server...
start "Flask AI Server" cmd /k "cd /d "%~dp0" && python backend\server.py"
timeout /t 4 >nul

:: Start Tunnel Watchdog (auto-reconnects if tunnel dies)
echo [3/3] Starting Self-Healing HTTPS Tunnel...
start "HTTPS Tunnel (Auto-Reconnect)" cmd /k "cd /d "%~dp0" && tunnel_watchdog.bat"

echo.
echo ==========================================
echo   READY! Your backend is live at:
echo   https://ev-battery-ai.loca.lt
echo ==========================================
echo.
echo - The tunnel auto-reconnects if it drops.
echo - Keep both CMD windows open.
echo - Paste URL in dashboard SERVER field.
echo.
pause

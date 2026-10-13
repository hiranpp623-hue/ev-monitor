@echo off
title EV Battery AI - Backend Launcher
color 0A
echo ==========================================
echo   EV Battery AI - Backend Startup
echo ==========================================
echo.

:: Kill any stale Flask on port 5000
echo [1/3] Stopping any existing processes on port 5000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5000" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 >nul

:: Start Flask backend in a new window
echo [2/3] Starting Flask AI Server...
start "Flask AI Server" cmd /k "cd /d "%~dp0" && python backend\server.py"
timeout /t 3 >nul

:: Start Cloudflare Tunnel (stable, auto-reconnects)
echo [3/3] Starting Cloudflare HTTPS Tunnel...
echo       (Wait for a trycloudflare.com URL to appear in the next window)
start "Cloudflare Tunnel" cmd /k "cd /d "%~dp0" && cloudflared.exe tunnel --url http://localhost:5000"

echo.
echo ==========================================
echo   READY! 
echo   - Look in the "Cloudflare Tunnel" window
echo   - Copy the https://xxxx.trycloudflare.com URL
echo   - Paste it into the SERVER field on your dashboard
echo   - Click START ENGINE!
echo ==========================================
echo.
pause

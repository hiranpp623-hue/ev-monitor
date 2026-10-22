@echo off
title EV Battery AI - Tunnel Watchdog
color 0B

:restart
echo.
echo [%TIME%] Starting HTTPS tunnel (ev-battery-ai.loca.lt)...
cmd /c "npx -y localtunnel --port 5000 --subdomain ev-battery-ai 2>&1"
echo.
echo [%TIME%] Tunnel died. Restarting in 3 seconds...
timeout /t 3 /nobreak >nul
goto restart

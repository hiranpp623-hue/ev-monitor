@echo off
title EV Battery AI Monitor - Backend API Server
echo ===================================================================
echo   EV Battery AI Monitor - Starting Flask Backend Server (Port 5000)
echo ===================================================================
cd /d "%~dp0backend"
python server.py
pause

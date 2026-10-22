@echo off
title EV Battery AI Monitor - Virtual Hardware Node
echo ===================================================================
echo   EV Battery AI Monitor - Virtual Hardware Node (Dataset Streaming)
echo ===================================================================
cd /d "%~dp0"
set TARGET_URL=https://ev-monitor-backend.onrender.com
if not "%~1"=="" set TARGET_URL=%~1
echo Target Backend: %TARGET_URL%
python virtual_hardware.py --mode dataset --interval 0.5 --url %TARGET_URL%
pause

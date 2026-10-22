@echo off
title EV Battery AI Monitor - Virtual Hardware Node
echo ===================================================================
echo   EV Battery AI Monitor - Virtual Hardware Node (Dataset Streaming)
echo ===================================================================
cd /d "%~dp0"
python virtual_hardware.py --mode dataset --interval 0.5 --url http://127.0.0.1:5000
pause

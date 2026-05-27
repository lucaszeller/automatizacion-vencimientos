@echo off
cd /d "%~dp0"
python main.py --ui
if errorlevel 1 pause

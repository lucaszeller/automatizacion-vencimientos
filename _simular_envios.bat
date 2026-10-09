@echo off
chcp 65001 > nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python _simular_envios.py > _simular_output.txt 2>&1
echo.
echo Resultado guardado en _simular_output.txt
type _simular_output.txt
pause

@echo off
cd /d "%~dp0"

set "EXE_PATH=dist\Alertas Services UI\Alertas Services UI.exe"

if not exist "%EXE_PATH%" (
    echo No se encontro el EXE. Ejecuta "Crear EXE.bat" primero.
    pause
    exit /b 1
)

if exist ".env" copy /Y ".env" "dist\Alertas Services UI\.env" >nul

start "" "%EXE_PATH%"

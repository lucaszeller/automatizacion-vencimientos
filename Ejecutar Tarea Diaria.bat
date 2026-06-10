@echo off
cd /d "%~dp0"

set "EXE_PATH=dist\Alertas Services Tarea\Alertas Services Tarea.exe"
set "NEED_BUILD=0"

for /f %%I in ('powershell -NoProfile -Command "$exe='dist/Alertas Services Tarea/Alertas Services Tarea.exe'; if(-not (Test-Path $exe)){1; exit}; $exeTime=(Get-Item $exe).LastWriteTimeUtc; $src=(Get-ChildItem -Recurse -File app,sql,main.py,ui_launcher.py,daily_launcher.py,requirements.txt,'Crear EXE.bat' | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1); if($src.LastWriteTimeUtc -gt $exeTime){1}else{0}"') do set "NEED_BUILD=%%I"

if "%NEED_BUILD%"=="1" (
    call "Crear EXE.bat" --no-pause
    if errorlevel 1 exit /b 1
)

if exist ".env" copy /Y ".env" "dist\Alertas Services Tarea\.env" >nul

if exist "%EXE_PATH%" (
    "%EXE_PATH%"
    exit /b %errorlevel%
)

exit /b 1

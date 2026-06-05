@echo off
cd /d "%~dp0"

set "EXE_PATH=dist\Alertas Services UI\Alertas Services UI.exe"
set "NEED_BUILD=0"

for /f %%I in ('powershell -NoProfile -Command "$exe='dist/Alertas Services UI/Alertas Services UI.exe'; if(-not (Test-Path $exe)){1; exit}; $exeTime=(Get-Item $exe).LastWriteTimeUtc; $src=(Get-ChildItem -Recurse -File app,sql,main.py,ui_launcher.py,daily_launcher.py,requirements.txt,'Crear EXE.bat' | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1); if($src.LastWriteTimeUtc -gt $exeTime){1}else{0}"') do set "NEED_BUILD=%%I"

if "%NEED_BUILD%"=="1" (
    echo Compilando EXE automaticamente...
    call "Crear EXE.bat" --no-pause
    if errorlevel 1 (
        echo.
        echo Error al compilar el EXE.
        pause
        exit /b 1
    )
)

if exist ".env" copy /Y ".env" "dist\Alertas Services UI\.env" >nul

if exist "%EXE_PATH%" (
    start "" "%EXE_PATH%"
    exit /b 0
)

echo No se encontro el EXE en: %EXE_PATH%
pause
exit /b 1

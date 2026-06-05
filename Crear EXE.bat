@echo off
cd /d "%~dp0"
setlocal

set "DIST_TEMP=dist_build"
set "BUILD_TEMP=build_temp"

python -m pip install --upgrade pyinstaller
if errorlevel 1 goto :fail

if exist "%DIST_TEMP%" rmdir /S /Q "%DIST_TEMP%"
if exist "%BUILD_TEMP%" rmdir /S /Q "%BUILD_TEMP%"

pyinstaller ^
  --noconfirm ^
  --clean ^
  --onedir ^
  --windowed ^
  --name "Alertas Services UI" ^
  --add-data "sql;sql" ^
  --distpath "%DIST_TEMP%" ^
  --workpath "%BUILD_TEMP%" ^
  ui_launcher.py

if errorlevel 1 goto :fail

pyinstaller ^
  --noconfirm ^
  --clean ^
  --onedir ^
  --windowed ^
  --name "Alertas Services Tarea" ^
  --add-data "sql;sql" ^
  --distpath "%DIST_TEMP%" ^
  --workpath "%BUILD_TEMP%" ^
  daily_launcher.py

if errorlevel 1 goto :fail

robocopy "%DIST_TEMP%\Alertas Services UI" "dist\Alertas Services UI" /MIR /XD data /XF "*.xlsx" "*.db" "*.txt" >nul
if errorlevel 8 goto :fail

robocopy "%DIST_TEMP%\Alertas Services Tarea" "dist\Alertas Services Tarea" /MIR /XD data /XF "*.xlsx" "*.db" "*.txt" >nul
if errorlevel 8 goto :fail

if exist ".env" (
  copy /Y ".env" "dist\\Alertas Services UI\\.env" >nul
  copy /Y ".env" "dist\\Alertas Services Tarea\\.env" >nul
)

echo.
echo EXE generado en:
echo %CD%\dist\Alertas Services UI\Alertas Services UI.exe
echo %CD%\dist\Alertas Services Tarea\Alertas Services Tarea.exe
echo.
echo Si no existe .env en esta carpeta, recuerde copiarlo junto al EXE.
if /I "%~1"=="--no-pause" exit /b 0
pause
exit /b 0

:fail
if /I "%~1"=="--no-pause" exit /b 1
pause
exit /b 1

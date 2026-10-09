@echo off
pushd "%~dp0"
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
  --hidden-import gspread ^
  --hidden-import google.oauth2.service_account ^
  --hidden-import google.auth.transport.requests ^
  --hidden-import reportlab.graphics.barcode.code128 ^
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
  --hidden-import gspread ^
  --hidden-import google.oauth2.service_account ^
  --hidden-import google.auth.transport.requests ^
  --hidden-import reportlab.graphics.barcode.code128 ^
  --distpath "%DIST_TEMP%" ^
  --workpath "%BUILD_TEMP%" ^
  daily_launcher.py

if errorlevel 1 goto :fail

rem /XD excluye carpetas que NO vienen del build y no hay que borrar
robocopy "%DIST_TEMP%\Alertas Services UI" "dist\Alertas Services UI" /MIR /XD data credenciales /XF "*.xlsx" "*.db" "*.txt" >nul
if errorlevel 8 goto :fail

robocopy "%DIST_TEMP%\Alertas Services Tarea" "dist\Alertas Services Tarea" /MIR /XD data credenciales /XF "*.xlsx" "*.db" "*.txt" >nul
if errorlevel 8 goto :fail

if exist ".env" (
  copy /Y ".env" "dist\Alertas Services UI\.env" >nul
  copy /Y ".env" "dist\Alertas Services Tarea\.env" >nul
)

rem Credenciales de Google (hojas de ruta / calendar)
if exist "credenciales\*.json" (
  if not exist "dist\Alertas Services UI\credenciales" mkdir "dist\Alertas Services UI\credenciales"
  if not exist "dist\Alertas Services Tarea\credenciales" mkdir "dist\Alertas Services Tarea\credenciales"
  copy /Y "credenciales\*.json" "dist\Alertas Services UI\credenciales\" >nul
  copy /Y "credenciales\*.json" "dist\Alertas Services Tarea\credenciales\" >nul
)

rem Limpiar las carpetas temporales del build.
rem dist_build NO tiene .env ni credenciales: si alguien abre el EXE desde ahi,
rem la app no encuentra la configuracion y trata de conectarse a localhost.
if exist "%DIST_TEMP%" rmdir /S /Q "%DIST_TEMP%"
if exist "%BUILD_TEMP%" rmdir /S /Q "%BUILD_TEMP%"

echo.
echo ============================================================
echo  EXE generado. Abrir SOLO desde estas rutas:
echo ============================================================
echo.
echo   %CD%\dist\Alertas Services UI\Alertas Services UI.exe
echo   %CD%\dist\Alertas Services Tarea\Alertas Services Tarea.exe
echo.
echo  Las carpetas temporales del build ya fueron eliminadas.
echo  El .env y las credenciales se copiaron junto a cada EXE.
popd
if /I "%~1"=="--no-pause" exit /b 0
pause
exit /b 0

:fail
popd
if /I "%~1"=="--no-pause" exit /b 1
pause
exit /b 1

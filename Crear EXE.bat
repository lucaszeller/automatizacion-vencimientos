@echo off
cd /d "%~dp0"

python -m pip install --upgrade pyinstaller
if errorlevel 1 pause & exit /b 1

pyinstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name "Alertas Services" ^
  --add-data "sql;sql" ^
  main.py

if errorlevel 1 pause & exit /b 1

echo.
echo EXE generado en:
echo %CD%\dist\Alertas Services.exe
echo.
echo Copie el archivo .env junto al EXE antes de usarlo en otra PC.
pause

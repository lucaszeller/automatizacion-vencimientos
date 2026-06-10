@echo off
cd /d "%~dp0"
setlocal

set "TASK_NAME=WhatsApp Server Alertas"
set "BAT_PATH=%~dp0Iniciar WhatsApp Server.bat"

echo Registrando inicio automatico del servidor WhatsApp...
echo.

schtasks /Create ^
  /TN "%TASK_NAME%" ^
  /TR "cmd /c \"%BAT_PATH%\"" ^
  /SC ONLOGON ^
  /RL HIGHEST ^
  /F

if errorlevel 1 (
    echo.
    echo ERROR: No se pudo crear la tarea. Intente ejecutar como Administrador.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Tarea creada correctamente.
echo ============================================================
echo.
echo  El servidor WhatsApp arrancara automaticamente
echo  cada vez que inicie sesion en Windows.
echo.
echo  Para eliminarlo: Eliminar Tarea Inicio WhatsApp.bat
echo.
pause
exit /b 0

@echo off
setlocal

set "TASK_NAME=WhatsApp Server Alertas"

schtasks /Delete /TN "%TASK_NAME%" /F

if errorlevel 1 (
    echo.
    echo ERROR: No se pudo eliminar la tarea.
    pause
    exit /b 1
)

echo.
echo Tarea "%TASK_NAME%" eliminada correctamente.
pause
exit /b 0

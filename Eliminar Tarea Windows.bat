@echo off
setlocal

set "TASK_NAME=Alertas Services Diario"

schtasks /Delete /TN "%TASK_NAME%" /F

if errorlevel 1 (
    echo.
    echo ERROR: No se pudo eliminar la tarea. Puede que no exista o requiera permisos.
    pause
    exit /b 1
)

echo.
echo Tarea "%TASK_NAME%" eliminada correctamente.
pause
exit /b 0

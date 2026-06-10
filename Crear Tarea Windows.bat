@echo off
cd /d "%~dp0"
setlocal

set "TASK_NAME=Alertas Services Diario"
set "BAT_PATH=%~dp0Ejecutar Tarea Diaria.bat"

echo Registrando tarea en el Programador de Windows...
echo.

schtasks /Create ^
  /TN "%TASK_NAME%" ^
  /TR "cmd /c \"%BAT_PATH%\"" ^
  /SC WEEKLY ^
  /D MON,TUE,WED,THU,FRI ^
  /ST 08:00 ^
  /RL HIGHEST ^
  /F

if errorlevel 1 (
    echo.
    echo ERROR: No se pudo crear la tarea.
    echo Intente ejecutar este archivo como Administrador:
    echo   clic derecho ^> Ejecutar como administrador
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Tarea programada creada correctamente.
echo ============================================================
echo.
echo  Nombre  : %TASK_NAME%
echo  Horario : Lunes a Viernes a las 08:00 AM
echo  Script  : %BAT_PATH%
echo.
echo  Para ver o modificar la tarea:
echo    Inicio ^> Programador de tareas (taskschd.msc)
echo.
echo  Para eliminar la tarea en el futuro, ejecutar:
echo    Eliminar Tarea Windows.bat
echo.
pause
exit /b 0

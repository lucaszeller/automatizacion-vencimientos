@echo off
cd /d "%~dp0whatsapp-server"
setlocal

echo ============================================
echo   Servidor WhatsApp Local - Alertas Services
echo ============================================
echo.

:: Verificar que Node.js este instalado
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js no esta instalado o no esta en el PATH.
    echo Descargue Node.js desde https://nodejs.org
    pause
    exit /b 1
)

:: Instalar dependencias si no existen
if not exist "node_modules" (
    echo Instalando dependencias npm por primera vez...
    echo Esto puede tardar 1-2 minutos.
    echo.
    npm install
    if errorlevel 1 (
        echo ERROR: Fallo la instalacion de dependencias.
        pause
        exit /b 1
    )
    echo.
)

echo Iniciando servidor...
echo Cuando aparezca el QR, escaneelo con WhatsApp ^> Dispositivos vinculados.
echo La sesion se guarda automaticamente. El QR solo se pide la primera vez.
echo.
echo Para detener el servidor: Ctrl+C
echo.

:loop
node server.js
echo.
echo El servidor se detuvo. Reiniciando en 3 segundos... (Ctrl+C para salir)
timeout /t 3 /nobreak >nul
goto loop

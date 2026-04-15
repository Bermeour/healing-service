@echo off
title Self-Healing Demo
cd /d "%~dp0.."

echo ============================================
echo   Self-Healing - Pagina Demo
echo   http://localhost:9000
echo ============================================
echo.
echo Abriendo navegador...

:: Abre el navegador
start "" "http://localhost:9000"

:: Sirve los archivos estáticos con Python
echo [INFO] Servidor en http://localhost:9000
echo [INFO] Presiona Ctrl+C para detener
echo.

if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -m http.server 9000 --directory demo
) else (
    python -m http.server 9000 --directory demo
)

pause

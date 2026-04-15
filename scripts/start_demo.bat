@echo off
title Self-Healing Demo

:: Raiz del proyecto (un nivel arriba de scripts/)
set ROOT=%~dp0..
set DEMO_DIR=%ROOT%\demo

echo ============================================
echo   Self-Healing - Pagina Demo
echo   http://localhost:9000
echo ============================================
echo.
echo [INFO] Raiz del proyecto : %ROOT%
echo [INFO] Directorio demo   : %DEMO_DIR%
echo.

:: Verificar que la carpeta demo existe
if not exist "%DEMO_DIR%\index.html" (
    echo [ERROR] No se encontro demo\index.html en %DEMO_DIR%
    pause
    exit /b 1
)

:: 1) Elegir Python
if exist "%ROOT%\.venv\Scripts\python.exe" (
    set PYTHON="%ROOT%\.venv\Scripts\python.exe"
) else (
    set PYTHON=python
)
echo [INFO] Usando Python: %PYTHON%

:: 2) Arrancar servidor en ventana separada con cmd /k para ver errores
echo [INFO] Iniciando servidor...
start "Demo Server" cmd /k %PYTHON% -m http.server 9000 --directory "%DEMO_DIR%"

:: 3) Esperar a que el servidor este listo
timeout /t 2 /nobreak >nul

:: 4) Abrir navegador
echo [INFO] Abriendo navegador en http://localhost:9000 ...
start "" "http://localhost:9000"

echo.
echo [INFO] Servidor activo en http://localhost:9000
echo [INFO] Cierra la ventana "Demo Server" para detenerlo.
echo.
pause

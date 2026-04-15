@echo off
title Self-Healing Service [DEV]
cd /d "%~dp0.."

echo ============================================
echo   Self-Healing Service - Modo DESARROLLO
echo ============================================
echo.

:: Activa el entorno virtual
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [ERROR] No se encontro el entorno virtual .venv
    echo Ejecuta: python -m venv .venv
    echo         .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

:: Crea el .env si no existe
if not exist ".env" (
    echo [INFO] Creando .env desde .env.example...
    copy ".env.example" ".env" >nul
)

:: Libera el puerto 8765 si ya está ocupado
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8765 "') do (
    echo [INFO] Puerto 8765 ocupado por PID %%a, liberando...
    taskkill /PID %%a /F >nul 2>&1
)

echo [INFO] Levantando servicio en http://localhost:8765
echo [INFO] Swagger UI: http://localhost:8765/docs
echo [INFO] Presiona Ctrl+C para detener
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8765 --reload --log-level info

pause

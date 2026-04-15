@echo off
title Self-Healing Service [PROD]
cd /d "%~dp0.."

echo ============================================
echo   Self-Healing Service - Modo PRODUCCION
echo ============================================
echo.

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [ERROR] No se encontro el entorno virtual .venv
    pause
    exit /b 1
)

if not exist ".env" (
    echo [ERROR] Falta el archivo .env
    echo Copia .env.example como .env y configura los valores
    pause
    exit /b 1
)

:: Lee el puerto del .env (default 8765)
set PORT=8765
for /f "tokens=2 delims==" %%a in ('findstr /i "^PORT=" .env') do set PORT=%%a

:: Calcula workers = nucleos * 2 + 1 (minimo 2)
for /f %%a in ('wmic cpu get NumberOfLogicalProcessors /value ^| findstr "="') do set CPUS=%%a
set CPUS=%CPUS:NumberOfLogicalProcessors=%
if "%CPUS%"=="" set CPUS=2
set /a WORKERS=%CPUS% * 2 + 1

echo [INFO] Workers: %WORKERS%
echo [INFO] Puerto:  %PORT%
echo [INFO] Presiona Ctrl+C para detener
echo.

python -m uvicorn main:app --host 0.0.0.0 --port %PORT% --workers %WORKERS% --log-level info --no-access-log

pause

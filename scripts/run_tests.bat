@echo off
title Self-Healing Service - Tests
cd /d "%~dp0.."

echo ============================================
echo   Self-Healing Service - Tests
echo ============================================
echo.

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [ERROR] No se encontro el entorno virtual .venv
    pause
    exit /b 1
)

:: Modo: todos | unit | integration
set MODE=%1
if "%MODE%"=="" set MODE=all

if "%MODE%"=="unit" (
    echo [INFO] Corriendo tests unitarios...
    python -m pytest tests/unit/ -v --tb=short
) else if "%MODE%"=="integration" (
    echo [INFO] Corriendo tests de integracion...
    python -m pytest tests/integration/ -v --tb=short
) else (
    echo [INFO] Corriendo todos los tests...
    python -m pytest tests/ -v --tb=short
)

echo.
echo Uso: run_tests.bat [unit^|integration^|all]
pause

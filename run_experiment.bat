@echo off
title E-Miu Advanced EV Station Monitoring System
setlocal
cd /d "%~dp0"

echo ========================================================
echo Starting E-Miu Advanced EV Station Monitoring System...
echo ========================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_experiment.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================================
    echo Application exited with error code %ERRORLEVEL%.
    echo ========================================================
    pause
)

@echo off
setlocal
cd /d "%~dp0"
title Wartales CAT Studio - Modo Desktop

where powershell >nul 2>nul
if %errorlevel% equ 0 (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Iniciar_Estudio_CAT.ps1"
    exit /b %errorlevel%
)

echo [ERRO] PowerShell nao foi localizado no sistema.
pause
exit /b 1

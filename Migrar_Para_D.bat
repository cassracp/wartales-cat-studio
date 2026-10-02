@echo off
chcp 65001 > nul
title Migração do Wartales CAT Studio para D:\Projetos

echo ========================================================================
echo        ⚔️ WARTALES CAT STUDIO - MIGRAÇÃO PARA D:\PROJETOS ⚔️
echo ========================================================================
echo.
echo Este script copia todos os arquivos do projeto para o caminho definitivo:
echo   Destino: D:\Projetos\wartales-cat-studio
echo.

set "DESTINO=D:\Projetos\wartales-cat-studio"
set "ORIGEM=%~dp0"
set "ORIGEM=%ORIGEM:~0,-1%"

if /i "%ORIGEM%"=="%DESTINO%" (
    echo [INFO] O projeto Wartales CAT Studio já está localizado no destino definitivo:
    echo        %DESTINO%
    echo Nenhuma ação é necessária. Você pode executar 'Iniciar_Estudio_CAT.bat'.
    echo.
    pause
    exit /b 0
)

if not exist "D:\Projetos" (
    echo Criando pasta D:\Projetos...
    mkdir "D:\Projetos" 2>nul
)

echo Copiando arquivos via Robocopy...
robocopy "%ORIGEM%" "%DESTINO%" /E /XD .git __pycache__ .venv .idea .vscode /R:1 /W:1

echo.
echo ========================================================================
echo  Migração concluída com sucesso!
echo  Novo local: %DESTINO%
echo ========================================================================
echo.
pause

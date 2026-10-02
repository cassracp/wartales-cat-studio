# Wartales CAT Studio - Migrador PowerShell para D:\Projetos
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$origem = $PSScriptRoot
$destino = "D:\Projetos\wartales-cat-studio"

if ($origem.TrimEnd('\') -eq $destino.TrimEnd('\')) {
    Write-Host "[INFO] O projeto já está localizado no destino definitivo: $destino" -ForegroundColor Green
    Write-Host "Nenhuma ação é necessária. Execute 'Iniciar_Estudio_CAT.ps1' para abrir o Studio." -ForegroundColor Cyan
    Read-Host "Pressione Enter para sair..."
    exit 0
}

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "       ⚔️ WARTALES CAT STUDIO - MIGRAÇÃO PARA D:\PROJETOS ⚔️" -ForegroundColor Yellow
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Origem:  $origem" -ForegroundColor Gray
Write-Host "Destino: $destino" -ForegroundColor Green
Write-Host ""

if (-not (Test-Path "D:\Projetos")) {
    New-Item -ItemType Directory -Path "D:\Projetos" -Force | Out-Null
}

Write-Host "Transferindo arquivos com Robocopy..." -ForegroundColor Cyan
robocopy "$origem" "$destino" /E /XD .git __pycache__ .venv .idea .vscode /R:1 /W:1 | Out-Null

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host " Projeto migrado com sucesso para: $destino" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Pressione Enter para concluir..."

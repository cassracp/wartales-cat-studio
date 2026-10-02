# ==============================================================================
# Wartales CAT Studio - Inicializador PowerShell com Desmontagem & Montagem
# ==============================================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location $PSScriptRoot

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "              ⚔️ WARTALES CAT STUDIO - MODO DESKTOP ⚔️" -ForegroundColor Yellow
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Localizar executável do Python (python, py ou python3)
$executavelPython = $null
foreach ($nomeCmd in @("python", "py", "python3")) {
    $c = Get-Command $nomeCmd -ErrorAction SilentlyContinue
    if ($c) {
        $executavelPython = $c.Source
        break
    }
}

if (-not $executavelPython) {
    Write-Host "[ERRO] Python 3 não foi localizado no sistema." -ForegroundColor Red
    Write-Host "Por favor, instale o Python 3.10 ou superior para executar a aplicação." -ForegroundColor Yellow
    Read-Host "Pressione Enter para sair..."
    exit 1
}

# 2. Desmontar qualquer instância anterior na porta 5000 ou rodando servidor_api.py
Write-Host "[1/4] Desmontando instâncias anteriores do servidor..." -ForegroundColor DarkYellow

$conexoesPorta = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
if ($conexoesPorta) {
    $pidsOcupados = $conexoesPorta | Select-Object -ExpandProperty OwningProcess -Unique | Where-Object { $_ -gt 0 }
    foreach ($pidAlvo in $pidsOcupados) {
        Write-Host "      -> Encerrando processo na porta 5000 (PID: $pidAlvo)..." -ForegroundColor DarkGray
        Stop-Process -Id $pidAlvo -Force -ErrorAction SilentlyContinue
    }
}

Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*servidor_api.py*" } |
    ForEach-Object {
        Write-Host "      -> Encerrando processo python servidor_api.py (PID: $($_.ProcessId))..." -ForegroundColor DarkGray
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

Start-Sleep -Milliseconds 600

# 3. Montar / Iniciar o servidor HTTP atualizado
Write-Host "[2/4] Montando e iniciando servidor Python atualizado..." -ForegroundColor Green
$argumentos = if ($executavelPython -like "*\py.exe") { @("-3", "servidor\servidor_api.py") } else { @("servidor\servidor_api.py") }
$processoServidor = Start-Process -FilePath $executavelPython -ArgumentList $argumentos -PassThru -WindowStyle Hidden

# 4. Aguardar o servidor responder na porta 5000 com verificação ativa da API
Write-Host "[3/4] Aguardando disponibilidade da API HTTP (http://127.0.0.1:5000)..." -ForegroundColor Green
$tentativas = 0
$servidorPronto = $false
while ($tentativas -lt 20 -and -not $servidorPronto) {
    Start-Sleep -Milliseconds 350
    try {
        $resposta = Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/projetos" -TimeoutSec 1 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($resposta.StatusCode -eq 200) {
            $servidorPronto = $true
        }
    } catch {}
    $tentativas++
}

if (-not $servidorPronto) {
    Write-Host "[AVISO] Servidor ainda iniciando... prosseguindo com a abertura." -ForegroundColor Yellow
}

# 5. Abrir a interface em modo aplicativo nativo (Janela própria / Webview PWA)
Write-Host "[4/4] Abrindo interface no modo aplicativo nativo (Janela Própria)..." -ForegroundColor Green

$caminhosNavegadoresApp = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles}\Microsoft\Edge\Application\msedge.exe",
    "${env:LocalAppData}\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "${env:LocalAppData}\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles}\BraveSoftware\Brave-Browser\Application\brave.exe"
)

$executavelApp = $null
foreach ($caminho in $caminhosNavegadoresApp) {
    if (Test-Path $caminho) {
        $executavelApp = $caminho
        break
    }
}

if ($executavelApp) {
    Start-Process -FilePath $executavelApp -ArgumentList "--app=http://127.0.0.1:5000"
} else {
    Start-Process "http://127.0.0.1:5000"
}

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host " Wartales CAT Studio ativo com sucesso! (PID: $($processoServidor.Id))" -ForegroundColor Green
Write-Host " Pressione Ctrl+C para encerrar o estúdio." -ForegroundColor Yellow
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

try {
    Wait-Process -Id $processoServidor.Id
} finally {
    if (-not $processoServidor.HasExited) {
        Write-Host "Desmontando servidor ao encerrar..." -ForegroundColor DarkYellow
        Stop-Process -Id $processoServidor.Id -Force -ErrorAction SilentlyContinue
    }
}

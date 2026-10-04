$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$preferredPort = 8501

function Get-FreePort {
    param(
        [int]$StartPort
    )

    for ($port = $StartPort; $port -lt ($StartPort + 20); $port++) {
        $inUse = netstat -ano | Select-String ":$port\s"
        if (-not $inUse) {
            return $port
        }
    }

    throw "Could not find a free port starting from $StartPort."
}

if (-not (Test-Path $venvPython)) {
    python -m venv (Join-Path $root ".venv")
}

& $venvPython -m pip install -r (Join-Path $root "requirements.txt")
$port = Get-FreePort -StartPort $preferredPort

Write-Host ""
Write-Host "Starting E-Miu Advanced EV Station Monitoring System on port $port" -ForegroundColor Cyan
Write-Host "Laptop URL: http://localhost:$port" -ForegroundColor Green
Write-Host "Phone URL:  http://$(hostname):$port" -ForegroundColor Green
Write-Host ""

& $venvPython -m streamlit run (Join-Path $root "app.py") --server.address 0.0.0.0 --server.port $port

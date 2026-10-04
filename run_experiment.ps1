$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = if (Test-Path (Join-Path $root ".venv\Scripts\python.exe")) {
    Join-Path $root ".venv\Scripts\python.exe"
} elseif (Test-Path (Join-Path $root ".venv/bin/python")) {
    Join-Path $root ".venv/bin/python"
} else {
    if ($IsWindows -ne $false) {
        Join-Path $root ".venv\Scripts\python.exe"
    } else {
        Join-Path $root ".venv/bin/python"
    }
}
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
    $venvDir = Join-Path $root ".venv"
    if (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv $venvDir
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        py -3 -m venv $venvDir
    } elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
        python3 -m venv $venvDir
    } else {
        throw "Python executable was not found in PATH (tried python, py, python3)."
    }
}

& $venvPython -m pip install -r (Join-Path $root "requirements.txt")
$port = Get-FreePort -StartPort $preferredPort

Write-Host ""
Write-Host "Starting E-Miu Advanced EV Station Monitoring System on port $port" -ForegroundColor Cyan
Write-Host "Laptop URL: http://localhost:$port" -ForegroundColor Green
Write-Host "Phone URL:  http://$(hostname):$port" -ForegroundColor Green
Write-Host ""

& $venvPython -m streamlit run (Join-Path $root "app.py") --server.address 0.0.0.0 --server.port $port

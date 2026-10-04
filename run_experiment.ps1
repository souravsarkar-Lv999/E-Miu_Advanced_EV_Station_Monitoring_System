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
        try {
            $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
            $listener.Start()
            $listener.Stop()
            return $port
        } catch {
            continue
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
        Write-Host "No system Python detected. Setting up portable environment in project folder..." -ForegroundColor Yellow
        $toolsDir = Join-Path $root ".tools"
        $uvExe = Join-Path $toolsDir "uv.exe"
        if (-not (Test-Path $uvExe)) {
            New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
            $zipPath = Join-Path $toolsDir "uv.zip"
            curl.exe -sL "https://github.com/astral-sh/uv/releases/download/0.4.18/uv-x86_64-pc-windows-msvc.zip" -o $zipPath
            tar.exe -xf $zipPath -C $toolsDir
            if (Test-Path $zipPath) { Remove-Item $zipPath }
        }
        $env:UV_PYTHON_INSTALL_DIR = Join-Path $root ".python"
        & $uvExe venv $venvDir --python 3.12
        & $uvExe pip install pip --python (Join-Path $venvDir "Scripts\python.exe")
    }
}

$toolsUv = Join-Path $root ".tools\uv.exe"
if (Test-Path $toolsUv) {
    & $toolsUv pip install -r (Join-Path $root "requirements.txt") --python $venvPython
} else {
    & $venvPython -m pip install -r (Join-Path $root "requirements.txt")
}

$port = Get-FreePort -StartPort $preferredPort

$localIp = try {
    (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Wi-Fi*", "Ethernet*" -ErrorAction SilentlyContinue |
     Where-Object { $_.IPAddress -notmatch '^127\.' -and $_.IPAddress -notmatch '^169\.254\.' } |
     Select-Object -First 1).IPAddress
} catch { $null }

if (-not $localIp) {
    $localIp = hostname
}

Write-Host ""
Write-Host "Starting E-Miu Advanced EV Station Monitoring System on port $port" -ForegroundColor Cyan
Write-Host "Laptop URL: http://localhost:$port" -ForegroundColor Green
Write-Host "Phone URL:  http://${localIp}:$port" -ForegroundColor Green
Write-Host ""

& $venvPython -m streamlit run (Join-Path $root "app.py") --server.address 0.0.0.0 --server.port $port

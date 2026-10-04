$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = if ($IsWindows -ne $false) {
    Join-Path $root ".venv\Scripts\python.exe"
} else {
    Join-Path $root ".venv/bin/python"
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

function Find-RealPython {
    foreach ($cmd in @("python", "py", "python3")) {
        try {
            $entry = Get-Command $cmd -ErrorAction SilentlyContinue
            if ($entry) {
                $ver = & $entry.Source -c "import sys; print(sys.version_info[0])" 2>$null
                if ($LASTEXITCODE -eq 0 -and $ver -ge 3) {
                    return $entry.Source
                }
            }
        } catch {
            continue
        }
    }
    return $null
}

function Test-VenvFunctional {
    param([string]$PythonPath)
    if (-not (Test-Path $PythonPath)) { return $false }
    try {
        $test = & $PythonPath -c "import sys; print('ok')" 2>$null
        if ($LASTEXITCODE -eq 0 -and $test -match "ok") {
            return $true
        }
    } catch {
        return $false
    }
    return $false
}

$venvDir = Join-Path $root ".venv"

if (-not (Test-VenvFunctional $venvPython)) {
    if (Test-Path $venvDir) {
        Write-Host "Detected moved or invalid virtual environment. Rebuilding .venv in project folder..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $venvDir -ErrorAction SilentlyContinue
    }

    $toolsDir = Join-Path $root ".tools"
    $uvExe = Join-Path $toolsDir "uv.exe"
    $localPythonDir = Join-Path $root ".python"
    $portablePython = Get-ChildItem -Path $localPythonDir -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName

    if ($portablePython -and (Test-Path $portablePython) -and (Test-Path $uvExe)) {
        Write-Host "Linking virtual environment with existing portable Python..." -ForegroundColor Cyan
        & $uvExe venv $venvDir --python $portablePython
        & $uvExe pip install pip --python (Join-Path $venvDir "Scripts\python.exe")
    } else {
        $realPython = Find-RealPython
        if ($realPython) {
            Write-Host "Creating virtual environment with system Python ($realPython)..." -ForegroundColor Cyan
            & $realPython -m venv $venvDir
        } else {
            Write-Host "No working Python runtime found on system." -ForegroundColor Yellow
            Write-Host "Setting up portable Python 3.12 strictly inside the project folder..." -ForegroundColor Cyan
            if (-not (Test-Path $uvExe)) {
                New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
                $zipPath = Join-Path $toolsDir "uv.zip"
                curl.exe -sL "https://github.com/astral-sh/uv/releases/download/0.4.18/uv-x86_64-pc-windows-msvc.zip" -o $zipPath
                tar.exe -xf $zipPath -C $toolsDir
                if (Test-Path $zipPath) { Remove-Item $zipPath }
            }
            $env:UV_PYTHON_INSTALL_DIR = $localPythonDir
            & $uvExe venv $venvDir --python 3.12
            & $uvExe pip install pip --python (Join-Path $venvDir "Scripts\python.exe")
        }
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

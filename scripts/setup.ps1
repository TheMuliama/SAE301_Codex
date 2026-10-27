$ErrorActionPreference = "Stop"

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    Write-Error "This script supports Windows. On Linux, run scripts/setup.sh."
}

$Python = Get-Command py -ErrorAction SilentlyContinue
if (-not $Python) {
    Write-Error "Python 3.10+ is required. Install it from python.org, enable the py launcher, then rerun."
}

py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 10))"
if ($LASTEXITCODE -ne 0) { Write-Error "Python 3.10 or newer is required." }

py -3 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if ($args -contains "-WithPluto") {
    & .\.venv\Scripts\python.exe -m pip install -r requirements-pluto.txt
}
& .\.venv\Scripts\python.exe -m pip install --no-deps -e .
& .\.venv\Scripts\python.exe -m sae301 check --mode simulation

Write-Host "Setup complete."
Write-Host "Receiver:    .\.venv\Scripts\python.exe -m sae301 receiver --mode simulation"
Write-Host "Transmitter: .\.venv\Scripts\python.exe -m sae301 transmitter --mode simulation"
Write-Host "Use -WithPluto only after installing the Analog Devices libiio Windows runtime/driver."

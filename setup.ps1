# Siapkan virtualenv + dependency (sekali saja)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pytest

New-Item -ItemType Directory -Force secrets, data | Out-Null
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "File .env dibuat dari .env.example. Isi TELEGRAM_BOT_TOKEN dulu."
}
Write-Host "Setup selesai."

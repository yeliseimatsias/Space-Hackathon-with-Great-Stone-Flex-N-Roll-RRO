# Запуск API с hot-reload (из корня репозитория):
#   powershell -ExecutionPolicy Bypass -File scripts/dev.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

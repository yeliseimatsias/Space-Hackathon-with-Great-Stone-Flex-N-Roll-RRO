# Полная подготовка окружения (Windows, PowerShell). Запуск из корня репозитория:
#   powershell -ExecutionPolicy Bypass -File scripts/setup.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$ComposeFile = Join-Path $Root "docker\docker-compose.yml"

Write-Host "==> Каталог проекта: $Root"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "==> Создан .env из .env.example — откройте .env и вставьте TELEGRAM_BOT_TOKEN, BASE_URL, BITRIX_WEBHOOK_URL, LLM_API_KEY."
} else {
    Write-Host "==> .env уже есть, не перезаписываю."
}

Write-Host "==> pip install -r requirements.txt"
python -m pip install -r requirements.txt

Write-Host "==> Поднимаю только PostgreSQL (docker)..."
try {
    docker compose -f $ComposeFile up db -d
    Write-Host "==> Жду готовности Postgres..."
    $ok = $false
    for ($i = 0; $i -lt 40; $i++) {
        docker compose -f $ComposeFile exec -T db pg_isready -U app -d flexnroll 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $ok = $true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $ok) {
        Write-Host "WARN: pg_isready не ответил; смотрите: docker compose -f docker\docker-compose.yml logs db"
    }
} catch {
    Write-Host "WARN: Docker недоступен — поднимите Postgres вручную и проверьте DATABASE_URL в .env (имя БД flexnroll)."
}

Write-Host "==> alembic upgrade head"
python -m alembic -c alembic/alembic.ini upgrade head

Write-Host ""
Write-Host "Готово. Дальше:"
Write-Host "  1) Заполните секреты в .env (если ещё не заполнили)."
Write-Host "  2) Запуск API:  powershell -ExecutionPolicy Bypass -File scripts/dev.ps1"
Write-Host ""

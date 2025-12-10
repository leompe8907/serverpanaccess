# Script para iniciar Celery Beat
# Uso: .\start_celery_beat.ps1
# Las variables de entorno se cargan automáticamente desde .env

cd $PSScriptRoot
& .\env\Scripts\Activate.ps1

# Borrar schedule anterior para forzar recarga
Write-Host "Borrando schedule anterior..." -ForegroundColor Yellow
Get-ChildItem -Path . -Filter "celerybeat-schedule*" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

# Leer CELERY_SYNC_MINUTES desde .env para mostrar en el mensaje
$syncMinutes = (Get-Content .env | Select-String -Pattern "CELERY_SYNC_MINUTES=(\d+)" | ForEach-Object { $_.Matches.Groups[1].Value })
if (-not $syncMinutes) { $syncMinutes = "2" }

Write-Host "Iniciando Celery Beat (cada $syncMinutes minutos)..." -ForegroundColor Green
Write-Host "(Variables cargadas desde .env)" -ForegroundColor Gray
celery -A serverpanaccess beat -l info


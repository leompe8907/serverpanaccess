# Script para iniciar Celery Worker
# Uso: .\start_celery_worker.ps1
# Las variables de entorno se cargan automáticamente desde .env

cd $PSScriptRoot
& .\env\Scripts\Activate.ps1

Write-Host "Iniciando Celery Worker..." -ForegroundColor Green
Write-Host "(Variables cargadas desde .env)" -ForegroundColor Gray
celery -A serverpanaccess worker -l info -Q sync_subscribers -P solo --concurrency 1


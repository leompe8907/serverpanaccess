# Proxy HTTPS :8443 -> Daphne :8000. Requiere setup_local_https.ps1 y Daphne en marcha.
#   .\scripts\run_local_https.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoRoot

$Caddyfile = Join-Path $RepoRoot "deploy\local\Caddyfile"
$Cert = Join-Path $RepoRoot "deploy\local\certs\localhost+2.pem"
$Key = Join-Path $RepoRoot "deploy\local\certs\localhost+2-key.pem"

if (-not (Test-Path $Cert) -or -not (Test-Path $Key)) {
    Write-Host "No hay certificados. Ejecuta primero: .\scripts\setup_local_https.ps1" -ForegroundColor Red
    exit 1
}

# Comprobar que algo escucha en 8000
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect("127.0.0.1", 8000)
    $tcp.Close()
} catch {
    Write-Host "Nada escucha en 127.0.0.1:8000. Arranca Daphne antes:" -ForegroundColor Red
    Write-Host "  daphne -b 127.0.0.1 -p 8000 serverpanaccess.asgi:application"
    exit 1
}

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")
if (-not (Get-Command caddy -ErrorAction SilentlyContinue)) {
    $caddyGuess = "$env:LOCALAPPDATA\Microsoft\WinGet\Links\caddy.exe"
    if (Test-Path $caddyGuess) { $env:Path += ";$env:LOCALAPPDATA\Microsoft\WinGet\Links" }
}

Write-Host "=== Caddy HTTPS local ===" -ForegroundColor Cyan
Write-Host "  https://localhost:8444/wind/login/"
Write-Host "  https://127.0.0.1:8444/wind/login/"
Write-Host "Ctrl+C para detener."
Write-Host ""

# Caddy resuelve rutas del Caddyfile desde deploy/local/
Push-Location (Join-Path $RepoRoot "deploy\local")
try {
    & caddy run --config Caddyfile
} finally {
    Pop-Location
}

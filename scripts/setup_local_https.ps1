# Instala mkcert + Caddy (winget), genera certificados de confianza local y deja listo HTTPS en :8443.
# Ejecutar desde la raíz del repo:  .\scripts\setup_local_https.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoRoot

$CertsDir = Join-Path $RepoRoot "deploy\local\certs"
New-Item -ItemType Directory -Force -Path $CertsDir | Out-Null

function Ensure-WingetPackage {
    param([string]$Id, [string]$Name)
    $installed = winget list --id $Id -e 2>$null | Select-String $Id
    if ($installed) {
        Write-Host "[OK] $Name ya instalado ($Id)"
        return
    }
    Write-Host "[..] Instalando $Name ($Id)..."
    winget install --id $Id -e --accept-package-agreements --accept-source-agreements
}

Write-Host "=== Win backend: HTTPS local (mkcert + Caddy) ===" -ForegroundColor Cyan

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "winget no está disponible. Instala App Installer desde Microsoft Store."
}

Ensure-WingetPackage -Id "FiloSottile.mkcert" -Name "mkcert"
Ensure-WingetPackage -Id "CaddyServer.Caddy" -Name "Caddy"

# Refrescar PATH en esta sesión
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

if (-not (Get-Command mkcert -ErrorAction SilentlyContinue)) {
    $mkcertGuess = "$env:LOCALAPPDATA\Microsoft\WinGet\Links\mkcert.exe"
    if (Test-Path $mkcertGuess) { $env:Path += ";$env:LOCALAPPDATA\Microsoft\WinGet\Links" }
}
if (-not (Get-Command caddy -ErrorAction SilentlyContinue)) {
    $caddyGuess = "$env:LOCALAPPDATA\Microsoft\WinGet\Links\caddy.exe"
    if (Test-Path $caddyGuess) { $env:Path += ";$env:LOCALAPPDATA\Microsoft\WinGet\Links" }
}

Write-Host "[..] Instalando CA local de mkcert (puede pedir confirmación UAC)..."
& mkcert -install

Push-Location $CertsDir
try {
    Write-Host "[..] Generando certificados en $CertsDir ..."
    & mkcert -cert-file "localhost+2.pem" -key-file "localhost+2-key.pem" localhost 127.0.0.1 ::1
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Listo. Certificados en: $CertsDir" -ForegroundColor Green
Write-Host ""
Write-Host "Siguiente paso:" -ForegroundColor Yellow
Write-Host "  1. Terminal A: daphne -b 127.0.0.1 -p 8000 serverpanaccess.asgi:application"
Write-Host "  2. Terminal B: .\scripts\run_local_https.ps1"
Write-Host "  3. Navegador:   https://localhost:8444/wind/login/"
Write-Host ""
Write-Host "En Google Cloud y Meta Developer anade el origen HTTPS:" -ForegroundColor Yellow
Write-Host "  https://localhost:8444"
Write-Host "  (ALLOWED_HOSTS en .env: localhost,127.0.0.1)"
Write-Host ""
Write-Host "Docs: docs/LOGIN_SOCIAL_LOCAL_HTTPS.md"

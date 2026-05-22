# Login social en local con HTTPS (Facebook + Google)

Facebook **no permite** `FB.login` en páginas `http://`. En desarrollo local usa un proxy TLS delante de Daphne.

## Requisitos

- Windows con **winget**
- **Daphne** (o Gunicorn) en `127.0.0.1:8000`
- Variables social en `.env` (`GOOGLE_CLIENT_ID`, `FACEBOOK_APP_ID`, etc.)
- `SocialApp` de Facebook/Google en Django Admin (mismo `client_id` que `.env`)

## Instalación (una vez)

Desde la raíz del repo en PowerShell:

```powershell
.\scripts\setup_local_https.ps1
```

Instala **mkcert** y **Caddy**, crea la CA de confianza en el sistema y genera certificados en `deploy/local/certs/` (no se suben a git).

> **Puerto 8444:** en esta máquina el **8443** ya estaba ocupado por otro servicio; el proxy local usa **8444**. Si 8444 también falla al arrancar Caddy, edita `deploy/local/Caddyfile`.

## Uso cada día

**Terminal A** — backend:

```powershell
daphne -b 127.0.0.1 -p 8000 serverpanaccess.asgi:application
```

**Terminal B** — HTTPS:

```powershell
.\scripts\run_local_https.ps1
```

**Navegador** — siempre por HTTPS, no por `:8000`:

- https://localhost:8444/wind/login/
- Prueba Facebook: https://localhost:8444/wind/login-test-facebook/

## Configurar proveedores

### Google Cloud Console

Cliente OAuth **Web** → **Orígenes de JavaScript autorizados**:

```
https://localhost:8444
https://127.0.0.1:8444
```

### Meta for Developers

App → **Facebook Login** → **Settings**:

| Campo | Valor |
|-------|--------|
| Valid OAuth Redirect URIs | `https://localhost:8444/` (y rutas de callback si usas allauth web) |
| App Domains | `localhost` |

Modo **Development**: tu usuario Facebook debe ser tester/admin de la app.

### Django `.env`

```env
DEBUG=true
ALLOWED_HOSTS=localhost,127.0.0.1
```

No hace falta `PRODUCTION_HTTPS=true` en local; Caddy termina TLS y Daphne sigue en HTTP interno.

## Alternativa: ngrok

Si no quieres mkcert/Caddy:

```powershell
ngrok http 8000
```

Abre la URL `https://....ngrok-free.app/wind/login/` y añade ese host en Google, Meta y `ALLOWED_HOSTS`.

## Solución de problemas

| Síntoma | Acción |
|---------|--------|
| Aviso "Facebook Login solo funciona con HTTPS" | Abre `https://localhost:8444`, no `http://localhost:8000` |
| Certificado no confiable | Vuelve a ejecutar `setup_local_https.ps1` (mkcert -install) |
| Google: origin not allowed | Añade exactamente `https://localhost:8444` en Google Cloud |
| Caddy: certificados no encontrados | Ejecuta `setup_local_https.ps1` |
| 502 / connection refused | Arranca Daphne en `:8000` antes que Caddy |

## Producción

En Ubuntu con nginx + Let's Encrypt no uses estos scripts; ver [NGINX_TLS_Y_RESTRICCION_UBUNTU.md](./NGINX_TLS_Y_RESTRICCION_UBUNTU.md).

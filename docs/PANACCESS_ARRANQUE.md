# Checklist arranque PanAccess (roadmap #15)

El servidor **no debe arrancar** sin las variables de integración con PanAccess. La validación corre al importar `settings` (`PanaccessConfig.validate()`).

## Variables obligatorias en `.env`

| Variable | Descripción |
|----------|-------------|
| `url_panaccess` | URL base de la API PanAccess |
| `username` | Usuario API |
| `password` | Contraseña API |
| `api_token` | Token API |
| `salt` | Salt para firmas |
| `hcId` | ID del operador (hcId) |
| `ENCRYPTION_KEY` | Clave Fernet para datos sensibles |

Copiar plantilla desde `.env.example` y completar con valores reales del entorno.

## Comprobar antes de desplegar

```bash
python manage.py check_deploy --strict
```

Debe mostrar: `PanAccess .env: variables obligatorias OK`.

## Login social (opcional por proveedor)

Solo se exigen las credenciales de los proveedores listados en:

```env
SOCIAL_LOGIN_PROVIDERS=google,facebook
```

Ejemplos:

- Solo Google: `SOCIAL_LOGIN_PROVIDERS=google` + vars `GOOGLE_*`
- Sin social en un entorno interno: `SOCIAL_LOGIN_PROVIDERS=` (vacío)

## Redis y sesión PanAccess (producción multi-worker)

```env
PANACCESS_SESSION_USE_REDIS=true
REDIS_HOST=127.0.0.1
```

Ver [PANACCESS_SESION_REDIS.md](./PANACCESS_SESION_REDIS.md).

## Orden recomendado en Ubuntu

1. PostgreSQL + `migrate`
2. Redis + variables Celery
3. Completar `.env` PanAccess + `check_deploy --strict`
4. `systemctl start` gunicorn, celery worker, celery beat
5. Deploy manual sync (una vez) — [SYNC_FLUJO_TAREAS.md](./SYNC_FLUJO_TAREAS.md)

## Si falla al arrancar

```
EnvironmentError: Faltan variables de entorno: url_panaccess, ...
```

Corregir `.env`, reiniciar Gunicorn/Daphne. No desactivar la validación en producción.

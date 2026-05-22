# Sentry en staging/producción (roadmap #18)

Errores de Django y Celery visibles en [Sentry](https://sentry.io) cuando ocurren de noche (full-sync, worker, etc.).

## Ya integrado en el proyecto

Si `SENTRY_DSN` está en `.env`, al arrancar Django se ejecuta `sentry_sdk.init()` en `serverpanaccess/settings.py` con:

- Django
- Celery
- Redis

Dependencia: `sentry-sdk[django]` en `requirements.txt`.

## Configuración en `.env`

```env
SENTRY_DSN=https://xxxx@o000.ingest.sentry.io/0000
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
```

En staging usa `SENTRY_ENVIRONMENT=staging`.

Sin `SENTRY_DSN` el proyecto arranca igual (Sentry desactivado).

## Probar que funciona

Con el servidor corriendo y `SENTRY_DSN` definido:

```bash
python manage.py sentry_test
```

Debe aparecer un evento de prueba en el proyecto Sentry (mensaje: `Win backend Sentry test (manage.py sentry_test)`).

## Qué verás en producción

- Excepciones no capturadas en vistas DRF
- Fallos en tareas Celery (`full_sync_task`, compare, etc.)
- Contexto: entorno (`SENTRY_ENVIRONMENT`), release si lo añades después

## Buenas prácticas

| Hacer | Evitar |
|-------|--------|
| DSN solo en servidor (`.env`, no en git) | Commitear `SENTRY_DSN` |
| `traces_sample_rate` bajo (0.05–0.1) en prod | 1.0 en alto tráfico |
| Alertas por email/Slack en Sentry | Ignorar errores de `skipped` normales en Celery |

## Referencias

- [DESPLIEGUE.md](./DESPLIEGUE.md)
- [ROADMAP_PRODUCCION.md](./ROADMAP_PRODUCCION.md) — ítem #18

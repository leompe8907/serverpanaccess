# Sync HTTP en horario pico (roadmap #10)

Los endpoints **`POST /wind/sync-*`** ejecutan la sincronización **dentro del worker web** (Gunicorn/Daphne). Pueden tardar **varios minutos** y bloquear un worker mientras corren.

## Regla operativa

| Cuándo | Qué usar |
|--------|----------|
| **Horario pico** (usuarios activos) | **No** llamar sync HTTP. Dejar que Celery Beat (`compare_and_update_*`) y el full-sync nocturno mantengan los datos. |
| **Deploy inicial** (una vez) | Sync HTTP staff/VPN: ver [SYNC_FLUJO_TAREAS.md](./SYNC_FLUJO_TAREAS.md) fase 1. |
| **Emergencia** (datos desfasados) | Sync HTTP solo **staff + JWT**, fuera de pico, o encolar tarea Celery. |

## Endpoints afectados

| Ruta | Riesgo en pico |
|------|----------------|
| `POST /wind/sync-subscribers/` | Alto — muchas llamadas PanAccess |
| `POST /wind/sync-products/` | Alto |
| `POST /wind/sync-smartcards/` | Alto |
| `POST /wind/compare-and-update-*` | Alto — reconciliación completa |
| `POST /wind/full-sync/` | Muy alto — deshabilitado en prod (`FULL_SYNC_HTTP_ENABLED=false`) |

## Alternativa sin bloquear Gunicorn

Encolar en Celery (mismo resultado, worker dedicado):

```python
from wind.tasks import (
    compare_and_update_subscribers_task,
    compare_and_update_smartcards_task,
    sync_subscribers_task,
)
compare_and_update_subscribers_task.delay()
```

O esperar al **full-sync nocturno** (`CELERY_FULL_SYNC_ENABLED=true`).

## Protecciones ya en el proyecto

- nginx: sync no expuesto a internet abierto ([NGINX_TLS_Y_RESTRICCION_UBUNTU.md](./NGINX_TLS_Y_RESTRICCION_UBUNTU.md)).
- `FULL_SYNC_HTTP_ENABLED=false` en producción.
- Tareas Beat con `skipped` si hay full-sync en curso.

## Checklist staff (emergencia)

1. Confirmar que no es horario pico o avisar al equipo.
2. Autenticarse con usuario **staff** (JWT).
3. Llamar **un** endpoint con `?limit=200` (no encadenar los tres a la vez en pico).
4. Revisar logs del worker web y de Celery.
5. Si tarda >10 min, valorar `sync_*_task.delay()` en lugar de HTTP.

Ver también: [SYNC_FLUJO_TAREAS.md](./SYNC_FLUJO_TAREAS.md), [FULL_SYNC_PRODUCCION.md](./FULL_SYNC_PRODUCCION.md).

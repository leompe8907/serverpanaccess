# Sync HTTP asíncrono vía Celery (roadmap #26)

Los `POST /wind/sync-*` y `compare-and-update-*` **encolan Celery** por defecto y responden **202** con `task_id`, sin bloquear Gunicorn.

## Comportamiento

| Método | Respuesta |
|--------|-----------|
| `GET` | Info del endpoint y nombre de tarea Celery |
| `POST` (default) | **202** + `task_id` + `status_url` |
| `POST` con `SYNC_HTTP_ASYNC=false` | **200** síncrono (legacy / dev sin worker) |

## Variable `.env`

```env
SYNC_HTTP_ASYNC=true
```

En local sin Celery worker:

```env
SYNC_HTTP_ASYNC=false
```

## Deploy manual (fase 1)

Con worker activo:

```http
POST /wind/sync-subscribers/?limit=200
POST /wind/sync-products/?limit=200
POST /wind/sync-smartcards/?limit=200
Authorization: Bearer <jwt_staff>
```

Respuesta ejemplo:

```json
{
  "success": true,
  "message": "sync-subscribers encolado",
  "task_id": "abc-123",
  "limit": 200,
  "status_url": "/api/v1/tasks/abc-123/"
}
```

Consultar estado:

```http
GET /api/v1/tasks/abc-123/
```

## Tareas Celery

| Endpoint | Task |
|----------|------|
| `sync-subscribers/` | `sync_subscribers_task` |
| `sync-products/` | `sync_products_task` |
| `sync-smartcards/` | `sync_smartcards_task` |
| `compare-and-update-subscribers/` | `compare_and_update_subscribers_task` |
| `full-sync/` | `full_sync_task` (requiere `FULL_SYNC_HTTP_ENABLED=true`) |

## Referencias

- [SYNC_FLUJO_TAREAS.md](./SYNC_FLUJO_TAREAS.md)
- [SYNC_HTTP_OPERACION.md](./SYNC_HTTP_OPERACION.md)

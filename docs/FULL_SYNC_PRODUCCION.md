# Full-sync correctivo en producción (roadmap #8)

El **full sync** alinea suscriptores, productos, smartcards y login info con PanAccess, incluyendo borrados locales que ya no existen en remoto. Es **pesado** y debe ejecutarse en horario bajo tráfico.

## Configuración recomendada (`.env`)

```env
CELERY_FULL_SYNC_ENABLED=true
CELERY_FULL_SYNC_HOUR=0
CELERY_FULL_SYNC_MINUTE=0
FULL_SYNC_HTTP_ENABLED=false
```

| Variable | Prod | Efecto |
|----------|------|--------|
| `CELERY_FULL_SYNC_ENABLED` | `true` | Beat programa `full_sync_task` cada noche |
| `CELERY_FULL_SYNC_HOUR` / `MINUTE` | p. ej. `0` / `0` | Hora local del servidor (00:00) |
| `FULL_SYNC_HTTP_ENABLED` | **`false`** | `POST /wind/full-sync/` → **403** aunque haya JWT staff |

## Canales de ejecución

1. **Automático (prod)** — Celery Beat → worker cola `sync_subscribers` → `run_full_sync()`.
2. **HTTP (solo emergencia)** — Con `FULL_SYNC_HTTP_ENABLED=true`, staff hace `POST /wind/full-sync/` y recibe **202** + `task_id` (encola la misma tarea; no bloquea Gunicorn).

Mientras corre el full sync, las tareas incrementales (`sync_subscribers_task`, etc.) devuelven `skipped` para no interferir.

## Capas de protección

- **`.env`** — `FULL_SYNC_HTTP_ENABLED=false`
- **`check_deploy --strict`** — falla si HTTP está habilitado en prod
- **nginx** — `/wind/full-sync/` solo desde VPN/localhost (ver [NGINX_TLS_Y_RESTRICCION_UBUNTU.md](./NGINX_TLS_Y_RESTRICCION_UBUNTU.md))

## Pruebas

```bash
python manage.py check_deploy --strict

# Con FULL_SYNC_HTTP_ENABLED=false (esperado en prod)
curl -X POST https://api.tudominio.com/wind/full-sync/ \
  -H "Authorization: Bearer <token_staff>"
# → 403

# Verificar Beat (en el servidor Ubuntu)
systemctl status win-celery-beat
# Logs del worker a la hora programada: "Iniciando full_sync_task"
```

## Staging / emergencia

```env
FULL_SYNC_HTTP_ENABLED=true
```

Solo en red controlada (VPN). Tras el correctivo, volver a `false`.

## Referencias

- [DESPLIEGUE.md](./DESPLIEGUE.md) — worker, beat, colas
- [REDIS_CELERY_UBUNTU.md](./REDIS_CELERY_UBUNTU.md) — instalación en Ubuntu

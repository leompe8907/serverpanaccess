# Sesión PanAccess en Redis — multi-worker (roadmap #9)

El backend usa una **cuenta de servicio** en PanAccess (`username` / `password` del `.env`). Tras el login, PanAccess devuelve un `session_id` que debe reutilizarse en todas las llamadas API.

## El problema sin Redis

Gunicorn lanza **varios procesos** (p. ej. `--workers 4` en `deploy/systemd/win-gunicorn.service`). Cada proceso tiene su propio singleton en RAM:

- Worker 1 → login → `session_id` solo en memoria de 1  
- Worker 2 → otro login → otra sesión  
- Más carga en PanAccess, riesgo de rate limit y comportamiento errático al caducar sesiones

## La solución

Con **`PANACCESS_SESSION_USE_REDIS=true`**, el `session_id` se guarda en Redis (`panaccess:session_id`). Todos los workers (y el worker Celery si comparte settings) leen la misma sesión. Si expira, un **lock** (`panaccess:session:refresh`) hace que solo un proceso ejecute el login.

## Variables `.env`

```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

PANACCESS_SESSION_USE_REDIS=true
PANACCESS_SESSION_TTL_SECONDS=1500
```

| Variable | Prod | Notas |
|----------|------|--------|
| `PANACCESS_SESSION_USE_REDIS` | **`true`** | Obligatorio con 2+ workers Gunicorn |
| `PANACCESS_SESSION_TTL_SECONDS` | `1500` (~25 min) | TTL de la clave en Redis; alinear con caducidad PanAccess si se conoce |

Si no defines `PANACCESS_SESSION_USE_REDIS`, el default en `settings.py` es `true` cuando `CELERY_TASK_ALWAYS_EAGER=false`. En Ubuntu conviene declararlo **explícito** en `.env`.

## Infraestructura

1. Redis instalado y accesible (`apt install redis-server`).
2. Gunicorn con varios workers (plantilla: 4).
3. Mismo Redis para broker Celery, locks y sesión PanAccess (DB `REDIS_DB` por defecto).

## Pruebas

```bash
python manage.py check_redis
# Debe mostrar: panaccess_session_store: ok

python manage.py check_deploy
# PANACCESS_SESSION_USE_REDIS: True
# Redis (sesión PanAccess): ping OK
```

En prod:

```bash
python manage.py check_deploy --strict
```

Varias peticiones que usen PanAccess (perfil, health con PanAccess) no deben generar un “Intento login #1” en **cada** worker en logs; solo al arrancar o al renovar sesión.

## Desarrollo local

- Con **Daphne/Gunicorn de un solo proceso** y sin Redis: puede funcionar sin la clave (sesión en RAM).
- Con **varios workers** o Celery + web: activar Redis y `PANACCESS_SESSION_USE_REDIS=true`.

## Referencias

- `wind/services/panaccess_session_store.py` — lectura/escritura Redis
- `wind/services/panaccess_singleton.py` — `ensure_session()` y lock
- [REDIS_CELERY_UBUNTU.md](./REDIS_CELERY_UBUNTU.md) — instalación Redis
- [DESPLIEGUE.md](./DESPLIEGUE.md) — Gunicorn systemd

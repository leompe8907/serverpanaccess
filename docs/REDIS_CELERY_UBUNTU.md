# Redis y Celery en Ubuntu Server (roadmap #2)

Sin Docker. Redis y Celery corren en el mismo servidor que la aplicación Django.

## Arquitectura

```text
Gunicorn (API HTTP)
       │
       ├── PostgreSQL
       └── Redis (DB 0 = broker Celery + locks + sesión PanAccess)
                ├── Celery Worker  (-Q sync_subscribers)
                └── Celery Beat    (programa sync cada 10 min + full sync 00:00)
```

| Redis DB | Uso |
|----------|-----|
| `0` (`REDIS_DB`) | Broker Celery, result backend, locks, flag full-sync |
| `1` (`REDIS_CACHE_DB`) | Caché Django (`CACHES`) |

---

## 1. Instalar Redis

```bash
sudo apt update
sudo apt install -y redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

Comprobar:

```bash
redis-cli ping
# PONG
```

Opcional (solo localhost, recomendado):

```bash
sudo sed -i 's/^# supervised no/supervised systemd/' /etc/redis/redis.conf
sudo systemctl restart redis-server
```

Si más adelante pones contraseña en Redis, define `REDIS_PASSWORD` en `.env`.

---

## 2. Variables en `.env`

Añade o revisa en el servidor:

```env
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
REDIS_CACHE_DB=1
CELERY_TASK_ALWAYS_EAGER=false

PANACCESS_SESSION_USE_REDIS=true
PANACCESS_SESSION_TTL_SECONDS=1500
# Ver [PANACCESS_SESION_REDIS.md](./PANACCESS_SESION_REDIS.md) (roadmap #9)

CELERY_SYNC_MINUTES=10
CELERY_SMARTCARD_SYNC_MINUTES=10
CELERY_SYNC_LIMIT=200
CELERY_SYNC_QUEUE=sync_subscribers

CELERY_FULL_SYNC_ENABLED=true
CELERY_FULL_SYNC_HOUR=0
CELERY_FULL_SYNC_MINUTE=0
FULL_SYNC_HTTP_ENABLED=false
```

**Crítico:** `CELERY_TASK_ALWAYS_EAGER=false` en producción. Si es `true`, las tareas no usan el worker.

---

## 3. Comprobar desde Django

Con el venv activado en `/ruta/al/win-backend`:

```bash
python manage.py check_redis
python manage.py check_database
```

`check_redis` debe mostrar `ping: PONG`, `broker: ok`, `cache_db: ok`.

---

## 4. Probar Celery manualmente (antes de systemd)

Terminal 1 — worker (cola obligatoria):

```bash
cd /ruta/al/win-backend
source env/bin/activate
python -m celery -A serverpanaccess worker -l info -Q sync_subscribers
```

Terminal 2 — beat:

```bash
cd /ruta/al/win-backend
source env/bin/activate
python -m celery -A serverpanaccess beat -l info
```

Terminal 3 — encolar una tarea de prueba:

```bash
cd /ruta/al/win-backend
source env/bin/activate
python manage.py shell -c "from wind.tasks import compare_and_update_subscribers_task; r=compare_and_update_subscribers_task.delay(); print('task_id', r.id)"
```

En el worker debe aparecer `compare_and_update_subscribers_task` ejecutándose o completada.

Inspección rápida:

```bash
python -m celery -A serverpanaccess inspect ping
```

---

## 5. Servicios systemd (producción)

Plantillas en `deploy/systemd/`. Ajusta rutas y usuario.

```bash
sudo cp deploy/systemd/win-celery-worker.service /etc/systemd/system/
sudo cp deploy/systemd/win-celery-beat.service /etc/systemd/system/
# Editar User, WorkingDirectory y ruta al venv
sudo nano /etc/systemd/system/win-celery-worker.service
sudo nano /etc/systemd/system/win-celery-beat.service

sudo systemctl daemon-reload
sudo systemctl enable win-celery-worker win-celery-beat
sudo systemctl start win-celery-worker win-celery-beat
sudo systemctl status win-celery-worker win-celery-beat
```

Logs:

```bash
journalctl -u win-celery-worker -f
journalctl -u win-celery-beat -f
```

**Orden de arranque en el servidor:** Redis → PostgreSQL → `migrate` → Gunicorn → Celery worker → Celery beat.

---

## 6. Tareas programadas (por defecto)

| Tarea | Frecuencia |
|-------|------------|
| `compare_and_update_subscribers_task` | Cada `CELERY_SYNC_MINUTES` (10) |
| `compare_and_update_smartcards_task` | Cada `CELERY_SMARTCARD_SYNC_MINUTES` (10) |
| `full_sync_task` | Diario `CELERY_FULL_SYNC_HOUR:MINUTE` (00:00) |

Mientras `full_sync_task` corre, las otras dos se **omiten** (flag en Redis).

---

## 7. Pruebas del roadmap #2

| Prueba | Resultado esperado |
|--------|-------------------|
| `redis-cli ping` | `PONG` |
| `python manage.py check_redis` | `ok: True` |
| Worker con `-Q sync_subscribers` | Procesa tareas encoladas |
| Beat activo | Programa próximas ejecuciones |
| `CELERY_TASK_ALWAYS_EAGER` | `false` en `.env` del servidor |

---

## Solución de problemas

| Síntoma | Solución |
|---------|----------|
| `Connection refused` Redis | `sudo systemctl start redis-server` |
| Tareas no se ejecutan | Falta worker o sin `-Q sync_subscribers` |
| Tareas “instantáneas” en web | `CELERY_TASK_ALWAYS_EAGER=true` → poner `false` |
| Beat no dispara | Servicio beat parado o reloj del servidor mal |
| `Task already running, skipped` | Normal: lock evita duplicados |

---

## Referencias

- [POSTGRESQL_UBUNTU.md](./POSTGRESQL_UBUNTU.md) — ítem #1
- [DESPLIEGUE.md](./DESPLIEGUE.md) — resumen de comandos
- [SYSTEMD_UBUNTU.md](./SYSTEMD_UBUNTU.md) — ítem #16 (Gunicorn + worker + beat)
- [ROADMAP_PRODUCCION.md](./ROADMAP_PRODUCCION.md)

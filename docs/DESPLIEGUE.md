# Guía de arranque — serverpanaccess

Comandos para desarrollo (Windows) y referencia para producción (Linux). Usar siempre el **entorno virtual** del proyecto.

```powershell
# Activar venv (Windows)
.\env\Scripts\Activate.ps1
```

```bash
# Activar venv (Linux)
source env/bin/activate
```

---

## 1. Dependencias y base de datos

```powershell
pip install -r requirements.txt
python manage.py migrate
```

Tras activar `rest_framework_simplejwt.token_blacklist`, `migrate` crea las tablas de tokens revocados (requerido si `BLACKLIST_AFTER_ROTATION=True`).

---

## 2. Servidor web (API)

### Desarrollo — runserver

```powershell
python manage.py runserver 0.0.0.0:8000
```

Inicializa el **singleton PanAccess** en el proceso hijo (`RUN_MAIN=true`).

### Desarrollo / ASGI — Daphne

Usar el Python del venv (no el `daphne.exe` global):

```powershell
python -m daphne -b 0.0.0.0 -p 8000 serverpanaccess.asgi:application
```

Desde la Fase 1, el singleton también se inicializa al arrancar con Daphne.

### Producción — Gunicorn (Linux)

```bash
gunicorn serverpanaccess.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --threads 2 \
  --timeout 120
```

Detrás de **nginx** con TLS y rate limiting.

---

## 3. Redis

Requerido para Celery (salvo modo eager en dev).

**Ubuntu Server:** [REDIS_CELERY_UBUNTU.md](./REDIS_CELERY_UBUNTU.md).

```bash
redis-cli ping
python manage.py check_redis
```

Variables en `.env` (ver `.env.example`).

---

## 4. Celery (tareas en segundo plano)

**Ubuntu:** servicios systemd en `deploy/systemd/` — ver [REDIS_CELERY_UBUNTU.md](./REDIS_CELERY_UBUNTU.md).

Abrir **dos terminales** además del servidor web (desarrollo local).

### Worker (cola obligatoria)

```powershell
python -m celery -A serverpanaccess worker -l info -Q sync_subscribers
```

En Windows el pool `solo` se aplica automáticamente desde settings.

### Beat (programación)

```powershell
python -m celery -A serverpanaccess beat -l info
```

Tareas programadas por defecto:

| Tarea | Horario |
|-------|---------|
| `sync_subscribers_task` | Cada `CELERY_SYNC_MINUTES` |
| `sync_smartcards_task` | Cada `CELERY_SMARTCARD_SYNC_MINUTES` |
| `full_sync_task` | `CELERY_FULL_SYNC_HOUR:MINUTE` (default 00:00) |

---

## 4.1 API v1 — Perfil de usuario (JWT)

Requiere header `Authorization: Bearer <access_token>`.

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/profile/me/` | Usuario + suscriptor vinculado |
| POST | `/api/v1/profile/password/` | Cambio contraseña PanAccess (`code`, `newPass`) |
| GET | `/api/v1/profile/products/` | Catálogo local paginado |

### Full-sync manual (solo staff)

Con `FULL_SYNC_HTTP_ENABLED=true` en `.env`:

```http
POST /wind/full-sync/
Authorization: Bearer <token_admin>
```

Respuesta `202` con `task_id`. Estado:

```http
GET /api/v1/tasks/<task_id>/
```

Por defecto `FULL_SYNC_HTTP_ENABLED=false`: usar solo Celery Beat nocturno.

### Sync operativo (solo administrador)

Rutas `wind/sync-*` y `compare-and-update-*` requieren usuario **staff** (`is_staff=True`).

---


## 5. Portal de usuario (flujo web)

| Paso | URL |
|------|-----|
| Login (página principal) | http://localhost:8000/wind/login/ |
| Registro | http://localhost:8000/wind/register/ |
| Dashboard (requiere JWT) | http://localhost:8000/wind/dashboard/ |

Tras login (email, Google o Facebook) el navegador guarda el JWT y redirige al dashboard.

Las páginas `login-test` y `login-test-facebook` siguen disponibles como referencia de desarrollo.

---

## 6. Comprobar PanAccess singleton

```http
GET http://localhost:8000/wind/singleton/
```

Respuesta esperada: `has_session: true` y validación `cvLoggedIn` OK.

```http
GET http://localhost:8000/wind/login/
```

Renueva o confirma la sesión del singleton (cuenta de servicio, no usuario final).

---

## 6. Fase 3 — Preparación para carga y prod (sin contenedores por ahora)

> **Despliegue en Ubuntu Server:** PostgreSQL, Redis, Gunicorn y Celery en el host (sin contenedores). Ver [POSTGRESQL_UBUNTU.md](./POSTGRESQL_UBUNTU.md) y [ROADMAP_PRODUCCION.md](./ROADMAP_PRODUCCION.md).

### 6.1 PostgreSQL (staging/prod)

**Ubuntu Server (sin Docker):** [POSTGRESQL_UBUNTU.md](./POSTGRESQL_UBUNTU.md).

```bash
python manage.py check_database
python manage.py migrate
```

En `.env` (ver `.env.example`):

```env
DB_ENGINE=django.db.backends.postgresql
DB_NAME=wind
DB_USER=wind
DB_PASSWORD=...
DB_HOST=localhost
DB_PORT=5432
DB_CONN_MAX_AGE=600
```

Sin `DB_ENGINE` postgresql se usa **SQLite** (`db.sqlite3`) en desarrollo.

Migrar datos desde SQLite (ejemplo):

```powershell
python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission --indent 2 > backup.json
# Activar PostgreSQL en .env, luego:
python manage.py migrate
python manage.py loaddata backup.json
```

### 6.2 Caché Redis y sesión PanAccess

```env
REDIS_CACHE_DB=1
PANACCESS_SESSION_USE_REDIS=true
PANACCESS_SESSION_TTL_SECONDS=1500
```

`REDIS_DB=0` sigue siendo el broker Celery; la caché Django usa otra DB.

### 6.3 Health checks

| URL | Uso |
|-----|-----|
| `GET /ready/` | DB + caché (probe ligero antes de enviar tráfico) |
| `GET /health/` | DB + caché + sesión PanAccess |

### 6.4 Sentry (opcional)

```env
SENTRY_DSN=https://...
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
```

### 6.5 Pruebas de carga (Locust)

```powershell
$env:LOCUST_USERNAME="tu_login1"
$env:LOCUST_PASSWORD="tu_password"
locust -f scripts/load/locustfile.py --host http://127.0.0.1:8000
```

Abrir `http://localhost:8089` para la UI de Locust.

---

## 7. Fase 4 — Escala (sin compras)

| Variable | Efecto |
|----------|--------|
| `DB_REPLICA_HOST` | Lecturas en réplica PostgreSQL |
| `CDN_STATIC_URL` | URL base de estáticos en CDN |
| `PANACCESS_CIRCUIT_BREAKER_ENABLED` | Corta llamadas tras fallos de red/timeout |

---

## 8. Variables `.env` relevantes (Fase 1)

| Variable | Ejemplo | Notas |
|----------|---------|--------|
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` en dev | Dominios reales en prod (sin `*`) — [SEGURIDAD_PRODUCCION_UBUNTU.md](./SEGURIDAD_PRODUCCION_UBUNTU.md) |
| `DEBUG` | `True` / `False` | `False` en producción |
| Verificación | `python manage.py check_deploy --strict` | Antes de abrir tráfico en Ubuntu |
| `CELERY_TASK_ALWAYS_EAGER` | `false` | `true` solo sin Redis/worker |
| `REDIS_HOST` | `localhost` | |

---

## 9. Orden de arranque recomendado

1. Redis  
2. `python manage.py migrate` (si hubo cambios)  
3. Servidor web (`runserver` o `daphne`)  
4. `celery worker -Q sync_subscribers`  
5. `celery beat` (si usas tareas programadas)

---

## 10. Solución de problemas

| Problema | Causa habitual | Acción |
|----------|----------------|--------|
| `No module named 'dj_rest_auth'` | Venv no activo o deps sin instalar | `pip install -r requirements.txt` |
| Celery no ejecuta tareas | Worker sin cola | Añadir `-Q sync_subscribers` |
| `Connection refused` Redis | Redis apagado | Iniciar Redis o `CELERY_TASK_ALWAYS_EAGER=true` |
| Daphne usa paquetes globales | `daphne` fuera del venv | `python -m daphne ...` |
| Sesión PanAccess falla | Credenciales `.env` | Revisar `url_panaccess`, `username`, `password`, `api_token` |

---

*Ver también: [ANALISIS_ESCALABILIDAD.md](./ANALISIS_ESCALABILIDAD.md) para roadmap completo.*

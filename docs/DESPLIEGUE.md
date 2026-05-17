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

```powershell
# Verificar (si redis-cli está instalado)
redis-cli ping
```

Variables en `.env`:

```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
CELERY_TASK_ALWAYS_EAGER=false
```

---

## 4. Celery (tareas en segundo plano)

Abrir **dos terminales** además del servidor web.

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

## 6. Variables `.env` relevantes (Fase 1)

| Variable | Ejemplo | Notas |
|----------|---------|--------|
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` o `*` en dev | En prod usar dominios reales |
| `DEBUG` | `True` / `False` | `False` en producción |
| `CELERY_TASK_ALWAYS_EAGER` | `false` | `true` solo sin Redis/worker |
| `REDIS_HOST` | `localhost` | |

---

## 7. Orden de arranque recomendado

1. Redis  
2. `python manage.py migrate` (si hubo cambios)  
3. Servidor web (`runserver` o `daphne`)  
4. `celery worker -Q sync_subscribers`  
5. `celery beat` (si usas tareas programadas)

---

## 8. Solución de problemas

| Problema | Causa habitual | Acción |
|----------|----------------|--------|
| `No module named 'dj_rest_auth'` | Venv no activo o deps sin instalar | `pip install -r requirements.txt` |
| Celery no ejecuta tareas | Worker sin cola | Añadir `-Q sync_subscribers` |
| `Connection refused` Redis | Redis apagado | Iniciar Redis o `CELERY_TASK_ALWAYS_EAGER=true` |
| Daphne usa paquetes globales | `daphne` fuera del venv | `python -m daphne ...` |
| Sesión PanAccess falla | Credenciales `.env` | Revisar `url_panaccess`, `username`, `password`, `api_token` |

---

*Ver también: [ANALISIS_ESCALABILIDAD.md](./ANALISIS_ESCALABILIDAD.md) para roadmap completo.*

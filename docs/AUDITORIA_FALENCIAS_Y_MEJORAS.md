# Auditoría técnica completa — Backend serverpanaccess (PanAccess)

**Fecha de revisión:** mayo 2026  
**Alcance:** rendimiento, funcionalidades, lógica, dependencias, flujo de datos, seguridad y preparación para despliegue en Ubuntu Server **sin Docker**.

---

## Resumen ejecutivo

El proyecto es un backend Django que actúa como **puente** entre un frontend (portal / apps móviles) y la API **PanAccess**: sincroniza suscriptores, smartcards y productos vía **Celery + Redis**, expone registro público y login social (Google/Facebook) con **JWT**, y ofrece APIs de perfil para usuarios autenticados.

**Estado general:** la base está bien orientada a producción (validación de `.env`, HTTPS, CORS estricto, locks Redis, circuit breaker, throttling, middleware de IP para sync, plantillas `deploy/`, comando `check_deploy --strict`). Quedan riesgos importantes en **dependencias**, **permisos por defecto de DRF**, **verificación de email desactivada**, **escalabilidad de sync** y **documentación de despliegue fragmentada/obsoleta**.

---

## 1. Arquitectura y flujo del sistema

### 1.1 Componentes

| Componente | Rol |
|------------|-----|
| **Gunicorn (WSGI)** | API HTTP en producción |
| **PostgreSQL** | Persistencia (suscriptores, smartcards, productos, usuarios Django, registro de emails) |
| **Redis DB 0** | Broker Celery, locks distribuidos, sesión PanAccess compartida, flag `full_sync` |
| **Redis DB 1** | Caché Django (`django-redis`) |
| **Celery Worker** | Cola `sync_subscribers`: sync/compare/full-sync |
| **Celery Beat** | `compare_and_update_*` cada N min + `full_sync` nocturno |
| **Nginx** | TLS, proxy, rate limit registro, bloqueo de rutas operativas |
| **PanAccess API** | Fuente de verdad externa |

### 1.2 Flujo de sincronización (correcto y documentado)

1. **Deploy inicial (una vez):** `POST /wind/sync-subscribers/`, `sync-products/`, `sync-smartcards/` → encolan tareas Celery (con `SYNC_HTTP_ASYNC=true` devuelven 202).
2. **Mantenimiento:** Beat ejecuta `compare_and_update_subscribers_task` y `compare_and_update_smartcards_task` cada `CELERY_SYNC_MINUTES` (default 10).
3. **Correctivo nocturno:** `full_sync_task` a las `CELERY_FULL_SYNC_HOUR:MINUTE` (default 00:00), con flag Redis que **omite** tareas incrementales concurrentes.

### 1.3 Flujo de registro de usuario final

1. **Registro HTTP público:** `POST /wind/create-subscriber/` (`AllowAny` + `RegisterThrottle` 10/h).
2. **Login social:** Google/Facebook → `dj-rest-auth` + adaptador `PanAccessSocialAccountAdapter` → crea/vincula suscriptor en PanAccess si no existe.
3. **Portal:** JWT → endpoints `/api/v1/profile/*` con `IsAuthenticated` + `IsOwnerSubscriber`.

### 1.4 Punto débil de arquitectura

- **Single point of failure:** Redis. Si cae, no hay locks fiables, la sesión PanAccess no se comparte entre workers Gunicorn, y Celery deja de procesar. En producción Redis debe tener **supervisión**, **persistencia configurada** (AOF/RDB según política) y **alertas**.
- **Singleton PanAccess por proceso:** cada worker Gunicorn tiene su instancia en memoria; la sesión se mitiga con `panaccess_session_store` en Redis, pero el login inicial puede competir entre workers al arranque (`wind/apps.py` inicializa en `ready()`).

---

## 2. Seguridad

### 2.1 Fortalezas

| Área | Implementación |
|------|----------------|
| Secretos | `SECRET_KEY`, PanAccess y social en `.env`; validación al arranque (`DjangoConfig`, `PanaccessConfig`, `SocialConfig`) |
| Hosts | `ALLOWED_HOSTS` obligatorio; `check_deploy --strict` rechaza `*` |
| HTTPS | `PRODUCTION_HTTPS=true` activa HSTS, cookies seguras, redirect SSL, `SECURE_PROXY_SSL_HEADER` |
| CORS | Prohibido `CORS_ALLOW_ALL_ORIGINS`; en prod exige `CORS_ALLOWED_ORIGINS` |
| Rutas operativas | `SyncAdminIPRestrictionMiddleware` + reglas nginx en `deploy/nginx/win-backend.conf` |
| Registro | Throttle DRF + `limit_req` nginx en `/wind/create-subscriber/` |
| JWT | Refresh con rotación y blacklist (`BLACKLIST_AFTER_ROTATION`) |
| Credenciales PanAccess | `ENCRYPTION_KEY` + utilidades de cifrado en modelos sensibles |
| Errores | Sentry opcional sin PII (`send_default_pii=False`) |

### 2.2 Falencias y riesgos (detalle)

#### 2.2.1 Verificación de email desactivada

```python
ACCOUNT_EMAIL_VERIFICATION = 'none'
```

**Riesgo:** cuentas con email no verificado en registro por contraseña; posible abuso/spam si `CREATE_SUBSCRIBER_PUBLIC_ENABLED=true`.  
**Recomendación:** en producción usar `mandatory` o `optional` con SMTP (SendGrid, SES, Mailgun) y flujo de confirmación; mantener `none` solo en desarrollo.

#### 2.2.2 Permisos por defecto de DRF demasiado permisivos

```python
'DEFAULT_PERMISSION_CLASSES': [
    'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly',
],
```

**Riesgo:** cualquier endpoint que **olvide** declarar `permission_classes` puede exponer lectura anónima según permisos del modelo Django (poco habitual en este proyecto porque casi todo usa decoradores explícitos, pero es un patrón peligroso).  
**Recomendación:** cambiar el default a `IsAuthenticated` y usar `AllowAny` solo donde haga falta (registro, auth pública).

#### 2.2.3 JWT — ventana de acceso larga

- `ACCESS_TOKEN_LIFETIME`: 60 minutos.  
**Recomendación:** 5–15 minutos en producción; el refresh (7 días con rotación) ya está bien configurado.

#### 2.2.4 Cookies JWT en respuestas REST

`JWT_AUTH_COOKIE` y `JWT_AUTH_REFRESH_COOKIE` están definidos. Si el frontend usa **solo** `Authorization: Bearer`, las cookies pueden ser superficie de ataque XSS si no se usan con `HttpOnly`/`Secure` explícitos en la configuración de dj-rest-auth.  
**Recomendación:** documentar un solo modo (header vs cookie); si solo header, desactivar cookies JWT.

#### 2.2.5 Confianza en `X-Forwarded-For`

El middleware de IP y nginx confían en el primer valor de `X-Forwarded-For`. Correcto **solo** si nginx es el único proxy y no es accesible para inyectar cabeceras desde internet.  
**Recomendación:** `set_real_ip_from` en nginx y `real_ip_header X-Forwarded-For`; no exponer Gunicorn directamente.

#### 2.2.6 Endpoints de administración Django

`/admin/` queda expuesto si nginx no lo restringe.  
**Recomendación:** bloquear por IP/VPN o deshabilitar en producción si no se usa.

#### 2.2.7 Registro público

`CREATE_SUBSCRIBER_PUBLIC_ENABLED=true` por defecto. Permite alta sin pasar por atención al cliente (objetivo del negocio), pero requiere:

- CAPTCHA o rate limit más agresivo bajo ataque (nginx + DRF).
- Validación de email/teléfono ya implementada parcialmente; reforzar con verificación de email.
- Monitoreo de creaciones anómalas (métricas Sentry/logs).

#### 2.2.8 Secretos en repositorio

Verificar que `.env` esté en `.gitignore` (debe estarlo). Rotar `SECRET_KEY` y credenciales PanAccess si alguna vez se filtraron.

#### 2.2.9 `locust` en `requirements.txt`

Herramienta de carga en dependencias de producción.  
**Riesgo:** superficie de instalación innecesaria.  
**Recomendación:** mover a `requirements-dev.txt` o grupo opcional.

---

## 3. Dependencias (`requirements.txt`)

### 3.1 Inconsistencia crítica: versión de Django

| Fuente | Versión declarada |
|--------|-------------------|
| `requirements.txt` | `Django==6.0.5` |
| Comentarios en `settings.py` | Django 5.2 |
| Entorno local probado | Django 4.2.0 |

**Problema:** desalineación entre documentación, lockfile y runtime. Antes de desplegar:

```bash
pip install -r requirements.txt
python -c "import django; print(django.get_version())"
python manage.py check
```

Fijar **una** versión LTS soportada por todo el stack (`djangorestframework`, `django-allauth`, `dj-rest-auth`) y actualizar comentarios en `settings.py`.

### 3.2 `psycopg[binary]`

En Ubuntu producción es preferible:

```text
psycopg>=3.2
```

(compilado contra `libpq` del sistema) en lugar de `binary`, por parches de seguridad del SO y compatibilidad con OpenSSL del servidor.

### 3.3 Paquetes pesados o de desarrollo en prod

| Paquete | Observación |
|---------|-------------|
| `daphne`, `Twisted`, `autobahn` | Necesarios si se usa ASGI/WebSockets; el proyecto **no** implementa WebSockets en código actual — solo ASGI estándar de Django |
| `locust` | Solo staging/CI |
| `colorama` | Innecesario en Linux servidor |

### 3.4 Dependencias faltantes recomendadas

| Paquete | Motivo |
|---------|--------|
| `setproctitle` | Identificar procesos Celery/Gunicorn en `ps`/`htop` |
| `django-health-check` (opcional) | Probes más ricos que `/health/` manual |

### 3.5 Pinning

El `requirements.txt` fija versiones exactas (bien para reproducibilidad). Falta un flujo documentado de actualización de seguridad (`pip-audit`, Dependabot).

---

## 4. Configuración Django

### 4.1 Fortalezas

- Validación centralizada en `appConfig.py`.
- `check_deploy --strict` cubre DEBUG, CORS, Redis sesión PanAccess, full-sync HTTP, HTTPS.
- WhiteNoise + manifest en producción para estáticos.
- `CONN_MAX_AGE` configurable para PostgreSQL.
- Router de réplica (`PrimaryReplicaRouter`) preparado.
- Logging rotativo en `logs/` (django, panaccess, errors).

### 4.2 Mejoras necesarias

| Tema | Detalle |
|------|---------|
| **MEDIA** | No hay `MEDIA_ROOT` / `MEDIA_URL`. Si en el futuro hay avatares o documentos, configurar nginx o S3 |
| **Rotación de logs** | 5 × 10 MB por archivo; en sync verboso puede llenar disco — añadir `logrotate` del SO |
| **Apple provider** | Instalado en `INSTALLED_APPS` pero credenciales comentadas; confunde despliegue |
| **SITE_ID = 1** | Requiere `django_site` con dominio correcto en prod para allauth |
| **CSRF** | APIs JWT no usan CSRF; vistas HTML del portal sí — verificar formularios |

---

## 5. Integración PanAccess

### 5.1 Fortalezas

- Cliente singleton thread-safe con reintentos y backoff.
- Sesión en Redis (`panaccess_session_store`) para multi-worker.
- Circuit breaker configurable (`PANACCESS_CIRCUIT_BREAKER_ENABLED`).
- Locks Redis por tarea (`task_lock`) evitan ejecuciones paralelas duplicadas.
- Flag `full_sync_in_progress` evita carreras con sync incremental.
- `bulk_create` en sync de suscriptores/smartcards/productos.
- Excepciones tipadas (`PanAccessException`, auth, timeout, API).

### 5.2 Falencias

| ID | Problema | Impacto | Mitigación |
|----|----------|---------|------------|
| P1 | `CELERY_SYNC_LIMIT=200` por defecto | Con decenas de miles de suscriptores, un ciclo de compare no alcanza; datos locales desactualizados | Subir límite, paginar sync, o aumentar frecuencia; monitorizar lag |
| P2 | `soft_time_limit=540` / `hard=600` | Tareas largas abortan | Ajustar por volumen; dividir en tareas por lote |
| P3 | `autoretry_for` × 5 con backoff | Muchas llamadas fallidas pueden saturar API PanAccess | Reducir reintentos; circuit breaker ya ayuda |
| P4 | Login al arranque en cada worker | Picos de autenticación tras deploy/restart | Mantener `PANACCESS_SESSION_USE_REDIS=true`; considerar delay escalonado |
| P5 | Alertas solo en log | Operador no se entera de caída prolongada | Sentry + alertas email/Slack en `_send_alert` |
| P6 | `VALIDATION_INTERVAL = 900` comentado como 5 min | Comentario incorrecto en código — confusión operativa | Corregir comentario o intervalo |

### 5.3 Sync HTTP síncrono

Con `SYNC_HTTP_ASYNC=false`, `POST /wind/sync-*` bloquean un worker Gunicorn hasta minutos.  
**Obligatorio en prod:** `SYNC_HTTP_ASYNC=true` (default en `check_deploy` strict).

---

## 6. Base de datos

### 6.1 Fortalezas

- Índices en `code`, `emails`, `subscriberCode`, `sn`, login info.
- Migraciones versionadas (`0001`, `0002`).
- Soporte réplica de lectura.
- `SubscriberEmailRegistry` para evitar duplicados de email en registro.

### 6.2 Riesgos de rendimiento

| Área | Observación |
|------|-------------|
| **N+1 en perfil** | `build_subscriber_products_payload` y consultas por código pueden hacer múltiples queries; no hay `select_related`/`prefetch_related` generalizado en capa de catálogo |
| **JSON en columnas** | `smartcards`, `products` en JSON dificultan consultas SQL analíticas |
| **Índice GIN** | Para búsquedas dentro de JSON, considerar índices GIN en PostgreSQL si el volumen crece |
| **Backups** | No hay script en repo — obligatorio en runbook de producción (`pg_dump` cron + retención) |
| **Conexiones** | `workers × threads` de Gunicorn + pool Celery no deben superar `max_connections` de PostgreSQL |

### 6.3 Comandos útiles

```bash
python manage.py check_database
python manage.py migrate --plan
```

---

## 7. Celery y Redis

### 7.1 Configuración actual (correcta)

- Cola dedicada `sync_subscribers`.
- Beat con compare + full sync.
- `CELERY_WORKER_MAX_TASKS_PER_CHILD=100` limita fugas de memoria.
- Pool `prefork` en Linux, `solo` en Windows.

### 7.2 Problemas operativos

| Problema | Guías antiguas vs plantillas actuales |
|----------|-------------------------------------|
| `celery multi` en `guia_despliegue.md` | Obsoleto; usar `Type=simple` como en `deploy/systemd/` |
| Rutas `/var/www/backend` vs `/opt/win-backend` | Inconsistencia entre documentos |
| Usuario `ubuntu` vs `www-data` vs `windapp` | Unificar un usuario de sistema dedicado |
| Sin `EnvironmentFile` en algunas guías | Las plantillas oficiales sí lo incluyen |

### 7.3 Redis en producción

Configurar en `/etc/redis/redis.conf`:

- `bind 127.0.0.1`
- `maxmemory` + `maxmemory-policy allkeys-lru`
- Contraseña (`requirepass`) + `REDIS_PASSWORD` en `.env` si el servidor es compartido

---

## 8. API REST y funcionalidades

### 8.1 Cobertura funcional

| Funcionalidad | Estado |
|---------------|--------|
| Sync suscriptores / smartcards / productos | ✅ Celery + endpoints admin |
| Compare incremental | ✅ Beat |
| Full sync nocturno | ✅ |
| Registro público | ✅ con throttling |
| Login social Google/Facebook | ✅ adaptador PanAccess |
| Perfil / contraseña / productos | ✅ JWT + ownership |
| Health / ready | ✅ `/health/`, `/ready/` |
| Estado de tareas async | ✅ `/api/v1/tasks/<id>/` |

### 8.2 Gaps

- Sin WebSockets en código (la guía `GUIA_DESPLIEGUE_SERVIDOR_PRIVADO.md` describe UDID/WebSockets — **no aplica** a este proyecto).
- Apple Sign-In instalado pero no configurado por defecto.
- Sin API de “estado de sincronización” pública para el front (solo admin).
- Tests automatizados no revisados en esta auditoría — verificar cobertura antes de prod.

---

## 9. Autenticación social

### 9.1 Fortalezas

- Validación de proveedores habilitados vía `SOCIAL_LOGIN_PROVIDERS`.
- Adaptador que crea suscriptor en PanAccess en primer login social.
- Manejo de `MultipleObjectsReturned` en `SocialApp`.

### 9.2 Checklist producción

1. URLs de redirección en Google Cloud Console y Meta **exactas** (`https://api.tudominio.com/...`).
2. `GOOGLE_REDIRECT_URI` / `FACEBOOK_REDIRECT_URI` alineados con el front.
3. Facebook exige HTTPS — usar Caddy local en dev (`docs/LOGIN_SOCIAL_LOCAL_HTTPS.md`).
4. Crear `SocialApp` en Django admin o vía migración/fixture con `SITE_ID` correcto.

---

## 10. Rendimiento y escalabilidad

### 10.1 Estimación de carga (referencia docs internos)

Para **1k–10k usuarios** concurrentes en portal (no sync masivo):

| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| CPU | 4 vCPU | 8+ vCPU |
| RAM | 8 GB | 16 GB+ |
| Disco | 100 GB SSD | 500 GB SSD (logs + PG) |
| PostgreSQL | Mismo host (inicio) | Host dedicado si crece |
| Redis | 512 MB–1 GB | 2 GB+ bajo carga |

### 10.2 Gunicorn

Plantilla actual: `4 workers`, `2 threads`, `timeout 120`.  
Fórmula orientativa: `workers = (2 × CPU) + 1`, ajustar tras pruebas Locust (`docs/LOCUST_STAGING.md`).

**No** usar `uvicorn`/`daphne` en prod salvo que se necesite ASGI real.

### 10.3 Cuellos de botella probables

1. Llamadas síncronas a PanAccess en vistas de perfil si no hay caché local.
2. Sync nocturno compitiendo por CPU/IO con PostgreSQL.
3. Redis single-thread en un solo nodo.

---

## 11. Observabilidad y logs

| Canal | Ubicación |
|-------|-----------|
| Django | `logs/django.log` |
| PanAccess | `logs/panaccess.log` |
| Errores | `logs/errors.log` |
| systemd | `journalctl -u win-gunicorn` etc. |
| Sentry | Si `SENTRY_DSN` definido |

**Falta:** métricas Prometheus/Grafana, alertas de disco, alertas de cola Celery atascada, dashboard de lag de sync.

---

## 12. Preparación para despliegue Ubuntu (sin Docker)

### 12.1 Lo que ya está listo

- `.env.example` exhaustivo.
- `deploy/systemd/*.service` y `deploy/nginx/win-backend.conf`.
- `python manage.py check_deploy --strict`.
- `docs/DEPLOY_UBUNTU_CHECKLIST.md` y guías modulares en `docs/`.

### 12.2 Lo que falta o está mal documentado

| Item | Estado |
|------|--------|
| Guía única consolidada | Parcial — ver `GUIA_DESPLIEGUE_UBUNTU_UNIFICADA.md` |
| `guia_despliegue.md` / `GUIA_DESPLIEGUE_PRODUCCION.md` | Duplicadas, rutas/usuarios distintos |
| `docs/GUIA_DESPLIEGUE_SERVIDOR_PRIVADO.md` | **Obsoleta** (proyecto UDID, WebSockets, `DATABASE_URL`, Python 3.12 PPA innecesario) |
| SSH hardening | Solo mencionado en guías breves |
| Backup/restauración PG | En `POSTGRESQL_UBUNTU.md` parcial |
| `logrotate` | No documentado |
| Fail2ban | Mencionado en guía corta, no en plantillas |

---

## 13. Lista priorizada de acciones

### Crítico (antes de producción)

1. **Alinear versión de Django** y probar `migrate` + `check --deploy`.
2. **Ejecutar** `python manage.py check_deploy --strict` en el servidor y corregir todos los errores.
3. **`PRODUCTION_HTTPS=true`**, `DEBUG=false`, `CORS_ALLOWED_ORIGINS` con dominios reales.
4. **`PANACCESS_SESSION_USE_REDIS=true`** con Redis activo y probado (`check_redis`).
5. **`CELERY_TASK_ALWAYS_EAGER=false`** + worker en cola `sync_subscribers` + beat.
6. **Restringir sync** en nginx (`deploy/nginx/win-backend.conf`) + `SYNC_ADMIN_IP_ALLOWLIST`.
7. **Unificar** usuario/ruta de despliegue (`/opt/win-backend` recomendado).
8. **Eliminar o archivar** `docs/GUIA_DESPLIEGUE_SERVIDOR_PRIVADO.md` como histórico.

### Alto

9. Cambiar default DRF a `IsAuthenticated`.
10. Reducir vida del access token JWT o documentar riesgo aceptado.
11. Plan SMTP + verificación de email si hay registro por contraseña.
12. Mover `locust` fuera de `requirements.txt` de producción.
13. `psycopg` sin `[binary]` en servidor Ubuntu.
14. Configurar Sentry con DSN real.
15. Backups PostgreSQL automatizados + prueba de restore.

### Medio

16. Revisar `CELERY_SYNC_LIMIT` y timeouts según volumen real de PanAccess.
17. `logrotate` para `logs/` y journals.
18. Fail2ban para ssh y nginx.
19. CAPTCHA en registro si hay abuso.
20. Profiling SQL en endpoints de perfil (`EXPLAIN ANALYZE`).

### Bajo

21. `setproctitle` en workers.
22. Limpiar dependencias ASGI no usadas si se confirma solo WSGI.
23. Documentar desactivación de `/admin/`.
24. Métricas y alertas de negocio (sync lag, fallos PanAccess).

---

## 14. Conclusión

El backend está **cerca de ser desplegable** en Ubuntu nativo gracias a decisiones recientes (seguridad HTTP, CORS, locks, plantillas systemd/nginx, validación de deploy). Los bloqueadores principales no son de “código inexistente”, sino de **consistencia operativa**: versiones de Django, documentación duplicada/obsoleta, endurecimiento de permisos DRF por defecto, política de email en registro, y runbook de backups/monitoreo.

La guía operativa unificada para el equipo de infraestructura está en **`GUIA_DESPLIEGUE_UBUNTU_UNIFICADA.md`**.

---

*Documento generado por auditoría de código y configuración del repositorio serverpanaccess / wind.*

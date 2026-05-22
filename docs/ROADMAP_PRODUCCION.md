# Roadmap producción y rendimiento

Checklist ordenada de **mayor a menor** importancia. Resolver **un ítem a la vez**, probar, marcar como hecho y seguir con el siguiente.

**Cómo usar este archivo**

1. Elige el siguiente ítem sin marcar.
2. Aplica el cambio (código, `.env` o infra).
3. Ejecuta las **pruebas sugeridas** de esa fila.
4. Marca `[x]` en **Estado** y anota fecha/notas si quieres.
5. No saltar P0 sin motivo: los primeros bloquean un deploy seguro.

**Leyenda de prioridad**

| Nivel | Significado |
|-------|-------------|
| **P0** | Bloqueante para producción |
| **P1** | Alto — seguridad o rendimiento serio |
| **P2** | Medio — operación y observabilidad |
| **P3** | Mejora — conviene, no urgente |
| **P4** | Escala futura (p. ej. 5k concurrentes) |

---

## Tabla maestra

| # | Estado | Prioridad | Qué hacer | Por qué | Dónde / notas | Pruebas sugeridas |
|---|--------|-----------|-----------|---------|---------------|-------------------|
| 1 | [x] | **P0** | Activar **PostgreSQL** en Ubuntu (`DB_ENGINE`, migrar; sin Docker) | SQLite no aguanta escrituras concurrentes ni sync masivo | `.env` + **[POSTGRESQL_UBUNTU.md](./POSTGRESQL_UBUNTU.md)** | `python manage.py check_database` → postgresql + ok; `migrate` |
| 2 | [x] | **P0** | **Redis** + `CELERY_TASK_ALWAYS_EAGER=false` + worker `-Q sync_subscribers` + **Beat** | Sin esto no hay sync incremental ni full sync nocturno | **[REDIS_CELERY_UBUNTU.md](./REDIS_CELERY_UBUNTU.md)** + `deploy/systemd/` | `check_redis`; encolar tarea; worker+beat en Ubuntu |
| 3 | [x] | **P0** | Prod: `DEBUG=false`, `SECRET_KEY` fuerte, `ALLOWED_HOSTS` con dominios reales | Seguridad; evitar stack traces públicos | **[SEGURIDAD_PRODUCCION_UBUNTU.md](./SEGURIDAD_PRODUCCION_UBUNTU.md)** | `check_deploy --strict`; Host inválido → 400 |
| 4 | [x] | **P0** | Configurar **`CORS_ALLOWED_ORIGINS`** con el front real | Portal en otro host falla sin esto | **[CORS_PRODUCCION_UBUNTU.md](./CORS_PRODUCCION_UBUNTU.md)** | `check_deploy --strict`; preflight OPTIONS OK |
| 5 | [x] | **P0** | **TLS** (nginx) + no exponer sync/admin a internet abierto | Sync pesado; superficie de ataque | **[NGINX_TLS_Y_RESTRICCION_UBUNTU.md](./NGINX_TLS_Y_RESTRICCION_UBUNTU.md)** + `deploy/nginx/` | HTTPS; sync 403 desde internet |
| 6 | [x] | **P0** | Proteger endpoint sesión PanAccess (ya no en `/wind/login/`) | Sesión de sistema no se filtra al público | `ops/panaccess-session/`, `PANACCESS_OPS_HTTP_ENABLED` | Anónimo → 401/403; portal `/wind/login/` HTML intacto |
| 7 | [x] | **P0** | Endurecer **`create-subscriber/`** (throttle + flag; sin JWT en registro) | Abuso = muchas llamadas PanAccess | **[REGISTRO_PUBLICO_SEGURIDAD.md](./REGISTRO_PUBLICO_SEGURIDAD.md)** | 429 tras límite; `CREATE_SUBSCRIBER_PUBLIC_ENABLED=false` → 403 |
| 8 | [x] | **P1** | Mantener **`FULL_SYNC_HTTP_ENABLED=false`** en prod | Correctivo solo por Celery | **[FULL_SYNC_PRODUCCION.md](./FULL_SYNC_PRODUCCION.md)** | `check_deploy --strict`; POST → 403 |
| 9 | [x] | **P1** | **`PANACCESS_SESSION_USE_REDIS=true`** con varios workers Gunicorn | Evita re-login PanAccess por worker | **[PANACCESS_SESION_REDIS.md](./PANACCESS_SESION_REDIS.md)** | `check_redis` → panaccess_session_store ok |
| 10 | [x] | **P1** | No usar **`/wind/sync-*`** en horario pico; solo emergencias staff | Sync HTTP es **síncrono** en worker web (hasta 600 s) | **[SYNC_HTTP_OPERACION.md](./SYNC_HTTP_OPERACION.md)** | Procedimiento staff documentado |
| 11 | [x] | **P1** | Optimizar **login info en full sync** (no 1 API por suscriptor) | Correctivo nocturno puede tardar horas | **[LOGIN_INFO_SYNC.md](./LOGIN_INFO_SYNC.md)** | `sync_subscribers_login_info`; log `list_api` o `parallel` |
| 12 | [x] | **P1** | Perfil: API PanAccess **por código**, no listar todo el catálogo | `_sync_subscriber_row_from_panaccess` es O(n) | **[PERFIL_PANACCESS.md](./PERFIL_PANACCESS.md)** | `GET /api/v1/profile/me/` → `getSubscriber` en logs |
| 13 | [x] | **P1** | Smartcards en perfil: filtrar por abonado, no paginar todo el mundo | Hasta 15×100 entradas globales | **[PERFIL_SMARTCARDS.md](./PERFIL_SMARTCARDS.md)** | `profile/products` sin escaneo global |
| 14 | [x] | **P1** | Relajar **`SocialConfig.validate()`** (solo proveedores usados) | Arranque exige Google **y** Facebook hoy | `SOCIAL_LOGIN_PROVIDERS` en `.env` | Boot con `SOCIAL_LOGIN_PROVIDERS=google` sin Facebook |
| 15 | [x] | **P1** | Checklist arranque: variables PanAccess completas en prod | `PanaccessConfig.validate()` al importar settings | **[PANACCESS_ARRANQUE.md](./PANACCESS_ARRANQUE.md)** + `check_deploy` | `check_deploy --strict` → PanAccess OK |
| 16 | [x] | **P2** | Activar **systemd** en Ubuntu (plantillas en `deploy/systemd/`) | Servicios reinician solos | **[SYSTEMD_UBUNTU.md](./SYSTEMD_UBUNTU.md)** | `systemctl status` los 3 servicios |
| 17 | [x] | **P2** | Orquestador usa **`GET /ready/`** antes de tráfico | Probe ya implementado | **[HEALTH_READINESS.md](./HEALTH_READINESS.md)** + nginx | LB marca unhealthy si DB/Redis cae |
| 18 | [x] | **P2** | **Sentry** (`SENTRY_DSN`) en staging/prod | Errores nocturnos visibles | **[SENTRY_PRODUCCION.md](./SENTRY_PRODUCCION.md)** + `sentry_test` | `python manage.py sentry_test` |
| 19 | [x] | **P2** | Locust en **staging + PostgreSQL** (perfil, no sync) | Límites reales | **[LOCUST_STAGING.md](./LOCUST_STAGING.md)** | Informe p95 latencia perfil |
| 20 | [x] | **P2** | Revisar **`singleton/`** y **`logged-in/`** (`AllowAny`) | Solo diagnóstico | `wind/functions/` | Staff + `PANACCESS_OPS_HTTP_ENABLED` (hecho con #6) |
| 21 | [x] | **P2** | Actualizar **`ANALISIS_ESCALABILIDAD.md`** (Beat, throttling, caché) | Doc desactualizado | `docs/ANALISIS_ESCALABILIDAD.md` | Alineado con roadmap y sync/perfil |
| 22 | [x] | **P2** | Alertas/logs Celery: `skipped`, duración `full_sync_task` | Saber si correctivo falló | `wind/tasks.py` logs | Log `completada en Xs`; `skipped` en compare/full |
| 23 | [x] | **P3** | `SECURE_*` en Django si TLS no solo en nginx | Defensa en profundidad | **[PRODUCTION_HTTPS.md](./PRODUCTION_HTTPS.md)** + `settings.py` | `PRODUCTION_HTTPS=true`; `check_deploy --strict` |
| 24 | [x] | **P3** | **`DB_REPLICA_HOST`** si lecturas crecen | Descargar carga al primary | **[DB_REPLICA_UBUNTU.md](./DB_REPLICA_UBUNTU.md)** + router | `DATABASES` con `replica` si .env |
| 25 | [x] | **P3** | **`CDN_STATIC_URL`** para estáticos del portal | Menos carga al app | **[CDN_STATIC.md](./CDN_STATIC.md)** | `STATIC_URL` desde CDN |
| 26 | [x] | **P3** | Encolar **sync manual** HTTP vía Celery (como full-sync) | Admin no bloquea Gunicorn | **[SYNC_HTTP_ASYNC.md](./SYNC_HTTP_ASYNC.md)** | POST sync → 202 + `task_id` |
| 27 | [x] | **P3** | Índices extra tras profiling (`SubscriberLoginInfo`, etc.) | Queries lentas puntuales | migración `0002` + **[INDICES_BD.md](./INDICES_BD.md)** | `EXPLAIN` login1/login2 |
| 28 | [x] | **P3** | CI/CD: migrate, tests, deploy web+worker+beat | Menos drift | `.github/workflows/ci.yml` | Pipeline verde en PR |
| 29 | [x] | **P4** | Objetivo **5k concurrentes**: más workers, pool PG, caché perfil | Fuera del diseño actual | **[ESCALA_5000_USUARIOS.md](./ESCALA_5000_USUARIOS.md)** | Locust + fases A/B/C |

---

## Fases resumidas

| Fase | Objetivo | Ítems |
|------|----------|-------|
| **Antes del primer deploy** | Arranque seguro y estable | 1–10 |
| **Primera semana en prod** | Rendimiento y seguridad operativa | 11–15 |
| **Siguiente iteración** | Operación y observabilidad | 16–22 |
| **Con tráfico real** | Pulir y escalar | 23–29 |

---

## Registro de avance (opcional)

| # | Fecha | Responsable | Notas / PR |
|---|-------|-------------|------------|
| 1 | 2026-05-22 | — | Código/docs: `check_database`, `POSTGRESQL_UBUNTU.md`, fix `DB_*` en appConfig. Local: PG ok + migrate. **Pendiente:** repetir en Ubuntu Server según guía. |
| 2 | 2026-05-22 | — | `check_redis`, `REDIS_CELERY_UBUNTU.md`, systemd worker/beat/gunicorn, `.env` Redis/Celery. **Pendiente:** `apt install redis`, servicios en Ubuntu. |
| 3 | 2026-05-22 | — | `check_deploy`, `SEGURIDAD_PRODUCCION_UBUNTU.md`, `PRODUCTION_HTTPS`, `.env` sin `*`. **Pendiente:** dominios reales en Ubuntu + `--strict`. |
| 4 | 2026-05-22 | — | CORS en settings (sin allow-all), `CORS_PRODUCCION_UBUNTU.md`, `check_deploy` valida CORS. **Pendiente:** URLs https del front en Ubuntu. |
| 5 | 2026-05-22 | — | `deploy/nginx/win-backend.conf`, middleware IP, `NGINX_TLS_Y_RESTRICCION_UBUNTU.md`. **Pendiente:** certbot + ufw en Ubuntu. |
| 6 | 2026-05-22 | — | Ruta `ops/panaccess-session/`, staff only, sin `session_id`; fix URL duplicada en `urls.py`. |
| 7 | 2026-05-22 | — | `RegisterThrottle`, `CREATE_SUBSCRIBER_PUBLIC_ENABLED`, nginx limit_req, doc registro. |
| 8 | 2026-05-22 | — | `check_deploy --strict` valida full-sync HTTP; doc `FULL_SYNC_PRODUCCION.md`. |
| 9 | 2026-05-22 | — | `.env` explícito, `check_deploy`/`check_redis` validan sesión Redis; doc. |
| 11 | 2026-05-22 | — | Login info: API listada + paralelo + bulk upsert; `LOGIN_INFO_SYNC.md`. |
| 12 | 2026-05-22 | — | `CallGetSubscriber`; perfil sin listar catálogo extendido. |
| 13 | 2026-05-22 | — | `CallGetSmartcard` + list por abonado; perfil sin 15×100 global. |
| 10 | 2026-05-22 | — | `SYNC_HTTP_OPERACION.md` — sync HTTP solo fuera de pico / emergencias. |
| 14 | 2026-05-22 | — | `SOCIAL_LOGIN_PROVIDERS`; `SocialConfig.validate()` con raise; providers dinámicos en settings. |
| 15 | 2026-05-22 | — | `PANACCESS_ARRANQUE.md`; `check_deploy` valida PanAccess. |
| 22 | 2026-05-22 | — | Log duración `full_sync_task` + `duration_seconds` en resultado. |
| 16–19 | 2026-05-22 | — | Docs systemd, health/ready, Sentry, Locust; `sentry_test`; nginx `/ready/`. |
| 21 | 2026-05-22 | — | `ANALISIS_ESCALABILIDAD.md` actualizado (Beat, sync HTTP, perfil). |
| 23 | 2026-05-22 | — | Doc `PRODUCTION_HTTPS.md`; `check_deploy --strict` exige flag en prod. |
| 26 | 2026-05-22 | — | `SYNC_HTTP_ASYNC`, `sync_products_task`, POST sync → 202 + `status_url`. |
| — | 2026-05-22 | — | [DEPLOY_UBUNTU_CHECKLIST.md](./DEPLOY_UBUNTU_CHECKLIST.md) checklist único deploy. |
| 28 | 2026-05-22 | — | GitHub Actions: check, test, check_redis; `wind/tests/`. |
| 24–25 | 2026-05-22 | — | Docs réplica y CDN; código ya existía en settings/router. |
| 27 | 2026-05-22 | — | Índices `SubscriberLoginInfo`; migración `0002_subscriberlogininfo_indexes`. |
| 29 | 2026-05-22 | — | Guía arquitectura 5k usuarios. |

---

## Referencias

- [POSTGRESQL_UBUNTU.md](./POSTGRESQL_UBUNTU.md) — ítem **#1** (PostgreSQL nativo en Ubuntu)
- [REDIS_CELERY_UBUNTU.md](./REDIS_CELERY_UBUNTU.md) — ítem **#2** (Redis + Celery + systemd)
- [SEGURIDAD_PRODUCCION_UBUNTU.md](./SEGURIDAD_PRODUCCION_UBUNTU.md) — ítem **#3** (DEBUG, SECRET_KEY, ALLOWED_HOSTS)
- [CORS_PRODUCCION_UBUNTU.md](./CORS_PRODUCCION_UBUNTU.md) — ítem **#4** (orígenes del frontend)
- [NGINX_TLS_Y_RESTRICCION_UBUNTU.md](./NGINX_TLS_Y_RESTRICCION_UBUNTU.md) — ítem **#5** (TLS + bloqueo sync público)
- [REGISTRO_PUBLICO_SEGURIDAD.md](./REGISTRO_PUBLICO_SEGURIDAD.md) — ítem **#7** (create-subscriber)
- [FULL_SYNC_PRODUCCION.md](./FULL_SYNC_PRODUCCION.md) — ítem **#8** (full-sync solo Celery)
- [PANACCESS_SESION_REDIS.md](./PANACCESS_SESION_REDIS.md) — ítem **#9** (sesión PanAccess multi-worker)
- [SYNC_FLUJO_TAREAS.md](./SYNC_FLUJO_TAREAS.md) — flujo deploy / Beat / full-sync
- [LOGIN_INFO_SYNC.md](./LOGIN_INFO_SYNC.md) — ítem **#11** (login info en full-sync)
- [PERFIL_PANACCESS.md](./PERFIL_PANACCESS.md) — ítem **#12** (profile/me por código)
- [PERFIL_SMARTCARDS.md](./PERFIL_SMARTCARDS.md) — ítem **#13** (profile/products por abonado)
- [SYNC_HTTP_OPERACION.md](./SYNC_HTTP_OPERACION.md) — ítem **#10** (sync HTTP fuera de pico)
- [PANACCESS_ARRANQUE.md](./PANACCESS_ARRANQUE.md) — ítem **#15** (variables PanAccess al arrancar)
- [SYSTEMD_UBUNTU.md](./SYSTEMD_UBUNTU.md) — ítem **#16**
- [HEALTH_READINESS.md](./HEALTH_READINESS.md) — ítem **#17**
- [SENTRY_PRODUCCION.md](./SENTRY_PRODUCCION.md) — ítem **#18**
- [LOCUST_STAGING.md](./LOCUST_STAGING.md) — ítem **#19**
- [DEPLOY_UBUNTU_CHECKLIST.md](./DEPLOY_UBUNTU_CHECKLIST.md) — checklist único primer deploy
- [PRODUCTION_HTTPS.md](./PRODUCTION_HTTPS.md) — ítem **#23**
- [SYNC_HTTP_ASYNC.md](./SYNC_HTTP_ASYNC.md) — ítem **#26**
- [CI_CD.md](./CI_CD.md) — ítem **#28** (GitHub Actions)
- [DB_REPLICA_UBUNTU.md](./DB_REPLICA_UBUNTU.md) — ítem **#24**
- [CDN_STATIC.md](./CDN_STATIC.md) — ítem **#25**
- [INDICES_BD.md](./INDICES_BD.md) — ítem **#27**
- [ESCALA_5000_USUARIOS.md](./ESCALA_5000_USUARIOS.md) — ítem **#29**
- [DESPLIEGUE.md](./DESPLIEGUE.md) — comandos worker, beat, variables `.env`
- [ANALISIS_ESCALABILIDAD.md](./ANALISIS_ESCALABILIDAD.md) — contexto de carga (revisar tras ítem 21)

**Nota:** el despliegue es **solo Ubuntu Server** — PostgreSQL, Redis, Gunicorn y Celery instalados en el sistema (`apt` + `systemd`). **No hay Docker** en este proyecto.

# Checklist único — primer deploy en Ubuntu

Sin Docker. Marca cada paso al completarlo en el servidor.

## A. Sistema

- [ ] Ubuntu actualizado; usuario deploy con sudo
- [ ] `python3.12`, `venv`, `git`, `nginx`, `postgresql`, `redis-server`
- [ ] Código en `/opt/win-backend` + venv + `pip install -r requirements.txt`

## B. Base de datos

- [ ] Rol y BD creados — [POSTGRESQL_UBUNTU.md](./POSTGRESQL_UBUNTU.md)
- [ ] `.env`: `DB_ENGINE=django.db.backends.postgresql` + `DB_*`
- [ ] `python manage.py migrate`
- [ ] `python manage.py check_database` → OK

## C. Configuración `.env` producción

- [ ] `DEBUG=false`, `SECRET_KEY` fuerte (≥50 chars)
- [ ] `ALLOWED_HOSTS=api.tudominio.com,...`
- [ ] `CORS_ALLOWED_ORIGINS=https://app.tudominio.com`
- [ ] `PRODUCTION_HTTPS=true` — [PRODUCTION_HTTPS.md](./PRODUCTION_HTTPS.md)
- [ ] PanAccess completo — [PANACCESS_ARRANQUE.md](./PANACCESS_ARRANQUE.md)
- [ ] `PANACCESS_SESSION_USE_REDIS=true`
- [ ] `CELERY_TASK_ALWAYS_EAGER=false`
- [ ] `FULL_SYNC_HTTP_ENABLED=false`
- [ ] `SYNC_HTTP_ASYNC=true`
- [ ] `SOCIAL_LOGIN_PROVIDERS=google,facebook` (o los que uses)
- [ ] Opcional: `SENTRY_DSN=...`

## D. Validación pre-arranque

```bash
python manage.py check_deploy --strict
python manage.py check_redis
```

- [ ] Sin errores en `--strict`

## E. Servicios systemd

- [ ] `win-gunicorn`, `win-celery-worker`, `win-celery-beat` — [SYSTEMD_UBUNTU.md](./SYSTEMD_UBUNTU.md)
- [ ] `systemctl status` → los 3 **active**
- [ ] `curl -s http://127.0.0.1:8000/ready/` → `{"ready": true}`

## F. nginx + TLS

- [ ] Plantilla `deploy/nginx/win-backend.conf` — [NGINX_TLS_Y_RESTRICCION_UBUNTU.md](./NGINX_TLS_Y_RESTRICCION_UBUNTU.md)
- [ ] `certbot` OK; HTTPS público
- [ ] Sync bloqueado desde internet; VPN/localhost para staff

## G. Sync inicial (una vez, staff JWT)

- [ ] Worker Celery corriendo
- [ ] `POST /wind/sync-subscribers/` → **202** + `task_id`
- [ ] `POST /wind/sync-products/` → **202**
- [ ] `POST /wind/sync-smartcards/` → **202**
- [ ] Verificar en `GET /api/v1/tasks/<id>/` — [SYNC_HTTP_ASYNC.md](./SYNC_HTTP_ASYNC.md)

## H. Beat y correctivo

- [ ] Beat programa compare 10 min + full-sync 00:00 — [SYNC_FLUJO_TAREAS.md](./SYNC_FLUJO_TAREAS.md)
- [ ] Logs: `compare_and_update_*` sin errores repetidos

## I. Observabilidad

- [ ] `python manage.py sentry_test` (si hay DSN)
- [ ] Locust en staging — [LOCUST_STAGING.md](./LOCUST_STAGING.md)

## J. Portal

- [ ] `https://api.tudominio.com/wind/login/` carga
- [ ] Login usuario / social OK
- [ ] Front apunta al API con CORS correcto

---

**Roadmap completo:** [ROADMAP_PRODUCCION.md](./ROADMAP_PRODUCCION.md)

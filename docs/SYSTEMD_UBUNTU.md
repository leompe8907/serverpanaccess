# systemd en Ubuntu (roadmap #16)

Servicios para que Gunicorn, Celery worker y Celery beat **reinicien solos** tras un fallo o reboot.

Plantillas: `deploy/systemd/`

## Requisitos previos

- Código en `/opt/win-backend` (o ajusta rutas en los `.service`)
- venv en `/opt/win-backend/env`
- `.env` en `/opt/win-backend/.env`
- PostgreSQL y Redis activos ([POSTGRESQL_UBUNTU.md](./POSTGRESQL_UBUNTU.md), [REDIS_CELERY_UBUNTU.md](./REDIS_CELERY_UBUNTU.md))

## 1. Usuario del servicio

```bash
sudo useradd -r -s /bin/false www-data 2>/dev/null || true
sudo chown -R www-data:www-data /opt/win-backend
```

O usa tu usuario de deploy y cambia `User=` / `Group=` en cada unidad.

## 2. Instalar unidades

```bash
cd /opt/win-backend
sudo cp deploy/systemd/win-gunicorn.service /etc/systemd/system/
sudo cp deploy/systemd/win-celery-worker.service /etc/systemd/system/
sudo cp deploy/systemd/win-celery-beat.service /etc/systemd/system/
```

Edita las tres si tu ruta no es `/opt/win-backend`:

```bash
sudo nano /etc/systemd/system/win-gunicorn.service
# WorkingDirectory, EnvironmentFile, ExecStart → ruta real al venv
```

## 3. Habilitar y arrancar

```bash
sudo systemctl daemon-reload
sudo systemctl enable win-gunicorn win-celery-worker win-celery-beat
sudo systemctl start win-gunicorn win-celery-worker win-celery-beat
```

## 4. Comprobar (prueba roadmap #16)

```bash
sudo systemctl status win-gunicorn
sudo systemctl status win-celery-worker
sudo systemctl status win-celery-beat
```

Los tres deben estar **active (running)**.

```bash
curl -s http://127.0.0.1:8000/ready/
# {"ready": true}
```

## 5. Logs

```bash
journalctl -u win-gunicorn -f
journalctl -u win-celery-worker -f
journalctl -u win-celery-beat -f
```

## Orden de arranque recomendado

1. `postgresql`, `redis-server`
2. `python manage.py migrate`
3. `win-gunicorn`
4. `win-celery-worker` (cola `sync_subscribers`)
5. `win-celery-beat`
6. nginx (TLS público)

## Dependencias en las unidades

| Servicio | After |
|----------|--------|
| Gunicorn | `postgresql`, `redis-server` |
| Celery worker / beat | `redis-server`, `postgresql` |

## Tras actualizar código

```bash
sudo systemctl restart win-gunicorn win-celery-worker win-celery-beat
```

Si solo cambias `.env`, basta con `restart` de los tres.

## Referencias

- [REDIS_CELERY_UBUNTU.md](./REDIS_CELERY_UBUNTU.md) — worker `-Q sync_subscribers`
- [DESPLIEGUE.md](./DESPLIEGUE.md)
- [HEALTH_READINESS.md](./HEALTH_READINESS.md) — probes `/ready/`

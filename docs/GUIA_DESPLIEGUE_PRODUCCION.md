# 🚀 Guía de Despliegue Definitiva — Producción (Ubuntu 22.04)
## Proyecto: serverpanaccess

> **Reemplazada por:** **[GUIA_DESPLIEGUE_UBUNTU_UNIFICADA.md](./GUIA_DESPLIEGUE_UBUNTU_UNIFICADA.md)** (SSH, PostgreSQL, Redis, systemd, nginx, logs, sync inicial).

Esta guía unifica la lógica de negocio de **serverpanaccess** (Celery, Panaccess, Django) con una infraestructura de nivel empresarial (Hardening de Nginx, Gunicorn optimizado, Fail2Ban y Monitoreo).

---

## 📋 Especificaciones de Producción (1k - 10k Usuarios)
*   **SO:** Ubuntu 22.04 LTS (Host puro, sin Docker).
*   **Web Server:** Nginx (Proxy Reverso + Rate Limiting).
*   **App Server:** Gunicorn (con workers tipo gthread o uvicorn).
*   **Tareas:** Celery + Celery Beat (Sincronización Panaccess).
*   **Base de Datos:** PostgreSQL 14+.
*   **Cache/Broker:** Redis 6+.

---

## 1. Preparación del Sistema y Seguridad Inicial

```bash
# Actualizar y dependencias básicas
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv nginx redis-server postgresql postgresql-contrib libpq-dev curl git fail2ban certbot python3-certbot-nginx

# Configurar Firewall (UFW)
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

---

## 2. Base de Datos y Redis

### PostgreSQL
```bash
sudo -u postgres psql
# En la consola psql:
CREATE DATABASE wind;
CREATE USER winduser WITH PASSWORD 'TU_PASSWORD_SEGURA';
ALTER ROLE winduser SET client_encoding TO 'utf8';
ALTER ROLE winduser SET default_transaction_isolation TO 'read committed';
ALTER ROLE winduser SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE wind TO winduser;
\q
```

### Redis (Optimización para alta carga)
```bash
sudo nano /etc/redis/redis.conf
# Cambiar:
# maxmemory 512mb
# maxmemory-policy allkeys-lru
sudo systemctl restart redis-server
```

---

## 3. Instalación de la Aplicación

```bash
# Crear usuario de sistema para la app
sudo adduser --system --group --home /var/www/backend windapp
sudo mkdir -p /var/www/backend
sudo chown windapp:windapp /var/www/backend

# Cambiar al usuario y clonar
sudo su - windapp
git clone <URL_REPOSITORIO> .

# Entorno virtual y dependencias
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# Importante: usar psycopg (no binary) para producción
pip install gunicorn setproctitle psycopg
```

---

## 4. Configuración del Entorno (`.env`)
Crea el archivo `.env` en `/var/www/backend/.env` con las variables de `appConfig.py`:

```env
DEBUG=false
SECRET_KEY=usa_un_token_largo_aqui
ALLOWED_HOSTS=api.tudominio.com
CORS_ALLOWED_ORIGINS=https://app.tudominio.com

# Base de Datos
DB_ENGINE=django.db.backends.postgresql
DB_NAME=wind
DB_USER=winduser
DB_PASSWORD=TU_PASSWORD_SEGURA
DB_HOST=localhost
DB_PORT=5432
DB_CONN_MAX_AGE=600

# Redis / Celery
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
REDIS_CACHE_DB=1
PANACCESS_SESSION_USE_REDIS=true

# Seguridad
PRODUCTION_HTTPS=true

# Panaccess
url_panaccess=...
username=...
password=...
api_token=...
salt=...
hcId=...
ENCRYPTION_KEY=...
```

---

## 5. Preparación de Django
```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check_deploy --strict
```

---

## 6. Servidor de Aplicación (Gunicorn)
Crea `/var/www/backend/gunicorn_conf.py`:
```python
import multiprocessing
bind = "unix:/run/gunicorn.sock"
workers = multiprocessing.cpu_count() * 2 + 1
threads = 4
worker_class = "gthread"
worker_connections = 2000
timeout = 300
keepalive = 2
max_requests = 1000
max_requests_jitter = 50
accesslog = "/var/www/backend/logs/gunicorn_access.log"
errorlog = "/var/www/backend/logs/gunicorn_error.log"
```

Crea el servicio: `sudo nano /etc/systemd/system/gunicorn.service`
```ini
[Unit]
Description=gunicorn daemon para serverpanaccess
After=network.target

[Service]
User=windapp
Group=www-data
WorkingDirectory=/var/www/backend
ExecStart=/var/www/backend/venv/bin/gunicorn --config gunicorn_conf.py serverpanaccess.wsgi:application

[Install]
WantedBy=multi-user.target
```

---

## 7. Tareas Asíncronas (Celery)
### Worker: `sudo nano /etc/systemd/system/celery.service`
```ini
[Service]
User=windapp
Group=windapp
WorkingDirectory=/var/www/backend
EnvironmentFile=/var/www/backend/.env
ExecStart=/var/www/backend/venv/bin/celery -A serverpanaccess worker --loglevel=INFO -Q sync_subscribers,celery
Restart=always
```

### Beat: `sudo nano /etc/systemd/system/celerybeat.service`
```ini
[Service]
User=windapp
Group=windapp
WorkingDirectory=/var/www/backend
EnvironmentFile=/var/www/backend/.env
ExecStart=/var/www/backend/venv/bin/celery -A serverpanaccess beat --loglevel=INFO
Restart=always
```

---

## 8. Proxy Reverso (Nginx Hardening)
`sudo nano /etc/nginx/sites-available/serverpanaccess`

```nginx
# Rate Limiting
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

server {
    listen 80;
    server_name api.tudominio.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.tudominio.com;

    ssl_certificate /etc/letsencrypt/live/api.tudominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.tudominio.com/privkey.pem;

    # Headers de Seguridad
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    location /static/ {
        alias /var/www/backend/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    location / {
        limit_req zone=api_limit burst=20 nodelay;
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn.sock;
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }
}
```

---

## 9. Monitoreo Proactivo
Crea un script de salud en `/var/www/backend/monitor_health.sh`:
```bash
#!/bin/bash
echo "--- STATUS REPORT ---"
systemctl is-active gunicorn
systemctl is-active celery
systemctl is-active celerybeat
redis-cli ping
free -h
df -h
```
Hacerlo ejecutable: `chmod +x /var/www/backend/monitor_health.sh`

---

## 10. Checklist Final Post-Despliegue
1. [ ] **SSL:** `sudo certbot --nginx -d api.tudominio.com`
2. [ ] **Logs:** Revisar `/var/www/backend/logs/` para asegurar que el singleton Panaccess inició sesión.
3. [ ] **Fail2Ban:** `sudo systemctl enable fail2ban && sudo systemctl start fail2ban`
4. [ ] **Beat:** Verificar que las tareas de `compare_and_update` se están encolando en Redis.
5. [ ] **Admin IP:** Si usas `SYNC_ADMIN_IP_ALLOWLIST`, verifica que tu IP tenga acceso a `/wind/singleton/`.

---
**Guía Definitiva Unificada** | 2026 | serverpanaccess

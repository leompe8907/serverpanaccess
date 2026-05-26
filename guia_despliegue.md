# Guía de Despliegue — Django Backend (Ubuntu 22.04)

> **Obsoleta parcialmente.** Usa la guía canónica: **[GUIA_DESPLIEGUE_UBUNTU_UNIFICADA.md](./GUIA_DESPLIEGUE_UBUNTU_UNIFICADA.md)** y las plantillas en `deploy/`.

Esta guía detalla los pasos para desplegar el proyecto en un servidor Ubuntu 22.04 LTS puro, sin Docker, utilizando Nginx, Gunicorn, PostgreSQL y Celery/Redis.

## 1. Preparación del Sistema
```bash
# Actualizar el sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependencias esenciales
sudo apt install -y python3-pip python3-venv nginx redis-server postgresql postgresql-contrib libpq-dev curl git
```

## 2. Seguridad Inicial (UFW)
```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

## 3. Configuración de PostgreSQL
```bash
# Entrar como usuario postgres
sudo -u postgres psql

# Ejecutar dentro de psql (cambia 'tu_password_seguro')
CREATE DATABASE wind;
CREATE USER winduser WITH PASSWORD 'tu_password_seguro';
ALTER ROLE winduser SET client_encoding TO 'utf8';
ALTER ROLE winduser SET default_transaction_isolation TO 'read committed';
ALTER ROLE winduser SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE wind TO winduser;
\q
```

## 4. Clonado y Entorno Virtual
```bash
# Crear directorio de la app
sudo mkdir -p /var/www/backend
sudo chown $USER:$USER /var/www/backend
cd /var/www/backend

# Clonar el proyecto
git clone <URL_DEL_REPOSITORIO> .

# Crear y activar entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias (asegúrate de corregir Django en requirements.txt primero)
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn setproctitle psycopg
```

## 5. Configuración de Variables de Entorno
Crea el archivo `.env` basado en `.env.example`:
```bash
cp .env.example .env
nano .env
```
**Campos obligatorios para completar:**
- `SECRET_KEY`: Genera una nueva con `python3 -c 'import secrets; print(secrets.token_hex(32))'`
- `DEBUG=false`
- `ALLOWED_HOSTS=api.tudominio.com`
- `DB_ENGINE=django.db.backends.postgresql`
- `DB_NAME=wind`
- `DB_USER=winduser`
- `DB_PASSWORD=tu_password_seguro`
- `DB_HOST=localhost`
- `DB_PORT=5432`
- `PRODUCTION_HTTPS=true`
- Datos de PanAccess y Social Auth (Google/Facebook).

## 6. Preparación de Django
```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

## 7. Gunicorn (systemd)
Crea el archivo de servicio: `sudo nano /etc/systemd/system/gunicorn.service`
```ini
[Unit]
Description=gunicorn daemon
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/var/www/backend
ExecStart=/var/www/backend/venv/bin/gunicorn \
          --access-logfile - \
          --workers 3 \
          --bind unix:/run/gunicorn.sock \
          serverpanaccess.wsgi:application

[Install]
WantedBy=multi-user.target
```

## 8. Celery y Celery Beat (systemd)
### Worker: `sudo nano /etc/systemd/system/celery.service`
```ini
[Unit]
Description=Celery Service
After=network.target redis-server.service

[Service]
Type=forking
User=ubuntu
Group=ubuntu
EnvironmentFile=/var/www/backend/.env
WorkingDirectory=/var/www/backend
ExecStart=/var/www/backend/venv/bin/celery -A serverpanaccess multi start worker \
    --pidfile=/var/run/celery/%n.pid \
    --logfile=/var/www/backend/logs/celery.log --loglevel=INFO \
    -Q sync_subscribers,celery
ExecStop=/var/www/backend/venv/bin/celery multi stopwait worker --pidfile=/var/run/celery/%n.pid
ExecReload=/var/www/backend/venv/bin/celery multi restart worker --pidfile=/var/run/celery/%n.pid

[Install]
WantedBy=multi-user.target
```

### Beat: `sudo nano /etc/systemd/system/celerybeat.service`
```ini
[Unit]
Description=Celery Beat Service
After=network.target redis-server.service

[Service]
User=ubuntu
Group=ubuntu
EnvironmentFile=/var/www/backend/.env
WorkingDirectory=/var/www/backend
ExecStart=/var/www/backend/venv/bin/celery -A serverpanaccess beat \
    --pidfile=/var/run/celery/beat.pid \
    --logfile=/var/www/backend/logs/beat.log --loglevel=INFO

[Install]
WantedBy=multi-user.target
```
*Nota: Crea el directorio para PIDs:* `sudo mkdir /var/run/celery && sudo chown ubuntu:ubuntu /var/run/celery`

## 9. Nginx como Proxy Reverso
`sudo nano /etc/nginx/sites-available/backend`
```nginx
server {
    listen 80;
    server_name api.tudominio.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /var/www/backend;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn.sock;
    }
}
```
Activa el sitio:
```bash
sudo ln -s /etc/nginx/sites-available/backend /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

## 10. Certificado SSL (Certbot)
```bash
sudo apt install -y python3-certbot-nginx
sudo certbot --nginx -d api.tudominio.com
```

## 11. Activación de Servicios
```bash
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
sudo systemctl start celery
sudo systemctl enable celery
sudo systemctl start celerybeat
sudo systemctl enable celerybeat
```

## 12. Monitoreo y Troubleshooting
- **Logs de Gunicorn:** `sudo journalctl -u gunicorn`
- **Logs de Celery:** `tail -f /var/www/backend/logs/celery.log`
- **Status Redis:** `redis-cli ping` (debe responder PONG)
- **Status DB:** `sudo -u postgres psql -c "SELECT 1;"`

# Guía unificada de despliegue — Ubuntu Server (sin Docker)

**Proyecto:** serverpanaccess (backend Django + PanAccess)  
**Entorno objetivo:** Ubuntu 22.04 LTS o 24.04 LTS, servidor dedicado o VPS  
**Método:** instalación nativa (Python venv, PostgreSQL, Redis, Nginx, systemd)

Esta guía **reemplaza y consolida** los siguientes documentos, que quedan como referencia histórica o parcial:

| Documento | Veredicto |
|-----------|-----------|
| `GUIA_DESPLIEGUE_UBUNTU_UNIFICADA.md` (este) | **Canónica** |
| `docs/DEPLOY_UBUNTU_CHECKLIST.md` | Checklist resumido — seguir en paralelo |
| `docs/POSTGRESQL_UBUNTU.md`, `REDIS_CELERY_UBUNTU.md`, `SYSTEMD_UBUNTU.md`, `NGINX_TLS_Y_RESTRICCION_UBUNTU.md` | Detalle modular — enlazados aquí |
| `deploy/systemd/*.service`, `deploy/nginx/win-backend.conf` | **Fuente de verdad** para unidades y nginx |
| `guia_despliegue.md` | Obsoleta parcialmente (`celery multi`, rutas `/var/www/backend`) |
| `GUIA_DESPLIEGUE_PRODUCCION.md` | Duplicada; mezcla rutas `windapp` y `/var/www/backend` |
| `docs/GUIA_DESPLIEGUE_SERVIDOR_PRIVADO.md` | **No usar** — describe otro proyecto (UDID/WebSockets) |
| `docs/DESPLIEGUE.md` | Comandos dev + enlaces — no sustituye esta guía |

---

## Tabla de contenidos

1. [Arquitectura en producción](#1-arquitectura-en-producción)
2. [Requisitos del servidor](#2-requisitos-del-servidor)
3. [Acceso SSH y hardening](#3-acceso-ssh-y-hardening)
4. [Preparación del sistema](#4-preparación-del-sistema)
5. [PostgreSQL](#5-postgresql)
6. [Redis](#6-redis)
7. [Usuario de aplicación y código](#7-usuario-de-aplicación-y-código)
8. [Entorno virtual y dependencias](#8-entorno-virtual-y-dependencias)
9. [Variables de entorno (.env)](#9-variables-de-entorno-env)
10. [Django: migrate, estáticos, validación](#10-django-migrate-estáticos-validación)
11. [systemd: Gunicorn, Celery worker, Celery beat](#11-systemd-gunicorn-celery-worker-celery-beat)
12. [Nginx, TLS y restricción de rutas](#12-nginx-tls-y-restricción-de-rutas)
13. [Sincronización inicial con PanAccess](#13-sincronización-inicial-con-panaccess)
14. [Logs, logrotate y monitoreo](#14-logs-logrotate-y-monitoreo)
15. [Actualizaciones y rollback](#15-actualizaciones-y-rollback)
16. [Solución de problemas](#16-solución-de-problemas)
17. [Checklist final](#17-checklist-final)

---

## 1. Arquitectura en producción

```text
Internet
    │
    ▼
┌─────────────┐     unix/TCP      ┌──────────────┐
│   Nginx     │ ───────────────► │   Gunicorn   │  Django WSGI
│  :443 TLS   │                  │  :8000/local │
└─────────────┘                  └──────┬───────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
             ┌────────────┐      ┌────────────┐      ┌────────────┐
             │ PostgreSQL │      │ Redis DB0  │      │ Redis DB1  │
             │   :5432    │      │ Celery/lock│      │   Caché    │
             └────────────┘      └─────┬──────┘      └────────────┘
                                       │
                              ┌────────┴────────┐
                              ▼                 ▼
                       Celery Worker       Celery Beat
                       -Q sync_subscribers  (cron interno)
```

**Puertos que deben estar abiertos al público:** 80 (redirect), 443 (HTTPS).  
**Solo localhost:** 5432 (PostgreSQL), 6379 (Redis), 8000 (Gunicorn si nginx hace proxy local).

---

## 2. Requisitos del servidor

| Recurso | Mínimo | Recomendado (1k–10k usuarios portal) |
|---------|--------|--------------------------------------|
| CPU | 2 vCPU | 4–8 vCPU |
| RAM | 4 GB | 8–16 GB |
| Disco | 40 GB SSD | 100+ GB SSD |
| SO | Ubuntu 22.04 LTS | Ubuntu 22.04 / 24.04 LTS |

**Software:**

- Python 3.11+ (3.12 en Ubuntu 24.04 está bien; **no** hace falta PPA deadsnakes salvo versión muy específica)
- PostgreSQL 14+
- Redis 6+
- Nginx
- Git
- Certbot (Let's Encrypt)

---

## 3. Acceso SSH y hardening

### 3.1 Primer acceso (desde tu PC)

```bash
ssh usuario@IP_DEL_SERVIDOR
```

Crea un usuario de despliegue con sudo (si solo existe `root`):

```bash
sudo adduser deploy
sudo usermod -aG sudo deploy
```

Copia tu clave pública (en tu PC):

```bash
ssh-copy-id deploy@IP_DEL_SERVIDOR
```

### 3.2 Endurecer OpenSSH

Edita `/etc/ssh/sshd_config` (como root o con sudo):

```bash
sudo nano /etc/ssh/sshd_config
```

Valores recomendados:

```text
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
```

Aplica cambios:

```bash
sudo systemctl reload sshd
```

**Importante:** mantén una sesión SSH abierta mientras pruebas en otra terminal:

```bash
ssh deploy@IP_DEL_SERVIDOR
```

### 3.3 Firewall (UFW)

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status verbose
```

### 3.4 Fail2Ban (opcional, recomendado)

```bash
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 3.5 Actualizaciones automáticas de seguridad

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

## 4. Preparación del sistema

Conéctate como `deploy` (o tu usuario con sudo):

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
  python3 python3-venv python3-dev python3-pip \
  build-essential libpq-dev \
  nginx redis-server \
  postgresql postgresql-contrib \
  git curl certbot python3-certbot-nginx \
  fail2ban
```

Verifica versiones:

```bash
python3 --version
psql --version
redis-server --version
nginx -v
```

---

## 5. PostgreSQL

### 5.1 Crear rol y base de datos

Sustituye `TU_PASSWORD_SEGURO` por una contraseña larga (gestor de secretos).

```bash
sudo -u postgres psql <<'EOF'
CREATE USER wind WITH PASSWORD 'TU_PASSWORD_SEGURO';
CREATE DATABASE wind OWNER wind;
GRANT ALL PRIVILEGES ON DATABASE wind TO wind;
\c wind
GRANT ALL ON SCHEMA public TO wind;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO wind;
EOF
```

### 5.2 Solo conexiones locales (recomendado)

En `/etc/postgresql/*/main/pg_hba.conf` debe existir una línea similar a:

```text
host    all    all    127.0.0.1/32    scram-sha-256
```

No expongas el puerto 5432 a internet salvo réplica en red privada ([DB_REPLICA_UBUNTU.md](docs/DB_REPLICA_UBUNTU.md)).

```bash
sudo systemctl reload postgresql
```

### 5.3 Variables en `.env` (más adelante)

```env
DB_ENGINE=django.db.backends.postgresql
DB_NAME=wind
DB_USER=wind
DB_PASSWORD=TU_PASSWORD_SEGURO
DB_HOST=127.0.0.1
DB_PORT=5432
DB_CONN_MAX_AGE=600
```

### 5.4 Comprobar desde Django (tras instalar app)

```bash
python manage.py check_database
python manage.py migrate
```

### 5.5 Backup (obligatorio en producción)

Cron diario ejemplo (`sudo crontab -e` como root o usuario postgres):

```cron
0 3 * * * postgres pg_dump -Fc wind > /var/backups/postgresql/wind_$(date +\%Y\%m\%d).dump
```

Crea el directorio y permisos:

```bash
sudo mkdir -p /var/backups/postgresql
sudo chown postgres:postgres /var/backups/postgresql
```

Más detalle: [POSTGRESQL_UBUNTU.md](docs/POSTGRESQL_UBUNTU.md).

---

## 6. Redis

### 6.1 Instalación y arranque

```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server
redis-cli ping
# PONG
```

### 6.2 Ajustes recomendados

```bash
sudo nano /etc/redis/redis.conf
```

```text
bind 127.0.0.1 ::1
supervised systemd
maxmemory 512mb
maxmemory-policy allkeys-lru
```

Si defines contraseña:

```text
requirepass TU_PASSWORD_REDIS
```

Y en `.env`:

```env
REDIS_PASSWORD=TU_PASSWORD_REDIS
```

Reinicia:

```bash
sudo systemctl restart redis-server
```

### 6.3 Uso en el proyecto

| Variable | Default | Uso |
|----------|---------|-----|
| `REDIS_DB` | 0 | Broker Celery, locks, sesión PanAccess |
| `REDIS_CACHE_DB` | 1 | Caché Django |

Más detalle: [REDIS_CELERY_UBUNTU.md](docs/REDIS_CELERY_UBUNTU.md).

---

## 7. Usuario de aplicación y código

### 7.1 Directorio estándar

Se recomienda **`/opt/win-backend`** (coincide con plantillas en `deploy/`).

```bash
sudo mkdir -p /opt/win-backend
sudo chown deploy:deploy /opt/win-backend   # o www-data según política
cd /opt/win-backend
```

### 7.2 Clonar repositorio

```bash
git clone https://github.com/TU_ORG/TU_REPO.git .
# o git pull en despliegues posteriores
```

### 7.3 Permisos para servicios

Si los servicios corren como `www-data`:

```bash
sudo chown -R www-data:www-data /opt/win-backend
sudo chmod 750 /opt/win-backend
sudo chmod 640 /opt/win-backend/.env
```

El usuario `deploy` puede ser dueño del código y `www-data` solo lectura/ejecución según tu política.

---

## 8. Entorno virtual y dependencias

```bash
cd /opt/win-backend
python3 -m venv env
source env/bin/activate
pip install --upgrade pip wheel
pip install -r requirements.txt
pip install --force-reinstall 'psycopg[c]>=3.2'
```

Ver [PYTHON_DEPENDENCIAS.md](docs/PYTHON_DEPENDENCIAS.md) (Django 5.2.14 LTS, `requirements-dev.txt` para Locust).

**Verificar Django instalado:**

```bash
python -c "import django; print(django.get_version())"
python manage.py check
```

---

## 9. Variables de entorno (.env)

```bash
cp .env.example .env
nano .env
chmod 600 .env
```

### 9.1 Plantilla mínima de producción

```env
# --- Django ---
DEBUG=false
SECRET_KEY=GENERA_CON_python3_-c_import_secrets_print_secrets_token_hex_32
ALLOWED_HOSTS=api.tudominio.com
CORS_ALLOWED_ORIGINS=https://app.tudominio.com
PRODUCTION_HTTPS=true

# --- PostgreSQL ---
DB_ENGINE=django.db.backends.postgresql
DB_NAME=wind
DB_USER=wind
DB_PASSWORD=TU_PASSWORD_SEGURO
DB_HOST=127.0.0.1
DB_PORT=5432
DB_CONN_MAX_AGE=600

# --- Redis / Celery ---
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
REDIS_CACHE_DB=1
CELERY_TASK_ALWAYS_EAGER=false
CELERY_SYNC_MINUTES=10
CELERY_SMARTCARD_SYNC_MINUTES=10
CELERY_SYNC_LIMIT=200
CELERY_SYNC_QUEUE=sync_subscribers
CELERY_FULL_SYNC_ENABLED=true
CELERY_FULL_SYNC_HOUR=0
CELERY_FULL_SYNC_MINUTE=0

# --- PanAccess ---
url_panaccess=https://...
username=...
password=...
api_token=...
salt=...
hcId=...
ENCRYPTION_KEY=...

# --- Sesión PanAccess multi-worker ---
PANACCESS_SESSION_USE_REDIS=true
PANACCESS_SESSION_TTL_SECONDS=1500
PANACCESS_CIRCUIT_BREAKER_ENABLED=true

# --- Sync / seguridad operativa ---
SYNC_HTTP_ASYNC=true
FULL_SYNC_HTTP_ENABLED=false
SYNC_ADMIN_IP_ALLOWLIST=127.0.0.1,TU_IP_OFICINA
CREATE_SUBSCRIBER_PUBLIC_ENABLED=true

# --- Social login ---
SOCIAL_LOGIN_PROVIDERS=google,facebook
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=https://app.tudominio.com/...
FACEBOOK_APP_ID=...
FACEBOOK_APP_SECRET=...
FACEBOOK_REDIRECT_URI=...

# --- Observabilidad (opcional) ---
SENTRY_DSN=https://...
SENTRY_ENVIRONMENT=production
```

Generar `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Referencia completa: `.env.example` y [SEGURIDAD_PRODUCCION_UBUNTU.md](docs/SEGURIDAD_PRODUCCION_UBUNTU.md).

---

## 10. Django: migrate, estáticos, validación

```bash
cd /opt/win-backend
source env/bin/activate

mkdir -p logs
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check_deploy --strict
python manage.py check_redis
```

Si `check_deploy --strict` falla, **no** arranques Gunicorn hasta corregir `.env`.

Crear superusuario Django (admin interno):

```bash
python manage.py createsuperuser
```

Configurar **Site** de allauth (ID 1):

```bash
python manage.py shell
```

```python
from django.contrib.sites.models import Site
Site.objects.update_or_create(id=1, defaults={"domain": "api.tudominio.com", "name": "api"})
```

---

## 11. systemd: Gunicorn, Celery worker, Celery beat

Las plantillas oficiales están en `deploy/systemd/`. Usan:

- Ruta: `/opt/win-backend`
- Venv: `/opt/win-backend/env`
- Usuario: `www-data`

### 11.1 Instalar unidades

```bash
cd /opt/win-backend
sudo cp deploy/systemd/win-gunicorn.service /etc/systemd/system/
sudo cp deploy/systemd/win-celery-worker.service /etc/systemd/system/
sudo cp deploy/systemd/win-celery-beat.service /etc/systemd/system/
```

Si tu ruta o usuario difieren, edita **las tres** unidades:

```bash
sudo nano /etc/systemd/system/win-gunicorn.service
```

### 11.2 Contenido de referencia (Gunicorn)

La plantilla actual ejecuta:

```ini
ExecStart=/opt/win-backend/env/bin/gunicorn serverpanaccess.wsgi:application \
    --bind 127.0.0.1:8000 \
    --workers 4 \
    --threads 2 \
    --timeout 120
```

**Ajuste de workers:** en servidor 4 vCPU, `4 workers × 2 threads` es razonable. Aumentar `timeout` si hay requests largas (no sustituye async en sync).

### 11.3 Celery worker (cola obligatoria)

```ini
ExecStart=/opt/win-backend/env/bin/python -m celery -A serverpanaccess worker -l info -Q sync_subscribers
```

Sin `-Q sync_subscribers` las tareas de sync **no se ejecutan**.

### 11.4 Celery beat

```ini
ExecStart=/opt/win-backend/env/bin/python -m celery -A serverpanaccess beat -l info
```

Solo debe haber **una** instancia de beat en todo el clúster.

### 11.5 Habilitar servicios

```bash
sudo systemctl daemon-reload
sudo systemctl enable win-gunicorn win-celery-worker win-celery-beat
sudo systemctl start win-gunicorn win-celery-worker win-celery-beat
```

### 11.6 Verificar

```bash
sudo systemctl status win-gunicorn
sudo systemctl status win-celery-worker
sudo systemctl status win-celery-beat
curl -s http://127.0.0.1:8000/ready/
# {"ready": true}
curl -s http://127.0.0.1:8000/health/
```

### 11.7 Orden de arranque tras reboot

1. `postgresql`, `redis-server`
2. `win-gunicorn`
3. `win-celery-worker`
4. `win-celery-beat`
5. `nginx`

Las unidades ya declaran `After=` parcial; en producción conviene `Requires=redis-server.service` si quieres fallo explícito.

Más detalle: [SYSTEMD_UBUNTU.md](docs/SYSTEMD_UBUNTU.md).

---

## 12. Nginx, TLS y restricción de rutas

### 12.1 Copiar plantilla

```bash
sudo cp /opt/win-backend/deploy/nginx/win-backend.conf /etc/nginx/sites-available/win-backend.conf
sudo nano /etc/nginx/sites-available/win-backend.conf
```

Cambiar:

- `server_name api.miempresa.com` → tu dominio real
- Rutas de certificados Let's Encrypt
- IPs en bloques `allow` para sync (VPN/oficina)

### 12.2 Activar sitio

```bash
sudo ln -sf /etc/nginx/sites-available/win-backend.conf /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### 12.3 Certificado SSL (Certbot)

Con DNS apuntando al servidor:

```bash
sudo certbot --nginx -d api.tudominio.com
```

Renovación automática:

```bash
sudo certbot renew --dry-run
```

### 12.4 Qué hace la plantilla nginx

| Ruta | Comportamiento |
|------|----------------|
| `/wind/sync-*`, `/compare-and-update`, `/full-sync`, `/singleton`, `/ops/` | Solo IPs `allow`; `deny all` |
| `/api/v1/tasks/` | Solo red de confianza |
| `/wind/create-subscriber/` | Rate limit 5 req/min por IP |
| `/ready/`, `/health/` | Sin log access (probes) |
| `/static/` | Archivos desde `staticfiles/` |
| Resto | Proxy a Gunicorn `127.0.0.1:8000` |

Complementa nginx con `SYNC_ADMIN_IP_ALLOWLIST` en Django.

Más detalle: [NGINX_TLS_Y_RESTRICCION_UBUNTU.md](docs/NGINX_TLS_Y_RESTRICCION_UBUNTU.md), [PRODUCTION_HTTPS.md](docs/PRODUCTION_HTTPS.md).

### 12.5 Alternativa: socket Unix

Si prefieres socket en lugar de TCP (como en guías antiguas):

1. Crear directorio `/run/gunicorn` con permisos `www-data`
2. Cambiar Gunicorn a `--bind unix:/run/gunicorn.sock`
3. En nginx: `proxy_pass http://unix:/run/gunicorn.sock`

La plantilla actual usa **TCP 127.0.0.1:8000** (más simple de depurar).

---

## 13. Sincronización inicial con PanAccess

**Solo después** de que worker y beat estén activos.

### 13.1 Obtener JWT de administrador

Crea superusuario o usa cuenta staff. Autentícate vía API:

```bash
curl -s -X POST https://api.tudominio.com/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@ejemplo.com","password":"..."}'
```

Guarda `access` del JSON.

### 13.2 Encolar sync inicial (desde red permitida)

Con `SYNC_HTTP_ASYNC=true` (recomendado):

```bash
TOKEN="eyJ..."
API="https://api.tudominio.com"

curl -s -X POST "$API/wind/sync-subscribers/" -H "Authorization: Bearer $TOKEN"
curl -s -X POST "$API/wind/sync-products/" -H "Authorization: Bearer $TOKEN"
curl -s -X POST "$API/wind/sync-smartcards/" -H "Authorization: Bearer $TOKEN"
```

Respuesta esperada: **202** con `task_id`.

### 13.3 Consultar estado de tarea

```bash
curl -s "$API/api/v1/tasks/TASK_ID/" -H "Authorization: Bearer $TOKEN"
```

### 13.4 Verificar logs

```bash
tail -f /opt/win-backend/logs/panaccess.log
journalctl -u win-celery-worker -f
```

### 13.5 Mantenimiento automático

Beat ejecutará:

- `compare_and_update_subscribers` cada `CELERY_SYNC_MINUTES`
- `compare_and_update_smartcards` cada `CELERY_SMARTCARD_SYNC_MINUTES`
- `full_sync_task` a la hora configurada

Flujo completo: [SYNC_FLUJO_TAREAS.md](docs/SYNC_FLUJO_TAREAS.md).

---

## 14. Logs, logrotate y monitoreo

### 14.1 Archivos de aplicación

| Archivo | Contenido |
|---------|-----------|
| `logs/django.log` | App general |
| `logs/panaccess.log` | API PanAccess |
| `logs/errors.log` | Errores HTTP Django |

### 14.2 Journal systemd

```bash
journalctl -u win-gunicorn -f
journalctl -u win-celery-worker -f
journalctl -u win-celery-beat -f
```

### 14.3 logrotate (recomendado)

Crea `/etc/logrotate.d/win-backend`:

```text
/opt/win-backend/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

```bash
sudo logrotate -d /etc/logrotate.d/win-backend
```

### 14.4 Sentry

Con `SENTRY_DSN` en `.env`:

```bash
python manage.py sentry_test
```

Guía: [SENTRY_PRODUCCION.md](docs/SENTRY_PRODUCCION.md).

### 14.5 Script de salud rápida

```bash
#!/bin/bash
# /opt/win-backend/scripts/health.sh
echo "=== $(date) ==="
systemctl is-active win-gunicorn win-celery-worker win-celery-beat nginx redis-server postgresql
redis-cli ping
curl -sf http://127.0.0.1:8000/ready/ && echo "ready OK" || echo "ready FAIL"
df -h / /opt/win-backend
free -h
```

---

## 15. Actualizaciones y rollback

### 15.1 Deploy de nueva versión

```bash
cd /opt/win-backend
sudo -u www-data git fetch
sudo -u www-data git checkout TAG_O_COMMIT
source env/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check_deploy --strict
sudo systemctl restart win-gunicorn win-celery-worker
# Beat: reiniciar solo si cambió CELERY_BEAT_SCHEDULE
sudo systemctl restart win-celery-beat
```

### 15.2 Rollback

```bash
git checkout COMMIT_ANTERIOR
pip install -r requirements.txt
python manage.py migrate  # si hay migraciones reversibles, evaluar plan
sudo systemctl restart win-gunicorn win-celery-worker win-celery-beat
```

### 15.3 Sin downtime (avanzado)

Requiere segundo servidor, balanceador y migraciones compatibles hacia adelante — fuera del alcance de esta guía single-server.

---

## 16. Solución de problemas

| Síntoma | Causa probable | Acción |
|---------|----------------|--------|
| `check_deploy` falla CORS | `CORS_ALLOWED_ORIGINS` vacío | Definir URL del front con `https://` |
| 502 Bad Gateway | Gunicorn caído | `journalctl -u win-gunicorn -n 50` |
| Sync no avanza | Worker sin cola | Verificar `-Q sync_subscribers` |
| Tareas duplicadas | Redis caído o lock expirado | Restaurar Redis; revisar `task_lock` |
| 403 en sync | IP no permitida | Ajustar nginx `allow` + `SYNC_ADMIN_IP_ALLOWLIST` |
| Login social falla | Redirect URI incorrecto | Consola Google/Meta |
| PanAccess 502 en perfil | Sesión expirada | Logs `panaccess.log`; circuit breaker |
| Estáticos rotos | Falta collectstatic | `collectstatic` + nginx `alias` a `staticfiles/` |
| `DisallowedHost` | `ALLOWED_HOSTS` | Añadir dominio API |

Comandos útiles:

```bash
python manage.py check_redis
python manage.py check_database
redis-cli LLEN sync_subscribers  # si usas cola con nombre visible en broker
sudo nginx -t
```

---

## 17. Checklist final

Marca antes de dar por cerrado el go-live:

### Infraestructura

- [ ] SSH solo con clave; root deshabilitado
- [ ] UFW activo (22, 80, 443)
- [ ] PostgreSQL solo local; backup cron configurado
- [ ] Redis activo; `maxmemory` configurado
- [ ] Certbot SSL válido

### Aplicación

- [ ] `.env` completo; permisos 640
- [ ] `check_deploy --strict` OK
- [ ] `migrate` y `collectstatic` OK
- [ ] `win-gunicorn`, `win-celery-worker`, `win-celery-beat` **active**
- [ ] `/ready/` → `{"ready": true}`

### Seguridad

- [ ] `DEBUG=false`, `PRODUCTION_HTTPS=true`
- [ ] Sync bloqueado en nginx desde internet
- [ ] `FULL_SYNC_HTTP_ENABLED=false`
- [ ] Credenciales PanAccess y social solo en servidor

### Datos

- [ ] Sync inicial suscriptores / productos / smartcards completado
- [ ] Beat ejecutando compare sin errores repetidos
- [ ] Login portal y social probados desde el front real

### Observabilidad

- [ ] Sentry recibiendo eventos de prueba
- [ ] logrotate configurado
- [ ] Runbook de restore de PostgreSQL documentado internamente

---

## Referencias rápidas en el repositorio

| Tema | Documento |
|------|-----------|
| Checklist corto | [DEPLOY_UBUNTU_CHECKLIST.md](docs/DEPLOY_UBUNTU_CHECKLIST.md) |
| CORS | [CORS_PRODUCCION_UBUNTU.md](docs/CORS_PRODUCCION_UBUNTU.md) |
| Registro público | [REGISTRO_PUBLICO_SEGURIDAD.md](docs/REGISTRO_PUBLICO_SEGURIDAD.md) |
| Full sync | [FULL_SYNC_PRODUCCION.md](docs/FULL_SYNC_PRODUCCION.md) |
| Auditoría técnica | [AUDITORIA_FALENCIAS_Y_MEJORAS.md](AUDITORIA_FALENCIAS_Y_MEJORAS.md) |

---

**Guía unificada** | serverpanaccess | Ubuntu sin Docker | 2026

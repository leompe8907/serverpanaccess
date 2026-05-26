# 🚀 Guía Completa de Despliegue - Servidor UDID Django

> ⚠️ **DOCUMENTO OBSOLETO** — Describe un proyecto distinto (UDID, WebSockets, `udid_server`).  
> Para **serverpanaccess / PanAccess** usar: **[../GUIA_DESPLIEGUE_UBUNTU_UNIFICADA.md](../GUIA_DESPLIEGUE_UBUNTU_UNIFICADA.md)**.

## 📋 Resumen del Proyecto

Este es un **servidor Django complejo** que maneja:
- ✅ **Autenticación UDID** con WebSockets en tiempo real
- ✅ **Encriptación de credenciales** (AES-256 + RSA)
- ✅ **Sincronización automática** con APIs externas (Panaccess)
- ✅ **Tareas cron** para sincronización periódica
- ✅ **Base de datos PostgreSQL** con múltiples modelos
- ✅ **Redis** para WebSockets y cache
- ✅ **JWT Authentication** para APIs REST

---

## 🖥️ Requerimientos del Servidor para Producción Multi-Usuario

### **Especificaciones Técnicas para Múltiples Usuarios:**

| Componente | Mínimo | Recomendado | Producción | Justificación |
|------------|--------|-------------|------------|---------------|
| **CPU**    | 4 cores| 8+ cores    | 16+ cores  | Múltiples conexiones WebSocket simultáneas |
| **RAM**    | 8GB    | 16GB+       | 32GB+      | Múltiples usuarios + cache + WebSockets |
| **Almacenamiento** | 100GB SSD | 500GB+ SSD | 1TB+ SSD | Base de datos + logs + backups |
| **Red**    | 1 Gbps | 10 Gbps     | 10+ Gbps   | Múltiples usuarios concurrentes |
| **Sistema Operativo** | Ubuntu 20.04 LTS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS | Estabilidad y soporte |
| **Ancho de Banda** | 100 Mbps | 1 Gbps | 10+ Gbps | Múltiples ubicaciones geográficas |

### **Servicios Requeridos:**
- **PostgreSQL 13+** (Base de datos principal)
- **Redis 6+** (WebSockets y cache)
- **Nginx** (Proxy reverso y load balancer)
- **Python 3.12** (Runtime de la aplicación)
- **Git** (Para clonar el repositorio)
- **Certbot** (Certificados SSL automáticos)
- **Fail2Ban** (Protección contra ataques)

### **⚠️ Consideraciones para Producción Multi-Usuario:**

1. **Concurrencia:** El sistema debe manejar múltiples usuarios simultáneos
2. **WebSockets:** Cada usuario puede tener conexiones WebSocket activas
3. **Geolocalización:** Usuarios desde diferentes países/regiones
4. **Escalabilidad:** Posibilidad de escalar horizontalmente
5. **Monitoreo:** Supervisión continua del rendimiento
6. **Backup:** Estrategia de respaldo robusta
7. **Seguridad:** Protección contra ataques DDoS y intrusiones

---

## 🔧 Instalación Paso a Paso

### **Paso 1: Preparación del Servidor**

```bash
# Actualizar el sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependencias básicas
sudo apt install -y curl wget git build-essential software-properties-common

# Instalar Python 3.12
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev

# Instalar PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Instalar Redis
sudo apt install -y redis-server

# Instalar Nginx
sudo apt install -y nginx

# Instalar Node.js (para compilar assets si es necesario)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

### **Paso 2: Configuración de PostgreSQL**

```bash
# Cambiar a usuario postgres
sudo -u postgres psql

# En la consola de PostgreSQL:
CREATE DATABASE udid_server;
CREATE USER udid_user WITH PASSWORD 'TU_PASSWORD_SEGURA_AQUI';
GRANT ALL PRIVILEGES ON DATABASE udid_server TO udid_user;
ALTER USER udid_user CREATEDB;
\q

# Configurar PostgreSQL para conexiones remotas (opcional)
sudo nano /etc/postgresql/13/main/postgresql.conf
# Descomentar y cambiar: listen_addresses = 'localhost'

sudo nano /etc/postgresql/13/main/pg_hba.conf
# Agregar línea: local   all             udid_user                                md5

# Reiniciar PostgreSQL
sudo systemctl restart postgresql
sudo systemctl enable postgresql
```

### **Paso 3: Configuración de Redis**

```bash
# Configurar Redis
sudo nano /etc/redis/redis.conf

# Cambiar las siguientes líneas:
# bind 127.0.0.1 ::1
# maxmemory 256mb
# maxmemory-policy allkeys-lru

# Reiniciar Redis
sudo systemctl restart redis-server
sudo systemctl enable redis-server

# Verificar que Redis funciona
redis-cli ping
# Debe responder: PONG
```

### **Paso 4: Crear Usuario del Sistema**

```bash
# Crear usuario para la aplicación
sudo adduser --system --group --home /opt/udid-server udid
sudo mkdir -p /opt/udid-server
sudo chown udid:udid /opt/udid-server

# Cambiar al usuario udid
sudo su - udid
```

### **Paso 5: Clonar y Configurar la Aplicación**

```bash
# Clonar el repositorio
cd /opt/udid-server
git clone https://github.com/tu-usuario/tu-repositorio.git .

# Crear entorno virtual
python3.12 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt

# Instalar dependencias adicionales para producción
pip install gunicorn psycopg2-binary
```

### **Paso 6: Configuración de Variables de Entorno**

```bash
# Crear archivo .env
nano .env
```

**Contenido del archivo .env:**

```env
# ===========================================
# CONFIGURACIÓN DE DJANGO
# ===========================================
SECRET_KEY=tu_secret_key_muy_largo_y_seguro_aqui
DEBUG=False
ALLOWED_HOSTS=tu-dominio.com,www.tu-dominio.com,IP_DEL_SERVIDOR
CORS_ORIGIN_WHITELIST=https://tu-dominio.com,https://www.tu-dominio.com

# ===========================================
# CONFIGURACIÓN DE BASE DE DATOS
# ===========================================
DATABASE_URL=postgresql://udid_user:TU_PASSWORD_SEGURA_AQUI@localhost:5432/udid_server

# ===========================================
# CONFIGURACIÓN DE REDIS
# ===========================================
REDIS_URL=redis://localhost:6379/0

# ===========================================
# CONFIGURACIÓN DE PANACCESS (API Externa)
# ===========================================
url_panaccess=https://api.panaccess.com
username=tu_usuario_panaccess
password=tu_password_panaccess
api_token=tu_api_token_panaccess
salt=tu_salt_panaccess
ENCRYPTION_KEY=tu_clave_de_encriptacion_fernet_aqui

# ===========================================
# CONFIGURACIÓN DE WEBSOCKETS
# ===========================================
UDID_WAIT_TIMEOUT=600
UDID_ENABLE_POLLING=1
UDID_POLL_INTERVAL=2

# ===========================================
# CONFIGURACIÓN DE PUERTO
# ===========================================
PORT=8000
```

### **Paso 7: Configuración de la Base de Datos**

```bash
# Activar entorno virtual
source venv/bin/activate

# Ejecutar migraciones
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Recopilar archivos estáticos
python manage.py collectstatic --noinput

# Verificar configuración
python manage.py check --deploy
```

### **Paso 8: Configuración de Nginx**

```bash
# Crear configuración de Nginx
sudo nano /etc/nginx/sites-available/udid-server
```

**Contenido de la configuración de Nginx para Multi-Usuario:**

```nginx
# Configuración upstream para balanceador de carga
upstream udid_backend {
    # Para múltiples instancias de Gunicorn (escalabilidad horizontal)
    server 127.0.0.1:8000 weight=3 max_fails=3 fail_timeout=30s;
    # server 127.0.0.1:8001 weight=3 max_fails=3 fail_timeout=30s;  # Descomentar para más instancias
    # server 127.0.0.1:8002 weight=3 max_fails=3 fail_timeout=30s;  # Descomentar para más instancias
    
    # Configuración de balanceador
    least_conn;  # Distribuir carga por conexiones activas
    keepalive 32;  # Mantener conexiones abiertas
}

# Configuración de rate limiting
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=ws:10m rate=5r/s;
limit_conn_zone $binary_remote_addr zone=conn_limit_per_ip:10m;

server {
    listen 80;
    server_name tu-dominio.com www.tu-dominio.com;

    # Redirigir HTTP a HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name tu-dominio.com www.tu-dominio.com;

    # Configuración SSL optimizada para múltiples usuarios
    ssl_certificate /etc/ssl/certs/tu-dominio.crt;
    ssl_certificate_key /etc/ssl/private/tu-dominio.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_stapling on;
    ssl_stapling_verify on;

    # Configuración de conexiones para múltiples usuarios
    keepalive_timeout 65;
    keepalive_requests 1000;
    
    # Límites de conexiones por IP
    limit_conn conn_limit_per_ip 20;
    
    # Archivos estáticos con cache optimizado
    location /static/ {
        alias /opt/udid-server/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        add_header Vary "Accept-Encoding";
        
        # Compresión para archivos estáticos
        gzip on;
        gzip_vary on;
        gzip_min_length 1024;
        gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
    }

    # Archivos de media
    location /media/ {
        alias /opt/udid-server/media/;
        expires 30d;
        add_header Cache-Control "public";
    }

    # WebSocket support optimizado para múltiples usuarios
    location /ws/ {
        # Rate limiting específico para WebSockets
        limit_req zone=ws burst=10 nodelay;
        
        proxy_pass http://udid_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts optimizados para WebSockets
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
        proxy_connect_timeout 60;
        
        # Buffer settings para WebSockets
        proxy_buffering off;
        proxy_cache off;
    }

    # APIs REST con rate limiting
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        
        proxy_pass http://udid_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts para APIs
        proxy_read_timeout 300;
        proxy_connect_timeout 60;
        proxy_send_timeout 300;
    }

    # Aplicación Django principal
    location / {
        limit_req zone=api burst=30 nodelay;
        
        proxy_pass http://udid_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts generales
        proxy_read_timeout 300;
        proxy_connect_timeout 60;
        proxy_send_timeout 300;
        
        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }

    # Configuración de seguridad mejorada para producción
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' wss: https:; frame-ancestors 'self';" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

    # Límites de tamaño para múltiples usuarios
    client_max_body_size 50M;
    client_body_timeout 60s;
    client_header_timeout 60s;
    
    # Configuración de logs específicos
    access_log /var/log/nginx/udid-access.log;
    error_log /var/log/nginx/udid-error.log;
}
```

```bash
# Habilitar el sitio
sudo ln -s /etc/nginx/sites-available/udid-server /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### **Paso 9: Configuración de Gunicorn**

```bash
# Crear archivo de configuración de Gunicorn
nano /opt/udid-server/gunicorn.conf.py
```

**Contenido de gunicorn.conf.py para Multi-Usuario:**

```python
# Gunicorn configuration file para producción multi-usuario
import multiprocessing
import os

# Configuración de binding
bind = "127.0.0.1:8000"

# Workers optimizados para múltiples usuarios
# Fórmula: (2 x CPU cores) + 1, pero limitado para WebSockets
workers = min(multiprocessing.cpu_count() * 2 + 1, 8)  # Máximo 8 workers

# Worker class optimizado para WebSockets
worker_class = "uvicorn.workers.UvicornWorker"

# Conexiones por worker (importante para WebSockets)
worker_connections = 2000  # Aumentado para múltiples usuarios

# Configuración de requests
max_requests = 2000  # Aumentado para producción
max_requests_jitter = 200  # Variación en el restart

# Timeouts optimizados para WebSockets
timeout = 600  # 10 minutos para WebSockets largos
keepalive = 5  # Aumentado para mantener conexiones
graceful_timeout = 30

# Preload app para mejor rendimiento
preload_app = True

# Configuración de threads (para I/O intensivo)
threads = 4

# Configuración de memoria
worker_tmp_dir = "/dev/shm"  # Usar RAM para archivos temporales

# Logging detallado para monitoreo
accesslog = "/opt/udid-server/logs/gunicorn_access.log"
errorlog = "/opt/udid-server/logs/gunicorn_error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "udid-server"

# Security mejorada
limit_request_line = 8192  # Aumentado para requests complejos
limit_request_fields = 200  # Aumentado para headers complejos
limit_request_field_size = 16384  # Aumentado para headers largos

# Configuración de usuario
user = "udid"
group = "udid"

# Configuración de archivos
raw_env = [
    'DJANGO_SETTINGS_MODULE=server.settings',
]

# Configuración de señales
forwarded_allow_ips = "*"  # Para proxy reverso

# Configuración de WebSockets
worker_class_kwargs = {
    "loop": "asyncio",
    "http": "httptools",
    "ws": "websockets",
}

# Configuración de memoria para WebSockets
worker_memory_limit = 512 * 1024 * 1024  # 512MB por worker

# Configuración de restart automático
max_worker_connections = 1000
worker_max_requests_jitter = 50

# Configuración de logging en tiempo real
capture_output = True
enable_stdio_inheritance = True
```

### **Paso 10: Crear Servicio Systemd**

```bash
# Crear directorio de logs
sudo mkdir -p /opt/udid-server/logs
sudo chown udid:udid /opt/udid-server/logs

# Crear servicio systemd
sudo nano /etc/systemd/system/udid-server.service
```

**Contenido del servicio systemd:**

```ini
[Unit]
Description=UDID Server Django Application
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=udid
Group=udid
WorkingDirectory=/opt/udid-server
Environment=PATH=/opt/udid-server/venv/bin
ExecStart=/opt/udid-server/venv/bin/gunicorn --config gunicorn.conf.py server.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=3

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/udid-server

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=udid-server

[Install]
WantedBy=multi-user.target
```

```bash
# Habilitar y iniciar el servicio
sudo systemctl daemon-reload
sudo systemctl enable udid-server
sudo systemctl start udid-server
sudo systemctl status udid-server
```

### **Paso 11: Configuración de Tareas Cron**

```bash
# Crear script para tareas cron
nano /opt/udid-server/run_cron.sh
```

**Contenido del script:**

```bash
#!/bin/bash
cd /opt/udid-server
source venv/bin/activate
python manage.py runcrons
```

```bash
# Hacer ejecutable
chmod +x /opt/udid-server/run_cron.sh

# Configurar cron (ejecutar cada minuto)
sudo crontab -e
# Agregar línea:
# * * * * * /opt/udid-server/run_cron.sh >> /opt/udid-server/logs/cron.log 2>&1
```

---

## 🔒 Configuración de Seguridad

### **1. Firewall (UFW)**

```bash
# Configurar firewall
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 8000/tcp  # Bloquear acceso directo a Gunicorn
```

### **2. Fail2Ban**

```bash
# Instalar Fail2Ban
sudo apt install -y fail2ban

# Configurar para Nginx
sudo nano /etc/fail2ban/jail.local
```

**Contenido de jail.local:**

```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log

[nginx-limit-req]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 10
```

### **3. Certificado SSL (Let's Encrypt)**

```bash
# Instalar Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtener certificado
sudo certbot --nginx -d tu-dominio.com -d www.tu-dominio.com

# Configurar renovación automática
sudo crontab -e
# Agregar línea:
# 0 12 * * * /usr/bin/certbot renew --quiet
```

---

## 📊 Monitoreo y Logs para Multi-Usuario

### **1. Configuración de Logs Avanzada**

```bash
# Crear directorios de logs
sudo mkdir -p /var/log/udid-server
sudo mkdir -p /opt/udid-server/logs
sudo chown udid:udid /var/log/udid-server
sudo chown udid:udid /opt/udid-server/logs

# Configurar rotación de logs optimizada para múltiples usuarios
sudo nano /etc/logrotate.d/udid-server
```

**Contenido de logrotate para Multi-Usuario:**

```
/opt/udid-server/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 udid udid
    postrotate
        systemctl reload udid-server
    endscript
}

/var/log/nginx/udid-*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 www-data www-data
    postrotate
        systemctl reload nginx
    endscript
}

# Logs de PostgreSQL
/var/log/postgresql/postgresql-*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 postgres postgres
    postrotate
        systemctl reload postgresql
    endscript
}
```

### **2. Monitoreo Avanzado para Multi-Usuario**

```bash
# Instalar herramientas de monitoreo avanzadas
sudo apt install -y htop iotop nethogs netstat-nat iftop nload

# Instalar herramientas adicionales para monitoreo de red
sudo apt install -y tcpdump wireshark-common

# Script de monitoreo avanzado para múltiples usuarios
nano /opt/udid-server/monitor_multi_user.sh
```

**Contenido del script de monitoreo avanzado:**

```bash
#!/bin/bash

echo "=== UDID Server Status - Multi-Usuario ==="
echo "Fecha: $(date)"
echo "=========================================="

# Información del sistema
echo "📊 SISTEMA:"
echo "Uptime: $(uptime)"
echo "Memoria: $(free -h | grep -E 'Mem|Swap')"
echo "Disco: $(df -h / | tail -1)"
echo "CPU Load: $(cat /proc/loadavg)"
echo ""

# Estado de servicios
echo "🔧 SERVICIOS:"
echo "UDID Server: $(systemctl is-active udid-server)"
echo "PostgreSQL: $(systemctl is-active postgresql)"
echo "Redis: $(systemctl is-active redis-server)"
echo "Nginx: $(systemctl is-active nginx)"
echo ""

# Conexiones de red
echo "🌐 CONEXIONES DE RED:"
echo "Conexiones WebSocket (puerto 8000):"
ss -tuln | grep :8000 | wc -l
echo "Conexiones HTTP (puerto 80):"
ss -tuln | grep :80 | wc -l
echo "Conexiones HTTPS (puerto 443):"
ss -tuln | grep :443 | wc -l
echo "Conexiones PostgreSQL (puerto 5432):"
ss -tuln | grep :5432 | wc -l
echo "Conexiones Redis (puerto 6379):"
ss -tuln | grep :6379 | wc -l
echo ""

# Procesos de Gunicorn
echo "⚙️ PROCESOS GUNICORN:"
ps aux | grep gunicorn | grep -v grep | wc -l
echo "Workers activos:"
ps aux | grep gunicorn | grep -v grep | awk '{print $2}' | wc -l
echo ""

# Uso de memoria por proceso
echo "💾 MEMORIA POR PROCESO:"
echo "Gunicorn workers:"
ps aux | grep gunicorn | grep -v grep | awk '{sum+=$6} END {print sum/1024 " MB"}'
echo "PostgreSQL:"
ps aux | grep postgres | grep -v grep | awk '{sum+=$6} END {print sum/1024 " MB"}'
echo "Redis:"
ps aux | grep redis | grep -v grep | awk '{sum+=$6} END {print sum/1024 " MB"}'
echo "Nginx:"
ps aux | grep nginx | grep -v grep | awk '{sum+=$6} END {print sum/1024 " MB"}'
echo ""

# Conexiones activas por IP
echo "👥 CONEXIONES POR IP (Top 10):"
ss -tuln | grep :443 | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -nr | head -10
echo ""

# Logs recientes
echo "📝 LOGS RECIENTES:"
echo "Errores de Gunicorn (últimas 5 líneas):"
tail -n 5 /opt/udid-server/logs/gunicorn_error.log 2>/dev/null || echo "No hay logs de error"
echo ""
echo "Accesos de Nginx (últimas 5 líneas):"
tail -n 5 /var/log/nginx/udid-access.log 2>/dev/null || echo "No hay logs de acceso"
echo ""

# Métricas de Redis
echo "🔴 REDIS:"
redis-cli info clients | grep connected_clients
redis-cli info memory | grep used_memory_human
redis-cli info stats | grep total_commands_processed
echo ""

# Métricas de PostgreSQL
echo "🐘 POSTGRESQL:"
sudo -u postgres psql -d udid_server -c "SELECT count(*) as conexiones_activas FROM pg_stat_activity;" 2>/dev/null || echo "No se pudo conectar a PostgreSQL"
echo ""

# Espacio en disco por directorio
echo "💿 ESPACIO EN DISCO:"
du -sh /opt/udid-server/logs/ 2>/dev/null || echo "0B logs"
du -sh /var/log/nginx/ 2>/dev/null || echo "0B nginx logs"
du -sh /var/log/postgresql/ 2>/dev/null || echo "0B postgres logs"
echo ""

echo "=========================================="
echo "Monitoreo completado: $(date)"
```

```bash
# Hacer ejecutable
chmod +x /opt/udid-server/monitor_multi_user.sh

# Crear script de monitoreo en tiempo real
nano /opt/udid-server/monitor_realtime.sh
```

**Script de monitoreo en tiempo real:**

```bash
#!/bin/bash
# Monitoreo en tiempo real para múltiples usuarios

while true; do
    clear
    echo "=== MONITOREO EN TIEMPO REAL - UDID SERVER ==="
    echo "Actualizado: $(date)"
    echo "Presiona Ctrl+C para salir"
    echo ""
    
    # Conexiones activas
    echo "🌐 CONEXIONES ACTIVAS:"
    echo "WebSocket (8000): $(ss -tuln | grep :8000 | wc -l)"
    echo "HTTPS (443): $(ss -tuln | grep :443 | wc -l)"
    echo "PostgreSQL (5432): $(ss -tuln | grep :5432 | wc -l)"
    echo "Redis (6379): $(ss -tuln | grep :6379 | wc -l)"
    echo ""
    
    # Uso de CPU y memoria
    echo "💻 RECURSOS:"
    echo "CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)%"
    echo "Memoria: $(free | grep Mem | awk '{printf "%.1f%%", $3/$2 * 100.0}')"
    echo "Load: $(cat /proc/loadavg | awk '{print $1}')"
    echo ""
    
    # Procesos Gunicorn
    echo "⚙️ WORKERS GUNICORN:"
    ps aux | grep gunicorn | grep -v grep | wc -l
    echo ""
    
    # Conexiones por IP (últimas 5)
    echo "👥 IPs CONECTADAS (Top 5):"
    ss -tuln | grep :443 | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -nr | head -5
    echo ""
    
    sleep 5
done
```

```bash
# Hacer ejecutable
chmod +x /opt/udid-server/monitor_realtime.sh
```

---

## 🚀 Comandos de Gestión

### **Comandos Básicos:**

```bash
# Iniciar/parar/reiniciar servicios
sudo systemctl start udid-server
sudo systemctl stop udid-server
sudo systemctl restart udid-server
sudo systemctl status udid-server

# Ver logs en tiempo real
sudo journalctl -u udid-server -f

# Ejecutar migraciones
cd /opt/udid-server
source venv/bin/activate
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Recopilar archivos estáticos
python manage.py collectstatic --noinput

# Ejecutar tareas cron manualmente
python manage.py runcrons

# Verificar configuración
python manage.py check --deploy
```

### **Comandos de Mantenimiento:**

```bash
# Backup de base de datos
pg_dump -h localhost -U udid_user -d udid_server > backup_$(date +%Y%m%d_%H%M%S).sql

# Restaurar backup
psql -h localhost -U udid_user -d udid_server < backup_file.sql

# Limpiar logs antiguos
find /opt/udid-server/logs -name "*.log" -mtime +30 -delete

# Actualizar aplicación
cd /opt/udid-server
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart udid-server
```

---

## ⚠️ Solución de Problemas Comunes

### **1. Error de Conexión a Base de Datos**

```bash
# Verificar que PostgreSQL esté corriendo
sudo systemctl status postgresql

# Verificar conexión
psql -h localhost -U udid_user -d udid_server

# Verificar configuración en .env
cat .env | grep DATABASE_URL
```

### **2. Error de WebSockets**

```bash
# Verificar Redis
redis-cli ping

# Verificar configuración de Nginx
sudo nginx -t

# Verificar logs de Gunicorn
tail -f /opt/udid-server/logs/gunicorn_error.log
```

### **3. Error de Memoria**

```bash
# Verificar uso de memoria
free -h
htop

# Ajustar workers en gunicorn.conf.py
# Reducir workers si hay poca memoria
```

### **4. Error de Permisos**

```bash
# Verificar permisos
ls -la /opt/udid-server/
sudo chown -R udid:udid /opt/udid-server/
```

---

## 📈 Optimizaciones de Rendimiento

### **1. Configuración de PostgreSQL**

```bash
# Editar configuración de PostgreSQL
sudo nano /etc/postgresql/13/main/postgresql.conf

# Ajustar parámetros para mejor rendimiento:
# shared_buffers = 256MB
# effective_cache_size = 1GB
# maintenance_work_mem = 64MB
# checkpoint_completion_target = 0.9
# wal_buffers = 16MB
# default_statistics_target = 100

# Reiniciar PostgreSQL
sudo systemctl restart postgresql
```

### **2. Configuración de Redis**

```bash
# Editar configuración de Redis
sudo nano /etc/redis/redis.conf

# Ajustar parámetros:
# maxmemory 512mb
# maxmemory-policy allkeys-lru
# tcp-keepalive 60

# Reiniciar Redis
sudo systemctl restart redis-server
```

---

## 🔄 Proceso de Actualización

### **Script de Actualización Automática:**

```bash
# Crear script de actualización
nano /opt/udid-server/update.sh
```

**Contenido del script:**

```bash
#!/bin/bash
set -e

echo "🔄 Iniciando actualización del servidor UDID..."

# Backup de base de datos
echo "📦 Creando backup de base de datos..."
pg_dump -h localhost -U udid_user -d udid_server > backup_$(date +%Y%m%d_%H%M%S).sql

# Parar servicios
echo "⏹️ Parando servicios..."
sudo systemctl stop udid-server

# Actualizar código
echo "📥 Actualizando código..."
cd /opt/udid-server
git pull origin main

# Actualizar dependencias
echo "📦 Actualizando dependencias..."
source venv/bin/activate
pip install -r requirements.txt

# Ejecutar migraciones
echo "🗄️ Ejecutando migraciones..."
python manage.py migrate

# Recopilar archivos estáticos
echo "📁 Recopilando archivos estáticos..."
python manage.py collectstatic --noinput

# Iniciar servicios
echo "▶️ Iniciando servicios..."
sudo systemctl start udid-server

# Verificar estado
echo "✅ Verificando estado..."
sudo systemctl status udid-server

echo "🎉 Actualización completada!"
```

```bash
# Hacer ejecutable
chmod +x /opt/udid-server/update.sh
```

---

## 📞 Soporte y Contacto

### **Archivos de Log Importantes:**
- `/opt/udid-server/logs/gunicorn_error.log` - Errores de la aplicación
- `/opt/udid-server/logs/gunicorn_access.log` - Accesos a la aplicación
- `/var/log/nginx/error.log` - Errores de Nginx
- `/var/log/postgresql/postgresql-13-main.log` - Logs de PostgreSQL
- `/var/log/redis/redis-server.log` - Logs de Redis

### **Comandos de Diagnóstico:**
```bash
# Estado general del sistema
sudo systemctl status udid-server postgresql redis-server nginx

# Uso de recursos
htop
df -h
free -h

# Conexiones de red
ss -tuln | grep -E ':(80|443|5432|6379|8000)'

# Logs en tiempo real
sudo journalctl -u udid-server -f
```

---

## 🔄 Escalabilidad Horizontal para Multi-Usuario

### **Configuración de Múltiples Instancias de Gunicorn**

Para manejar más usuarios concurrentes, puedes ejecutar múltiples instancias de Gunicorn:

```bash
# Crear script para múltiples instancias
nano /opt/udid-server/start_multiple_instances.sh
```

**Contenido del script:**

```bash
#!/bin/bash
# Script para iniciar múltiples instancias de Gunicorn

cd /opt/udid-server
source venv/bin/activate

# Configuración de puertos
PORTS=(8000 8001 8002 8003)
WORKERS_PER_INSTANCE=2

for port in "${PORTS[@]}"; do
    echo "Iniciando instancia en puerto $port..."
    gunicorn --config gunicorn.conf.py --bind 127.0.0.1:$port server.wsgi:application &
    sleep 2
done

echo "Todas las instancias iniciadas"
echo "Puertos activos: ${PORTS[*]}"
```

```bash
# Hacer ejecutable
chmod +x /opt/udid-server/start_multiple_instances.sh

# Actualizar configuración de Nginx para múltiples instancias
sudo nano /etc/nginx/sites-available/udid-server
```

**Actualizar upstream en Nginx:**

```nginx
# Configuración upstream para múltiples instancias
upstream udid_backend {
    server 127.0.0.1:8000 weight=3 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8001 weight=3 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8002 weight=3 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8003 weight=3 max_fails=3 fail_timeout=30s;
    
    # Configuración de balanceador
    least_conn;  # Distribuir carga por conexiones activas
    keepalive 32;  # Mantener conexiones abiertas
}
```

### **Configuración de Load Balancer con HAProxy (Opcional)**

Para mayor escalabilidad, puedes usar HAProxy como load balancer:

```bash
# Instalar HAProxy
sudo apt install -y haproxy

# Configurar HAProxy
sudo nano /etc/haproxy/haproxy.cfg
```

**Configuración de HAProxy:**

```haproxy
global
    daemon
    maxconn 4096
    log 127.0.0.1:514 local0

defaults
    mode http
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms
    option httplog

frontend udid_frontend
    bind *:80
    bind *:443 ssl crt /etc/ssl/certs/tu-dominio.pem
    redirect scheme https if !{ ssl_fc }
    
    # Rate limiting
    stick-table type ip size 100k expire 30s store http_req_rate(10s)
    http-request track-sc0 src
    http-request deny if { sc_http_req_rate(0) gt 20 }
    
    default_backend udid_backend

backend udid_backend
    balance leastconn
    option httpchk GET /health/
    
    server udid1 127.0.0.1:8000 check
    server udid2 127.0.0.1:8001 check
    server udid3 127.0.0.1:8002 check
    server udid4 127.0.0.1:8003 check
```

### **Monitoreo de Escalabilidad**

```bash
# Script para monitorear escalabilidad
nano /opt/udid-server/monitor_scalability.sh
```

**Script de monitoreo de escalabilidad:**

```bash
#!/bin/bash

echo "=== MONITOREO DE ESCALABILIDAD ==="
echo "Fecha: $(date)"
echo ""

# Verificar instancias activas
echo "🔧 INSTANCIAS ACTIVAS:"
for port in 8000 8001 8002 8003; do
    if ss -tuln | grep -q ":$port "; then
        echo "Puerto $port: ✅ ACTIVO"
    else
        echo "Puerto $port: ❌ INACTIVO"
    fi
done
echo ""

# Conexiones por instancia
echo "🌐 CONEXIONES POR INSTANCIA:"
for port in 8000 8001 8002 8003; do
    connections=$(ss -tuln | grep ":$port " | wc -l)
    echo "Puerto $port: $connections conexiones"
done
echo ""

# Uso de CPU por worker
echo "💻 CPU POR WORKER:"
ps aux | grep gunicorn | grep -v grep | awk '{print $2, $3, $4}' | while read pid cpu mem; do
    echo "PID $pid: CPU $cpu%, Mem $mem%"
done
echo ""

# Memoria total utilizada
echo "💾 MEMORIA TOTAL:"
total_mem=$(ps aux | grep gunicorn | grep -v grep | awk '{sum+=$6} END {print sum/1024}')
echo "Memoria total Gunicorn: ${total_mem} MB"
echo ""

# Recomendaciones
echo "📊 RECOMENDACIONES:"
cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
if (( $(echo "$cpu_usage > 80" | bc -l) )); then
    echo "⚠️  CPU alta ($cpu_usage%) - Considera agregar más instancias"
else
    echo "✅ CPU normal ($cpu_usage%)"
fi

mem_usage=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
if (( mem_usage > 80 )); then
    echo "⚠️  Memoria alta ($mem_usage%) - Considera optimizar o escalar"
else
    echo "✅ Memoria normal ($mem_usage%)"
fi
```

---

## ✅ Checklist de Despliegue Multi-Usuario

### **Configuración Básica:**
- [ ] Servidor configurado con especificaciones para multi-usuario (8GB+ RAM, 4+ cores)
- [ ] Python 3.12 instalado
- [ ] PostgreSQL instalado y configurado con conexiones optimizadas
- [ ] Redis instalado y configurado para múltiples conexiones
- [ ] Nginx instalado y configurado como load balancer
- [ ] Aplicación clonada y configurada
- [ ] Variables de entorno configuradas para producción
- [ ] Base de datos migrada
- [ ] Archivos estáticos recopilados

### **Configuración Multi-Usuario:**
- [ ] Nginx configurado con upstream para balanceador de carga
- [ ] Rate limiting configurado (APIs y WebSockets)
- [ ] Gunicorn configurado para múltiples workers
- [ ] WebSockets optimizados para múltiples conexiones
- [ ] CORS configurado para múltiples dominios
- [ ] Headers de seguridad configurados

### **Servicios y Monitoreo:**
- [ ] Servicios systemd configurados
- [ ] Firewall configurado con reglas para múltiples IPs
- [ ] Certificado SSL instalado y configurado
- [ ] Monitoreo avanzado configurado
- [ ] Scripts de monitoreo en tiempo real funcionando
- [ ] Logs configurados y rotando correctamente

### **Escalabilidad:**
- [ ] Múltiples instancias de Gunicorn configuradas (opcional)
- [ ] HAProxy configurado (opcional)
- [ ] Scripts de escalabilidad funcionando
- [ ] Monitoreo de escalabilidad implementado

### **Seguridad Multi-Usuario:**
- [ ] Fail2Ban configurado para múltiples IPs
- [ ] Rate limiting por IP implementado
- [ ] Conexiones por IP limitadas
- [ ] Headers de seguridad optimizados
- [ ] SSL/TLS configurado correctamente

### **Backup y Mantenimiento:**
- [ ] Estrategia de backup configurada
- [ ] Scripts de actualización automática funcionando
- [ ] Rotación de logs configurada
- [ ] Monitoreo de espacio en disco
- [ ] Documentación actualizada

### **Pruebas de Carga:**
- [ ] Pruebas con múltiples usuarios simultáneos
- [ ] Pruebas de WebSockets con múltiples conexiones
- [ ] Pruebas de APIs con rate limiting
- [ ] Pruebas de escalabilidad horizontal
- [ ] Monitoreo de rendimiento bajo carga

---

## 🎯 Capacidades del Sistema Multi-Usuario

### **Usuarios Concurrentes Soportados:**
- **Configuración Mínima:** 50-100 usuarios simultáneos
- **Configuración Recomendada:** 200-500 usuarios simultáneos  
- **Configuración de Producción:** 1000+ usuarios simultáneos

### **WebSockets Simultáneos:**
- **Configuración Mínima:** 100 conexiones WebSocket
- **Configuración Recomendada:** 500 conexiones WebSocket
- **Configuración de Producción:** 2000+ conexiones WebSocket

### **APIs por Segundo:**
- **Configuración Mínima:** 100 requests/segundo
- **Configuración Recomendada:** 500 requests/segundo
- **Configuración de Producción:** 2000+ requests/segundo

---

**¡Tu servidor UDID Django está listo para producción multi-usuario! 🚀**

Esta guía te proporciona todo lo necesario para desplegar y mantener tu aplicación en un servidor privado de forma segura y eficiente, optimizada para múltiples usuarios desde diferentes ubicaciones geográficas.

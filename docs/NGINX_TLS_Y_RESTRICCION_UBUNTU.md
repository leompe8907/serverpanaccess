# TLS (nginx) y restricción de sync (roadmap #5)

Sin Docker. nginx en Ubuntu termina HTTPS y reenvía a Gunicorn en `127.0.0.1:8000`.

## 1. Instalar nginx y certificado

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

Con DNS apuntando `api.tudominio.com` al servidor:

```bash
sudo certbot --nginx -d api.tudominio.com
```

## 2. Variables `.env` en el servidor

```env
PRODUCTION_HTTPS=true
ALLOWED_HOSTS=api.tudominio.com
CORS_ALLOWED_ORIGINS=https://app.tudominio.com

# Opcional: segunda capa en Django (además de nginx)
SYNC_ADMIN_IP_ALLOWLIST=127.0.0.1,10.8.0.0/24
```

`PRODUCTION_HTTPS=true` activa cookies secure, HSTS y redirect en Django (ver #3).

## 3. Plantilla nginx

Copiar y editar [`deploy/nginx/win-backend.conf`](../deploy/nginx/win-backend.conf):

```bash
sudo cp deploy/nginx/win-backend.conf /etc/nginx/sites-available/win-backend
sudo nano /etc/nginx/sites-available/win-backend
# Ajustar server_name, ssl_certificate, bloques allow (tu VPN)

sudo ln -sf /etc/nginx/sites-available/win-backend /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### Qué bloquea la plantilla

| Ruta | Acceso público internet |
|------|-------------------------|
| `/api/auth/`, `/api/v1/profile/` | Permitido (HTTPS) |
| `/wind/sync-*`, `/wind/full-sync/`, etc. | Solo `127.0.0.1` + IPs en `allow` |
| `/api/v1/tasks/` | Solo IPs permitidas |

El sync programado **no usa HTTP**: Celery Beat + worker en el mismo servidor.

## 4. Firewall (UFW)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

No expongas el puerto `8000` de Gunicorn; solo nginx en 80/443.

```bash
# Gunicorn solo local (win-gunicorn.service ya usa 127.0.0.1:8000)
```

## 5. Middleware Django (opcional)

Si defines `SYNC_ADMIN_IP_ALLOWLIST`, Django devuelve **403** en rutas sync/login/singleton/tasks desde IPs no listadas (útil si alguien salta nginx).

Sin la variable, solo aplica la restricción de nginx.

## 6. Pruebas roadmap #5

| Prueba | Comando | Esperado |
|--------|---------|----------|
| Solo HTTPS | `curl -I http://api.tudominio.com/ready/` | Redirect 301 a https |
| API pública | `curl https://api.tudominio.com/ready/` | 200 |
| Sync desde internet | `curl https://api.tudominio.com/wind/sync-subscribers/` | **403** (nginx) |
| Sync desde servidor | `curl -H "Host: api..." http://127.0.0.1/wind/...` con allow | Según auth staff |
| Puerto 8000 cerrado | `ss -tlnp \| grep 8000` | Solo 127.0.0.1 |

```bash
python manage.py check_deploy --strict
# Con PRODUCTION_HTTPS=true los avisos W004/W008 de check --deploy desaparecen
```

## 7. Orden de despliegue recomendado

1. PostgreSQL (#1)  
2. Redis + Celery (#2)  
3. `.env` seguridad (#3–#4)  
4. Gunicorn (`win-gunicorn.service`)  
5. **nginx + certbot (#5)**  
6. Abrir solo 443 al mundo; sync vía Celery o VPN  

## Referencias

- [SEGURIDAD_PRODUCCION_UBUNTU.md](./SEGURIDAD_PRODUCCION_UBUNTU.md)
- [CORS_PRODUCCION_UBUNTU.md](./CORS_PRODUCCION_UBUNTU.md)
- [ROADMAP_PRODUCCION.md](./ROADMAP_PRODUCCION.md)

# Seguridad básica de despliegue (roadmap #3)

Variables críticas en `.env` del **Ubuntu Server** antes de exponer la API a internet.

## 1. Variables obligatorias

```env
DEBUG=false
SECRET_KEY=<cadena-aleatoria-larga>
ALLOWED_HOSTS=api.tudominio.com,tudominio.com
```

| Variable | Desarrollo local | Producción Ubuntu |
|----------|------------------|-------------------|
| `DEBUG` | `true` opcional | **`false`** siempre |
| `SECRET_KEY` | Puede repetirse en equipo dev | **Única** por entorno; nunca en git |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | **Dominios reales** (sin `*`) |

### Generar `SECRET_KEY`

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copia el resultado a `.env` en el servidor (no al repositorio).

### `ALLOWED_HOSTS`

Debe coincidir con el **Host** que envía el cliente (dominio público o IP si accedes solo por IP interna).

Ejemplo con nginx:

```env
ALLOWED_HOSTS=api.miempresa.com,miempresa.com
```

Si nginx termina TLS y reenvía a Gunicorn en `127.0.0.1:8000`, el Host suele ser el dominio público, no `127.0.0.1`.

---

## 2. HTTPS detrás de nginx (recomendado)

Con TLS en nginx, activa en `.env`:

```env
PRODUCTION_HTTPS=true
```

Django aplicará cookies seguras y redirección HTTP→HTTPS según `settings.py`.

Ejemplo mínimo nginx (ajusta rutas y dominio):

```nginx
server {
    listen 443 ssl;
    server_name api.miempresa.com;

    ssl_certificate     /etc/letsencrypt/live/api.miempresa.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.miempresa.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Certificado gratuito: `sudo apt install certbot python3-certbot-nginx && sudo certbot --nginx`

---

## 3. Comprobar en el servidor

```bash
cd /opt/win-backend
source env/bin/activate
python manage.py check_deploy --strict
```

Debe terminar sin errores.

Prueba manual de Host inválido:

```bash
curl -s -o /dev/null -w "%{http_code}" -H "Host: evil.example" http://127.0.0.1:8000/health/
# Esperado: 400 (DisallowedHost)
```

Con dominio correcto:

```bash
curl -s -H "Host: api.miempresa.com" http://127.0.0.1:8000/ready/
# Esperado: 200 y {"ready": true}
```

---

## 4. Qué no subir al repositorio

- `.env` del servidor (solo en el VPS)
- `SECRET_KEY`, contraseñas de BD, `ENCRYPTION_KEY`, tokens PanAccess
- Certificados TLS (van en `/etc/letsencrypt`)

---

## 5. Pruebas del roadmap #3

| Prueba | Comando | Esperado |
|--------|---------|----------|
| Modo producción | `check_deploy --strict` | Exit 0 |
| Sin debug | `DEBUG=false` en `.env` | `check_deploy` no alerta DEBUG |
| Hosts reales | Sin `*` en `ALLOWED_HOSTS` | Pasa `--strict` |
| Host malicioso | `curl -H "Host: evil"` | 400 |

---

## Referencias

- [ROADMAP_PRODUCCION.md](./ROADMAP_PRODUCCION.md) — ítem #4 CORS, #5 TLS/firewall
- [Django deployment checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)

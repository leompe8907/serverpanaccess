# Health y readiness (roadmap #17)

Endpoints para balanceadores, nginx y orquestadores **antes de enviar tráfico de usuarios**.

Implementación: `wind/views_health.py`

| Ruta | Uso | Comprueba |
|------|-----|-----------|
| `GET /ready/` | **Readiness** — ¿puedo recibir tráfico? | PostgreSQL/SQLite + caché Redis |
| `GET /health/` | **Liveness** + diagnóstico | DB + caché + sesión PanAccess |

## Respuestas

**Listo:**

```json
{"ready": true}
```

**No listo (503):**

```json
{"ready": false, "errors": ["database: ..."]}
```

## nginx (upstream solo si está ready)

Añade en `deploy/nginx/win-backend.conf` (o tu sitio):

```nginx
# Probe ligero — sin PanAccess (más rápido para LB)
location = /ready/ {
    proxy_pass http://win_gunicorn;
    proxy_set_header Host $host;
    access_log off;
}

location = /health/ {
    proxy_pass http://win_gunicorn;
    proxy_set_header Host $host;
    access_log off;
}
```

El balanceador puede usar:

```text
GET https://api.tudominio.com/ready/
```

- **200** → enviar tráfico al backend
- **503** → sacar del pool (DB caída, Redis caído, etc.)

## systemd / script de deploy

Antes de `systemctl reload nginx` tras un deploy:

```bash
curl -sf http://127.0.0.1:8000/ready/ || exit 1
```

## Diferencia ready vs health

| | `/ready/` | `/health/` |
|---|-----------|------------|
| PanAccess | No llama | Sí (`ensure_session`) |
| Coste | Bajo | Mayor |
| Uso típico | LB cada 10–30 s | Monitoreo / alertas |

Si PanAccess está caído pero DB/Redis OK, `/ready/` puede ser **200** y `/health/` **503** — útil para degradar sin tumbar todo el pool por un fallo externo temporal.

## Referencias

- [SYSTEMD_UBUNTU.md](./SYSTEMD_UBUNTU.md)
- [NGINX_TLS_Y_RESTRICCION_UBUNTU.md](./NGINX_TLS_Y_RESTRICCION_UBUNTU.md)

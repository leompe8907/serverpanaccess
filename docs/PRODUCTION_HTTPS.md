# PRODUCTION_HTTPS en Django (roadmap #23)

Defensa en profundidad cuando **nginx** ya termina TLS pero quieres cookies y HSTS también en Django.

## Activar en Ubuntu

En `.env` del servidor (con `DEBUG=false`):

```env
PRODUCTION_HTTPS=true
```

nginx debe enviar:

```nginx
proxy_set_header X-Forwarded-Proto $scheme;
```

## Qué activa en `settings.py`

Con `PRODUCTION_HTTPS=true` y `DEBUG=false`:

| Setting | Efecto |
|---------|--------|
| `SECURE_PROXY_SSL_HEADER` | Confía en `X-Forwarded-Proto: https` |
| `SECURE_SSL_REDIRECT` | Redirige HTTP→HTTPS si alguien llega sin nginx |
| `SESSION_COOKIE_SECURE` | Cookie de sesión solo HTTPS |
| `CSRF_COOKIE_SECURE` | CSRF solo HTTPS |
| `SECURE_HSTS_*` | HSTS 1 año (preload) |

## Comprobar

```bash
python manage.py check_deploy --strict
```

Los avisos `security.W004`, `W008`, `W012`, `W016` de `check --deploy` desaparecen con `PRODUCTION_HTTPS=true`.

## Local (Windows)

No activar en desarrollo HTTP (`localhost:8000`). Dejar `PRODUCTION_HTTPS` sin definir o `false`.

Para HTTPS local con Caddy use `docs/LOGIN_SOCIAL_LOCAL_HTTPS.md` sin `PRODUCTION_HTTPS`.

## Referencias

- [SEGURIDAD_PRODUCCION_UBUNTU.md](./SEGURIDAD_PRODUCCION_UBUNTU.md)
- [NGINX_TLS_Y_RESTRICCION_UBUNTU.md](./NGINX_TLS_Y_RESTRICCION_UBUNTU.md)

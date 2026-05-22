# CORS en producción (roadmap #4)

El frontend (React, Vite, app móvil web) suele estar en **otro dominio** que la API (`api.tudominio.com`). El navegador exige CORS para llamadas con `Authorization: Bearer ...`.

## 1. Variable en `.env` (Ubuntu)

Lista **orígenes exactos** del frontend (esquema + host + puerto si aplica):

```env
CORS_ALLOWED_ORIGINS=https://app.miempresa.com,https://www.miempresa.com
```

Reglas:

- Separados por **coma**, sin espacios extra.
- Incluye `https://` en producción (no mezclar http salvo dev).
- Si tienes www y sin www, lista **ambos**.
- No uses `*` ni `CORS_ALLOW_ALL_ORIGINS` (bloqueado en settings).

### Desarrollo local (front en :3000 / :5173)

Opción A — listar orígenes:

```env
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Opción B — defaults automáticos:

```env
CORS_DEV_DEFAULTS=true
```

(solo con `DEBUG=true` o con esta variable)

## 2. Relación con `ALLOWED_HOSTS`

| Variable | Qué valida |
|----------|------------|
| `ALLOWED_HOSTS` | Header **Host** de la petición al **backend** |
| `CORS_ALLOWED_ORIGINS` | Header **Origin** del **navegador** (frontend) |

Ejemplo típico:

```env
ALLOWED_HOSTS=api.miempresa.com
CORS_ALLOWED_ORIGINS=https://app.miempresa.com
```

## 3. JWT y credenciales

La API usa **JWT en header** (`Authorization: Bearer`). Por defecto:

```env
CORS_ALLOW_CREDENTIALS=false
```

No cambies a `true` salvo que uses cookies cross-site (no es el caso habitual con SimpleJWT).

## 4. Google / Facebook login

Los popups de OAuth usan el mismo backend; el front debe estar en un origen listado en `CORS_ALLOWED_ORIGINS` para llamadas API posteriores.

`SECURE_CROSS_ORIGIN_OPENER_POLICY = same-origin-allow-popups` ya está en settings.

Actualiza también **redirect URIs** en Google/Facebook Console con la URL pública del front/back.

## 5. Comprobar

```bash
python manage.py check_deploy --strict
```

Debe mostrar `CORS_ALLOWED_ORIGINS` con tus dominios (no lista vacía en prod).

### Preflight manual

```bash
curl -i -X OPTIONS "http://127.0.0.1:8000/api/v1/profile/me/" \
  -H "Origin: https://app.miempresa.com" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization,content-type"
```

Busca en la respuesta:

- `access-control-allow-origin: https://app.miempresa.com`
- Status `200` o `204`

Origen no permitido: **sin** `access-control-allow-origin` o error CORS en el navegador.

### Desde el navegador

1. Abre el front en su dominio.
2. DevTools → Red → petición a `/api/auth/login/` o `/api/v1/profile/me/`.
3. No debe aparecer error CORS; debe verse el header `Access-Control-Allow-Origin` con tu origen.

## 6. nginx

No hace falta configurar CORS en nginx si Django ya lo hace (`django-cors-headers`). Si nginx añade headers CORS duplicados, quítalos del proxy para evitar conflictos.

## 7. Pruebas roadmap #4

| Prueba | Esperado |
|--------|----------|
| `check_deploy --strict` | `CORS_ALLOWED_ORIGINS` definido en prod |
| OPTIONS con Origin válido | `access-control-allow-origin` presente |
| OPTIONS con Origin inválido | Sin allow-origin |
| Login + perfil desde el front | Sin error CORS en consola |

## Referencias

- [SEGURIDAD_PRODUCCION_UBUNTU.md](./SEGURIDAD_PRODUCCION_UBUNTU.md) — ALLOWED_HOSTS (#3)
- [ROADMAP_PRODUCCION.md](./ROADMAP_PRODUCCION.md)

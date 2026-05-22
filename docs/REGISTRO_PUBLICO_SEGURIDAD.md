# Registro público `/wind/create-subscriber/` (roadmap #7)

El formulario en `/wind/register/` llama a este endpoint **sin JWT** (el usuario aún no existe). La seguridad no es JWT, sino **límites de tasa** y poder **desactivar** el endpoint en prod.

## Variables `.env`

```env
CREATE_SUBSCRIBER_PUBLIC_ENABLED=true
DRF_THROTTLE_REGISTER=10/hour
```

| Variable | Prod recomendado | Efecto |
|----------|------------------|--------|
| `CREATE_SUBSCRIBER_PUBLIC_ENABLED` | `true` si usas `/wind/register/` | `false` → 403 en HTTP (login social sigue creando vía código interno) |
| `DRF_THROTTLE_REGISTER` | `10/hour` o más estricto | Máx. creaciones por IP (scope `register`) |

## Capas de protección

1. **DRF** — `RegisterThrottle` (anon, por IP).
2. **nginx** — `limit_req` en `deploy/nginx/win-backend.conf` (~5 req/min por IP en esa ruta).
3. **Validación de negocio** — email/documento únicos (ya en la vista).
4. **Login social** — usa `request.wind_internal_create = True` y **no consume** el cupo de throttle público.

## Pruebas

```bash
# Debe funcionar (datos válidos, dentro del límite)
curl -X POST http://127.0.0.1:8000/wind/create-subscriber/ \
  -H "Content-Type: application/json" \
  -d '{"lastName":"Test","firstName":"User","email":"nuevo@example.com"}'

# Tras superar el límite → 429 Too Many Requests

# Con registro deshabilitado
# CREATE_SUBSCRIBER_PUBLIC_ENABLED=false → 403
```

## Si solo usas Google/Facebook (sin formulario web)

```env
CREATE_SUBSCRIBER_PUBLIC_ENABLED=false
```

El alta seguirá funcionando en el adaptador social (bypass interno).

## Referencias

- [CREATE_SUBSCRIBER_FRONTEND.md](./CREATE_SUBSCRIBER_FRONTEND.md)
- [NGINX_TLS_Y_RESTRICCION_UBUNTU.md](./NGINX_TLS_Y_RESTRICCION_UBUNTU.md)

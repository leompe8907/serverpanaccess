# Locust en staging (roadmap #19)

Prueba de carga del **perfil de usuario**, no de sync (sync bloquea workers y no representa tráfico real).

Script: `scripts/load/locustfile.py`

## Requisitos

- Backend con **PostgreSQL** (mismo que prod)
- Usuario de prueba con credenciales PanAccess válidas
- Redis + caché operativos

```bash
pip install locust
```

## Variables

```bash
export LOCUST_USERNAME=codigo_o_email_abonado
export LOCUST_PASSWORD=contraseña
```

## Ejecutar contra staging

```bash
cd /opt/win-backend
locust -f scripts/load/locustfile.py --host https://api-staging.tudominio.com
```

Abre la UI en `http://localhost:8089`, usuarios concurrentes sugeridos para empezar: **50 → 200 → 500**.

## Tareas simuladas (pesos)

| Tarea | Peso | Endpoint |
|-------|------|----------|
| `profile_me` | 3 | `GET /api/v1/profile/me/` |
| `profile_products` | 2 | `GET /api/v1/profile/products/` |
| `health` | 1 | `GET /ready/` |

**No** incluye `/wind/sync-*` a propósito.

## Qué medir

- **p95** latencia de `profile-me` y `profile-products`
- Tasa de error 5xx
- CPU Gunicorn y conexiones PostgreSQL

Objetivo orientativo antes de prod: p95 &lt; 2 s en perfil con carga acordada con negocio (no 5k aún — ver roadmap #29).

## Informe mínimo

Anotar en la PR o wiki:

- Host, fecha, usuarios concurrentes, duración
- p50 / p95 / p99 de `profile-me`
- Errores (%)
- `manage.py check_deploy --strict` en el mismo entorno

## Referencias

- [ANALISIS_ESCALABILIDAD.md](./ANALISIS_ESCALABILIDAD.md)
- [PERFIL_PANACCESS.md](./PERFIL_PANACCESS.md)

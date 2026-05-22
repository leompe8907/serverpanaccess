# Objetivo ~5.000 usuarios concurrentes (roadmap #29)

Guía de arquitectura cuando el tráfico de **perfil y login** crezca. No es un deploy único; es evolución por fases.

## Estado actual (suficiente para arranque prod)

- Sync en Celery (no en workers web)
- Perfil por código de abonado (no listados globales)
- PostgreSQL + Redis + sesión PanAccess en Redis
- Throttling DRF, nginx, systemd

## Cuellos de botella si sube la concurrencia

| Componente | Síntoma | Acción |
|------------|---------|--------|
| Gunicorn | Cola de requests, p95 alto | Más workers (`--workers` 2×CPU+1), `threads` |
| PostgreSQL primary | CPU/connections | PgBouncer, `DB_REPLICA_HOST` lecturas — [DB_REPLICA_UBUNTU.md](./DB_REPLICA_UBUNTU.md) |
| PanAccess API | Timeouts perfil | Caché perfil (Redis 60–300 s), circuit breaker ya en `.env` |
| Redis | Memoria | Instancia dedicada, monitoreo |
| Login | Picos | Rate limit nginx + DRF |

## Fase A — Medir (staging)

1. [LOCUST_STAGING.md](./LOCUST_STAGING.md) con PostgreSQL.
2. Objetivo inicial: p95 `profile/me` &lt; 2 s con N concurrentes acordados.
3. `EXPLAIN ANALYZE` en queries lentas.

## Fase B — Ajustes rápidos

- Gunicorn: 4–8 workers, `CONN_MAX_AGE=600`
- Índices login — migración `0002_subscriberlogininfo_indexes`
- `CDN_STATIC_URL` para HTML estático — [CDN_STATIC.md](./CDN_STATIC.md)
- Caché Django en Redis para respuestas de perfil (implementar cuando profiling lo pida)

## Fase C — Escala horizontal

- Varios nodos Gunicorn detrás de LB
- `PANACCESS_SESSION_USE_REDIS=true` (obligatorio)
- PostgreSQL primary + réplica
- Celery workers en host separado si sync compite con CPU

## Qué no escalar con más usuarios web

- No mover sync a Gunicorn; mantener Celery.
- No abrir `/wind/sync-*` al público.

## Referencias

- [ANALISIS_ESCALABILIDAD.md](./ANALISIS_ESCALABILIDAD.md)
- [ROADMAP_PRODUCCION.md](./ROADMAP_PRODUCCION.md)

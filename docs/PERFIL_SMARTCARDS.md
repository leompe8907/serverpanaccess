# Smartcards en `/api/v1/profile/products/` (roadmap #13)

## Comportamiento

1. Lee smartcards del abonado desde **PostgreSQL** (`ListOfSmartcards` + SN en `ListOfSubscriber.smartcards`).
2. Si la BD local no tiene filas, refresca desde PanAccess **solo para ese abonado**:
   - `getListOfSmartcards` con `subscriberCode` (máx. 5 páginas por defecto).
   - `getSmartcard` por cada SN conocido del suscriptor (paralelo, default 5 workers).
3. **No** recorre 15×100 smartcards globales en modo perfil.

Implementación: `refresh_smartcards_from_panaccess(..., profile_mode=True)` en `subscriber_catalog.py` → `fetch_subscriber_smartcards_from_panaccess` en `getSmartcard.py`.

## Variables `.env`

```env
PANACCESS_SMARTCARD_SUBSCRIBER_MAX_PAGES=5
PANACCESS_SMARTCARD_PAGE_LIMIT=100
PANACCESS_SMARTCARD_SN_CONCURRENCY=5

# Solo emergencia (sync masivo antiguo); no usar en perfil
# PANACCESS_SMARTCARD_GLOBAL_FALLBACK=true
# PANACCESS_SMARTCARD_SYNC_MAX_PAGES=15
```

## Prueba en local

Con JWT y BD sin smartcards del abonado:

```bash
curl -H "Authorization: Bearer <token>" http://127.0.0.1:8000/api/v1/profile/products/
```

En logs: `Smartcards perfil/abonado ...` con pocas llamadas `getSmartcard` / list filtrado, **sin** ráfaga de `getListOfSmartcards` sin filtro.

Con BD ya sincronizada (deploy + compare cada 10 min): **0 llamadas** PanAccess.

## Referencias

- [PERFIL_PANACCESS.md](./PERFIL_PANACCESS.md) — ítem #12 (`/profile/me/`)
- [SYNC_FLUJO_TAREAS.md](./SYNC_FLUJO_TAREAS.md)

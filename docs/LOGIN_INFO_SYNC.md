# Login info en full-sync (roadmap #11)

`SubscriberLoginInfo` (login1, login2, password cifrado) se sincroniza en el **full-sync nocturno** vía `sync_subscribers_login_info()`.

## Problema anterior

Un `getSubscriberLoginInfo` **por cada** suscriptor + `update_or_create` en serie → horas con catálogos grandes.

## Estrategia actual

| Paso | Modo | Llamadas HTTP |
|------|------|----------------|
| 1 | **API listada** (`getListOfSubscriberLoginInfo`, etc.) si PanAccess la expone | ~`ceil(N/limit)` páginas |
| 2 | **Paralelo** por `subscriberCode` si no hay list API | N llamadas, pero `PANACCESS_LOGIN_INFO_CONCURRENCY` en paralelo |
| Siempre | **Upsert masivo** en PostgreSQL (`bulk_create` / `bulk_update`) | — |

## Variables `.env`

```env
# Probar APIs listadas al arrancar el primer full-sync de login
PANACCESS_LOGIN_INFO_TRY_LIST_API=true

# Workers en modo paralelo (default 10)
PANACCESS_LOGIN_INFO_CONCURRENCY=10

# Paginación API listada
PANACCESS_LOGIN_INFO_PAGE_LIMIT=200

# Tamaño de chunk en BD
PANACCESS_LOGIN_INFO_DB_CHUNK=200
```

## Probar en local

```bash
python manage.py shell -c "
from wind.functions.getSubscriberLoginInfo import sync_subscribers_login_info
import time
t0 = time.time()
r = sync_subscribers_login_info(limit=50)  # prueba con 50 códigos
print(r, 'segundos', round(time.time()-t0, 1))
"
```

Revisa en logs `modo=list_api` o `modo=parallel`.

## Notas

- `getSubscriberLoginInfo` **por código** sigue existiendo para perfil, auth y vistas puntuales.
- Tras `fetch_all_subscribers` / altas nuevas, login info de ese lote usa `fetch_login_info_for_codes` (paralelo acotado al batch).

## Referencias

- `wind/functions/getSubscriberLoginInfo.py`
- [SYNC_FLUJO_TAREAS.md](./SYNC_FLUJO_TAREAS.md)
- [FULL_SYNC_PRODUCCION.md](./FULL_SYNC_PRODUCCION.md)

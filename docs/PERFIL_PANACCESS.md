# Perfil `/api/v1/profile/me/` (roadmap #12)

## Comportamiento

1. Resuelve el `subscriber_code` del usuario JWT.
2. Lee `ListOfSubscriber` + `SubscriberLoginInfo` en **PostgreSQL** (datos ya sincronizados por Celery).
3. Solo si faltan datos locales, llama a PanAccess **una vez por código**:
   - `getSubscriber` / `getExtendedSubscriber`
   - **No** recorre `getListOfExtendedSubscribers` página por página.

Implementación: `_sync_subscriber_row_from_panaccess` en `wind/services/subscriber_catalog.py` → `CallGetSubscriber` en `wind/functions/getSubscriber.py`.

## Prueba en local

```bash
# Con JWT de un usuario vinculado a un abonado
curl -H "Authorization: Bearer <access>" http://127.0.0.1:8000/api/v1/profile/me/
```

En logs debe aparecer `Suscriptor <code> obtenido vía getSubscriber` (como mucho 1–2 intentos de nombre de API), **no** una secuencia de `getListOfExtendedSubscribers` con offset creciente.

## Productos / smartcards

Ver [PERFIL_SMARTCARDS.md](./PERFIL_SMARTCARDS.md) (ítem **#13**).

## Referencias

- `wind/api/profile/views.py` — `profile_me_view`
- [SYNC_FLUJO_TAREAS.md](./SYNC_FLUJO_TAREAS.md)

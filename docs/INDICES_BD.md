# Índices de base de datos (roadmap #27)

## Migración `0002_subscriberlogininfo_indexes`

Índices en `SubscriberLoginInfo` para login portal (consultas por `login1`, `login2`, `subscriberCode`):

| Campo | Uso |
|-------|------|
| `subscriberCode` | Perfil, sync, borrado por lote |
| `login1` | `authenticate_portal_user` |
| `login2` | Login texto libre |

Aplicar:

```bash
python manage.py migrate
```

## Verificar en PostgreSQL

```sql
EXPLAIN ANALYZE
SELECT * FROM wind_subscriberlogininfo WHERE login1 = 12345 LIMIT 1;
```

Debe usar índice en `login1` (Index Scan), no Seq Scan en tablas grandes.

## Más índices

Solo añadir tras profiling (`EXPLAIN`, logs lentos). Candidatos futuros:

- `SubscriberEmailRegistry.subscriber_code` (si no existe búsqueda por código frecuente)
- Compuestos solo si un query fijo lo justifica

## Referencias

- `wind/models.py`
- [ESCALA_5000_USUARIOS.md](./ESCALA_5000_USUARIOS.md)

# Réplica PostgreSQL de lectura (roadmap #24)

Opcional. Cuando el **perfil** y listados saturan el primary, las lecturas van a una réplica; escrituras (sync, login que guarda) siguen en el primary.

## Ya implementado en código

- `DB_REPLICA_HOST` / `DB_REPLICA_PORT` en `.env`
- `wind.db_router.PrimaryReplicaRouter` — lecturas → `replica`, escrituras → `default`

## Configuración

```env
DB_ENGINE=django.db.backends.postgresql
DB_NAME=wind
DB_USER=wind
DB_PASSWORD=...
DB_HOST=primary-host
DB_PORT=5432

DB_REPLICA_HOST=replica-host
DB_REPLICA_PORT=5432
```

Sin `DB_REPLICA_HOST` todo usa solo `default` (comportamiento actual).

## Comprobar

```bash
python manage.py shell -c "
from django.conf import settings
print('databases:', list(settings.DATABASES.keys()))
"
# Debe listar: default, replica
```

## Notas

- Migraciones solo en **primary** (`allow_migrate` → default).
- Lag de réplica: lecturas de perfil pueden ir 1–2 s detrás tras un sync; aceptable para `/profile/me/`.
- En dev (SQLite) la réplica no aplica.

## Referencias

- [POSTGRESQL_UBUNTU.md](./POSTGRESQL_UBUNTU.md)
- `wind/db_router.py`
